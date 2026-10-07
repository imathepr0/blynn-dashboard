"""
Seguridad transversal de la API de datos (Etapa 3):

* TODO endpoint exige autenticación (barrido automático sobre OpenAPI, así
  que un endpoint futuro que olvide la protección hace fallar esta prueba).
* Un usuario NUNCA puede leer, cambiar ni borrar datos de otro (IDOR).
* No se pueden inyectar campos internos (`user_id`, `id`, `created_date`).
* Se limita el tamaño de las peticiones.
"""
import uuid

import pytest

from tests.utils import API, CATEGORIA, GASTO, INGRESO, META

PUBLICOS = {
    ("GET", "/health"),
    ("GET", "/health/ready"),
    ("POST", "/api/v1/auth/register"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/refresh"),
    ("POST", "/api/v1/auth/logout"),
}


def _endpoints(app):
    for ruta, metodos in app.openapi()["paths"].items():
        for metodo in metodos:
            if metodo.upper() in {"GET", "POST", "PATCH", "PUT", "DELETE"}:
                yield metodo.upper(), ruta


def _url(ruta: str) -> str:
    import re

    return re.sub(r"\{[^}]+\}", str(uuid.uuid4()), ruta)


def test_hay_endpoints_de_datos_para_barrer():
    from app.main import app

    protegidos = [e for e in _endpoints(app) if e not in PUBLICOS]
    assert len(protegidos) >= 25  # si baja, el barrido dejó de cubrir algo


def test_todo_endpoint_no_publico_exige_autenticacion(cliente):
    from app.main import app

    fallos = []
    for metodo, ruta in _endpoints(app):
        if (metodo, ruta) in PUBLICOS:
            continue
        r = cliente.request(metodo, _url(ruta), json={} if metodo in ("POST", "PATCH", "PUT") else None)
        if r.status_code != 401:
            fallos.append((metodo, ruta, r.status_code))
    assert fallos == [], f"Endpoints accesibles sin sesión: {fallos}"


def test_todo_endpoint_no_publico_rechaza_un_token_falso(cliente):
    from app.main import app

    for metodo, ruta in _endpoints(app):
        if (metodo, ruta) in PUBLICOS:
            continue
        r = cliente.request(
            metodo, _url(ruta), headers={"Authorization": "Bearer esto.no.es.un.jwt"},
            json={} if metodo in ("POST", "PATCH", "PUT") else None,
        )
        assert r.status_code == 401, (metodo, ruta, r.status_code)


RECURSOS = [
    # (ruta base, datos de creación, cambio válido para PATCH)
    ("/categories", CATEGORIA, {"name": "Hackeada"}),
    ("/expenses", GASTO, {"merchant": "Hackeado"}),
    ("/incomes", INGRESO, {"source": "Hackeado"}),
    ("/goals", META, {"title": "Hackeada"}),
]


@pytest.mark.parametrize("base, datos, cambio", RECURSOS)
def test_un_usuario_no_puede_ver_cambiar_ni_borrar_datos_de_otro(ana, beto, base, datos, cambio):
    original = ana.crear(base, datos)
    ruta = f"{base}/{original['id']}"

    # Para Beto es exactamente igual que si no existiera.
    assert beto.get(ruta).status_code == 404
    assert beto.patch(ruta, cambio).status_code == 404
    assert beto.delete(ruta).status_code == 404
    # La respuesta no revela que el id existe.
    assert beto.get(ruta).json() == beto.get(f"{base}/{uuid.uuid4()}").json()

    # Nada cambió para su dueña.
    despues = ana.get(ruta)
    assert despues.status_code == 200 and despues.json() == original
    # Y no aparece en el listado de Beto.
    assert beto.get(base).json() == []
    assert [x["id"] for x in ana.get(base).json()] == [original["id"]]


def test_aportes_de_otro_usuario_son_inalcanzables(ana, beto):
    meta = ana.crear("/goals", META)
    r = ana.post(f"/goals/{meta['id']}/contributions", {"amount": 5000, "date": "2026-09-29"})
    aporte = r.json()["contribution"]

    assert beto.post(f"/goals/{meta['id']}/contributions", {"amount": 1, "date": "2026-09-29"}).status_code == 404
    assert beto.delete(f"/contributions/{aporte['id']}").status_code == 404
    assert beto.get("/contributions").json() == []
    assert beto.get("/contributions", params={"goal_id": meta["id"]}).json() == []

    meta_ana = ana.get(f"/goals/{meta['id']}").json()
    assert meta_ana["current_amount"] == 5000  # Beto no logró tocar nada
    assert len(ana.get("/contributions").json()) == 1


@pytest.mark.parametrize("base, datos", [(b, d) for b, d, _ in RECURSOS])
@pytest.mark.parametrize("campo", ["id", "user_id", "created_date", "updated_date", "created_by"])
def test_no_se_pueden_inyectar_campos_internos_al_crear(ana, beto, base, datos, campo):
    valor = beto.id if campo in ("user_id", "created_by") else str(uuid.uuid4())
    r = ana.post(base, {**datos, campo: valor})
    assert r.status_code == 422
    assert ana.get(base).json() == []
    assert beto.get(base).json() == []


@pytest.mark.parametrize("base, datos, cambio", RECURSOS)
def test_no_se_puede_reasignar_el_dueno_con_patch(ana, beto, base, datos, cambio):
    recurso = ana.crear(base, datos)
    r = ana.patch(f"{base}/{recurso['id']}", {"user_id": beto.id})
    assert r.status_code == 422
    assert beto.get(base).json() == []
    assert len(ana.get(base).json()) == 1


@pytest.mark.parametrize("base", [b for b, _, _ in RECURSOS])
def test_id_mal_formado_es_422_y_id_inexistente_es_404(ana, base):
    assert ana.get(f"{base}/no-es-un-uuid").status_code == 422
    assert ana.get(f"{base}/{uuid.uuid4()}").status_code == 404
    assert ana.delete(f"{base}/{uuid.uuid4()}").status_code == 404


def test_no_se_puede_registrar_aporte_con_id_de_meta_mal_formado(ana):
    assert ana.post("/goals/xyz/contributions", {"amount": 1, "date": "2026-09-29"}).status_code == 422


def test_los_listados_solo_devuelven_lo_propio_aunque_haya_muchos_usuarios(ana, beto):
    for _ in range(3):
        ana.crear("/expenses", GASTO)
    beto.crear("/expenses", {**GASTO, "merchant": "De Beto"})
    assert len(ana.get("/expenses").json()) == 3
    assert [g["merchant"] for g in beto.get("/expenses").json()] == ["De Beto"]


# --- Tamaño de las peticiones ------------------------------------------
def test_cuerpo_demasiado_grande_se_rechaza_con_413(ana):
    enorme = {**GASTO, "description": "x" * 2_000_000}
    r = ana.post("/expenses", enorme)
    assert r.status_code == 413
    assert ana.get("/expenses").json() == []


def test_cuerpo_grande_enviado_por_partes_tambien_se_rechaza(ana):
    def partes():
        yield b'{"merchant": "X", "description": "'
        for _ in range(30):
            yield b"a" * 100_000
        yield b'", "amount": 1, "category": "Otros", "date": "2026-09-29"}'

    r = ana.cliente.post(
        f"{API}/expenses", content=partes(), headers={**ana.headers, "Content-Type": "application/json"}
    )
    assert r.status_code == 413


def test_la_respuesta_413_lleva_cabeceras_cors(ana):
    r = ana.cliente.post(
        f"{API}/expenses",
        json={**GASTO, "description": "x" * 2_000_000},
        headers={**ana.headers, "Origin": "http://localhost:5173"},
    )
    assert r.status_code == 413
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_un_cuerpo_normal_pasa_el_limite(ana):
    assert ana.post("/expenses", {**GASTO, "description": "x" * 4000}).status_code == 201
