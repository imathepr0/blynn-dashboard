"""
Límite de intentos compartido (app/auth/rate_limit.py): vive en la base de datos.

"Instancia" = una sesión de base de datos y un objeto limitador propios. Dos instancias
que comparten la base deben ver el MISMO conteo; con contadores en memoria cada una
contaría por separado y el límite casi no protegería en Vercel o Cloud Run.
"""
from sqlalchemy import select
from starlette.requests import Request

from app.auth.rate_limit import LimitadorDeIntentos, ip_cliente
from app.config import Settings
from app.db.models import IntentoLimitado


class Reloj:
    def __init__(self, t: float = 1_000_000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t


def _limpiar(db):
    db.query(IntentoLimitado).delete()
    db.commit()


def test_permite_hasta_el_maximo_y_luego_bloquea_con_los_segundos_que_faltan(fabrica_sesiones):
    r = Reloj()
    lim = LimitadorDeIntentos("t", 3, 60, reloj=r)
    with fabrica_sesiones() as db:
        for _ in range(3):
            assert lim.segundos_de_espera(db, "a") == 0
            lim.registrar(db, "a")
        assert 0 < lim.segundos_de_espera(db, "a") <= 61
        r.t += 30
        assert 0 < lim.segundos_de_espera(db, "a") <= 31


def test_la_ventana_se_desliza_y_vuelve_a_permitir(fabrica_sesiones):
    r = Reloj()
    lim = LimitadorDeIntentos("t", 2, 60, reloj=r)
    with fabrica_sesiones() as db:
        lim.registrar(db, "a")
        r.t += 40
        lim.registrar(db, "a")
        assert lim.segundos_de_espera(db, "a") > 0
        r.t += 25  # el primero ya salió de la ventana (65 s), el segundo no
        assert lim.segundos_de_espera(db, "a") == 0


def test_dos_instancias_comparten_el_conteo(fabrica_sesiones):
    """Lo esencial de este cambio: con varias instancias el límite sigue valiendo."""
    r = Reloj()
    instancia_1 = LimitadorDeIntentos("login", 3, 60, reloj=r)
    instancia_2 = LimitadorDeIntentos("login", 3, 60, reloj=r)
    with fabrica_sesiones() as db1, fabrica_sesiones() as db2:
        instancia_1.registrar(db1, "ana|1.2.3.4")
        instancia_2.registrar(db2, "ana|1.2.3.4")
        instancia_1.registrar(db1, "ana|1.2.3.4")
        assert instancia_2.segundos_de_espera(db2, "ana|1.2.3.4") > 0  # ya van 3 entre las dos
        assert instancia_1.segundos_de_espera(db1, "ana|1.2.3.4") > 0


def test_el_registro_queda_confirmado_aunque_la_peticion_deshaga_su_transaccion(fabrica_sesiones):
    """Un login fallido termina en error 401 y la petición hace rollback: el fallo debe contar igual."""
    lim = LimitadorDeIntentos("t", 1, 60)
    with fabrica_sesiones() as db:
        lim.registrar(db, "a")
        db.rollback()
    with fabrica_sesiones() as otra:
        assert lim.segundos_de_espera(otra, "a") > 0


def test_las_claves_y_los_limites_son_independientes(fabrica_sesiones):
    lim_a = LimitadorDeIntentos("uno", 1, 60)
    lim_b = LimitadorDeIntentos("dos", 1, 60)
    with fabrica_sesiones() as db:
        lim_a.registrar(db, "x")
        assert lim_a.segundos_de_espera(db, "x") > 0
        assert lim_a.segundos_de_espera(db, "y") == 0  # otra clave
        assert lim_b.segundos_de_espera(db, "x") == 0  # otro límite, misma clave


def test_reiniciar_borra_solo_esa_clave(fabrica_sesiones):
    lim = LimitadorDeIntentos("t", 1, 60)
    with fabrica_sesiones() as db:
        lim.registrar(db, "a")
        lim.registrar(db, "b")
        lim.reiniciar(db, "a")
        assert lim.segundos_de_espera(db, "a") == 0
        assert lim.segundos_de_espera(db, "b") > 0


def test_lo_vencido_se_limpia_de_la_tabla(fabrica_sesiones):
    r = Reloj()
    lim = LimitadorDeIntentos("t", 5, 60, reloj=r)
    with fabrica_sesiones() as db:
        for _ in range(4):
            lim.registrar(db, "a")
        r.t += 120
        lim.registrar(db, "a")
        assert len(db.scalars(select(IntentoLimitado)).all()) == 1


def test_ni_el_correo_ni_la_ip_se_guardan_en_claro(fabrica_sesiones):
    lim = LimitadorDeIntentos("fallos_cuenta", 5, 60)
    with fabrica_sesiones() as db:
        lim.registrar(db, "ana@correo.cl|203.0.113.9")
        fila = db.scalars(select(IntentoLimitado)).one()
        assert len(fila.clave) == 64 and all(c in "0123456789abcdef" for c in fila.clave)
        assert "ana" not in fila.clave and "203" not in fila.clave


# ---------------------------------------------------------------------- #
# IP del cliente detrás de un proxy
# ---------------------------------------------------------------------- #
def _peticion(cabeceras: dict[str, str], ip: str = "10.0.0.1") -> Request:
    return Request(
        {"type": "http", "headers": [(k.lower().encode(), v.encode()) for k, v in cabeceras.items()], "client": (ip, 1234)}
    )


def _config(**extra) -> Settings:
    return Settings(JWT_SECRET_KEY="k" * 64, **extra)


def test_por_defecto_la_ip_es_la_del_servidor_y_las_cabeceras_falsificadas_no_cuentan():
    r = _peticion({"X-Forwarded-For": "6.6.6.6", "X-Real-IP": "6.6.6.6"})
    assert ip_cliente(r) == "10.0.0.1"
    assert ip_cliente(r, _config()) == "10.0.0.1"


def test_con_cabecera_de_confianza_configurada_se_usa_esa_ip():
    config = _config(TRUSTED_CLIENT_IP_HEADER="x-real-ip")
    assert ip_cliente(_peticion({"X-Real-IP": "198.51.100.7"}), config) == "198.51.100.7"
    assert ip_cliente(_peticion({"X-Real-IP": "198.51.100.7, 10.1.1.1"}), config) == "198.51.100.7"


def test_si_la_cabecera_de_confianza_falta_o_viene_vacia_se_usa_la_ip_del_servidor():
    config = _config(TRUSTED_CLIENT_IP_HEADER="x-real-ip")
    assert ip_cliente(_peticion({}), config) == "10.0.0.1"
    assert ip_cliente(_peticion({"X-Real-IP": "  "}), config) == "10.0.0.1"


def test_otras_cabeceras_siguen_sin_confiarse_aunque_haya_una_configurada():
    config = _config(TRUSTED_CLIENT_IP_HEADER="x-real-ip")
    assert ip_cliente(_peticion({"X-Forwarded-For": "6.6.6.6"}), config) == "10.0.0.1"
