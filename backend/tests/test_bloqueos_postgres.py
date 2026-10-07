"""
Pruebas DETERMINISTAS de los bloqueos de fila (`SELECT ... FOR UPDATE`).

Las pruebas de concurrencia con muchos hilos (en otros archivos) dependen
del reparto de tiempo del sistema: pueden pasar "de suerte" aunque falte
el bloqueo. Estas no: una transacción ajena retiene el bloqueo de la fila,
se lanza la petición en otro hilo y se comprueba que ESPERA. Si el endpoint
no tomara el bloqueo, respondería de inmediato y la prueba fallaría siempre.
"""
import threading

import pytest
from sqlalchemy import text

from app.auth.tokens import huella_refresh_token
from tests.conftest import USA_POSTGRES
from tests.utils import API, META, Usuario

pytestmark = pytest.mark.skipif(not USA_POSTGRES, reason="requiere Postgres real (bloqueo de filas)")

ESPERA_PARA_CONSIDERAR_BLOQUEADA = 1.0  # segundos


def _lanzar(funcion):
    resultado: list = []
    hilo = threading.Thread(target=lambda: resultado.append(funcion()))
    hilo.start()
    return hilo, resultado


def _debe_esperar_y_luego_terminar(motor_bd, sql_de_bloqueo, parametros, peticion, esperado):
    """Retiene el bloqueo, lanza la petición, comprueba que espera; al soltar
    el bloqueo, la petición termina con el resultado `esperado`."""
    with motor_bd.connect() as ajena:
        ajena.execute(text(sql_de_bloqueo), parametros)  # toma el bloqueo
        hilo, resultado = _lanzar(peticion)
        hilo.join(timeout=ESPERA_PARA_CONSIDERAR_BLOQUEADA)
        esperando = hilo.is_alive()
        ajena.rollback()  # suelta el bloqueo
    hilo.join(timeout=15)
    assert esperando, "La petición NO esperó al bloqueo: el endpoint no toma FOR UPDATE."
    assert not hilo.is_alive() and resultado == [esperado], resultado


def test_refresh_espera_el_bloqueo_de_la_fila_del_token(cliente, motor_bd):
    u = Usuario(cliente, "bloqueo1@correo.cl")
    refresh = cliente.post(f"{API}/auth/login", json={"email": u.email, "password": "Tr3s-Tristes-Tigres"}).json()["refresh_token"]
    _debe_esperar_y_luego_terminar(
        motor_bd,
        "SELECT id FROM refresh_tokens WHERE token_hash = :h FOR UPDATE",
        {"h": huella_refresh_token(refresh)},
        lambda: cliente.post(f"{API}/auth/refresh", json={"refresh_token": refresh}).status_code,
        200,
    )


def test_registrar_aporte_espera_el_bloqueo_de_la_meta(cliente, motor_bd):
    u = Usuario(cliente, "bloqueo2@correo.cl")
    meta = u.crear("/goals", META)
    _debe_esperar_y_luego_terminar(
        motor_bd,
        "SELECT id FROM goals WHERE id = :id FOR UPDATE",
        {"id": meta["id"]},
        lambda: u.post(f"/goals/{meta['id']}/contributions", {"amount": 1000, "date": "2026-09-29"}).status_code,
        201,
    )
    assert u.get(f"/goals/{meta['id']}").json()["current_amount"] == 1000


def test_deshacer_aporte_espera_el_bloqueo_de_la_meta(cliente, motor_bd):
    u = Usuario(cliente, "bloqueo3@correo.cl")
    meta = u.crear("/goals", META)
    aporte = u.post(f"/goals/{meta['id']}/contributions", {"amount": 1000, "date": "2026-09-29"}).json()["contribution"]
    _debe_esperar_y_luego_terminar(
        motor_bd,
        "SELECT id FROM goals WHERE id = :id FOR UPDATE",
        {"id": meta["id"]},
        lambda: u.delete(f"/contributions/{aporte['id']}").status_code,
        200,
    )
    assert u.get(f"/goals/{meta['id']}").json()["current_amount"] == 0


def test_actualizar_meta_espera_el_bloqueo_de_su_fila(cliente, motor_bd):
    u = Usuario(cliente, "bloqueo4@correo.cl")
    meta = u.crear("/goals", META)
    _debe_esperar_y_luego_terminar(
        motor_bd,
        "SELECT id FROM goals WHERE id = :id FOR UPDATE",
        {"id": meta["id"]},
        lambda: u.patch(f"/goals/{meta['id']}", {"title": "Nuevo"}).status_code,
        200,
    )


def test_dos_deshacer_esperando_el_mismo_bloqueo_descuentan_una_sola_vez(cliente, motor_bd):
    """Dos peticiones leen el aporte y quedan esperando la meta. Al soltarse
    el bloqueo, la segunda debe volver a leer, ver que ya no existe y
    responder 404 (no descontar otra vez ni fallar con 500)."""
    import time

    u = Usuario(cliente, "bloqueo5@correo.cl")
    meta = u.crear("/goals", META)
    aporte = u.post(f"/goals/{meta['id']}/contributions", {"amount": 1000, "date": "2026-09-29"}).json()["contribution"]
    u.post(f"/goals/{meta['id']}/contributions", {"amount": 5000, "date": "2026-09-29"})

    with motor_bd.connect() as ajena:
        ajena.execute(text("SELECT id FROM goals WHERE id = :id FOR UPDATE"), {"id": meta["id"]})
        hilo_a, res_a = _lanzar(lambda: u.delete(f"/contributions/{aporte['id']}").status_code)
        hilo_b, res_b = _lanzar(lambda: u.delete(f"/contributions/{aporte['id']}").status_code)
        time.sleep(1.5)  # ambas ya pasaron la primera lectura y esperan el bloqueo
        assert hilo_a.is_alive() and hilo_b.is_alive()
        ajena.rollback()
    hilo_a.join(timeout=15)
    hilo_b.join(timeout=15)

    assert sorted(res_a + res_b) == [200, 404]
    assert u.get(f"/goals/{meta['id']}").json()["current_amount"] == 5000
