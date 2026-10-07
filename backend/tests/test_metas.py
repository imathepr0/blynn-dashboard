"""Pruebas de metas de ahorro y aportes (operaciones atómicas)."""
import threading

import pytest
from sqlalchemy.orm import Session

from tests.conftest import USA_POSTGRES
from tests.utils import META, Usuario

APORTE = {"amount": 40000, "date": "2026-09-29"}


def _aportar(u, meta_id, **extra):
    r = u.post(f"/goals/{meta_id}/contributions", {**APORTE, **extra})
    assert r.status_code == 201, r.text
    return r.json()


# --- Metas: CRUD y validación ----------------------------------------------
def test_crear_meta_aplica_valores_por_defecto(ana):
    m = ana.crear("/goals", META)
    assert m["current_amount"] == 0 and m["color"] == "#22c55e"
    assert m["contribution_mode"] == "manual" and m["contribution_frequency"] == "meses"
    assert m["auto_approved_count"] == 0 and m["deadline"] is None
    assert "user_id" not in m


def test_crud_de_metas(ana):
    m = ana.crear("/goals", {**META, "deadline": "2027-03-01"})
    assert ana.get(f"/goals/{m['id']}").json() == m
    r = ana.patch(f"/goals/{m['id']}", {"target_amount": 700000})
    assert r.json()["target_amount"] == 700000 and r.json()["title"] == "Notebook"
    assert ana.patch(f"/goals/{m['id']}", {"deadline": None}).json()["deadline"] is None
    assert ana.delete(f"/goals/{m['id']}").status_code == 204
    assert ana.get(f"/goals/{m['id']}").status_code == 404


def test_modo_porcentaje_exige_porcentaje_y_modo_fijo_exige_monto(ana):
    assert ana.post("/goals", {**META, "contribution_mode": "percent_surplus"}).status_code == 422
    assert ana.post("/goals", {**META, "contribution_mode": "fixed"}).status_code == 422
    ok = ana.post("/goals", {**META, "contribution_mode": "percent_surplus", "contribution_percent": 12.5})
    assert ok.status_code == 201 and ok.json()["contribution_percent"] == 12.5
    ok = ana.post("/goals", {**META, "contribution_mode": "fixed", "contribution_amount": 20000, "contribution_frequency": "semanas"})
    assert ok.status_code == 201


def test_patch_de_modo_valida_el_registro_completo(ana):
    m = ana.crear("/goals", META)
    assert ana.patch(f"/goals/{m['id']}", {"contribution_mode": "fixed"}).status_code == 422
    assert ana.get(f"/goals/{m['id']}").json() == m  # no quedó a medias
    ok = ana.patch(f"/goals/{m['id']}", {"contribution_mode": "fixed", "contribution_amount": 15000})
    assert ok.status_code == 200
    # Y no se puede quitar el dato que el modo necesita.
    assert ana.patch(f"/goals/{m['id']}", {"contribution_amount": None}).status_code == 422


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("title", ""), ("title", "x" * 256), ("target_amount", 0), ("target_amount", -1), ("target_amount", 1.5),
        ("target_amount", "600000"), ("target_amount", 10**12 + 1), ("current_amount", -1), ("current_amount", 2.5),
        ("deadline", "mañana"), ("deadline", "1999-01-01"), ("color", "verde"),
        ("contribution_mode", "auto"), ("contribution_frequency", "años"),
        ("contribution_percent", 0), ("contribution_percent", -5), ("contribution_percent", 100.5),
        ("contribution_percent", "10"), ("contribution_amount", 0),
    ],
)
def test_crear_meta_con_datos_invalidos_es_422(ana, campo, valor):
    extra = {}
    if campo in ("contribution_percent",):
        extra = {"contribution_mode": "percent_surplus"}
    elif campo == "contribution_amount":
        extra = {"contribution_mode": "fixed"}
    assert ana.post("/goals", {**META, **extra, campo: valor}).status_code == 422, (campo, valor)
    assert ana.get("/goals").json() == []


def test_el_contador_de_aprobados_no_lo_puede_fijar_el_cliente(ana):
    assert ana.post("/goals", {**META, "auto_approved_count": 99}).status_code == 422
    m = ana.crear("/goals", META)
    assert ana.patch(f"/goals/{m['id']}", {"auto_approved_count": 99}).status_code == 422


def test_patch_de_meta_no_acepta_nulos_en_obligatorios(ana):
    m = ana.crear("/goals", META)
    for campo in ("title", "target_amount", "current_amount", "color", "contribution_mode", "contribution_frequency"):
        assert ana.patch(f"/goals/{m['id']}", {campo: None}).status_code == 422, campo


def test_listado_de_metas_orden_y_paginacion(ana):
    for t, monto in [("A", 300), ("B", 100), ("C", 200)]:
        ana.crear("/goals", {**META, "title": t, "target_amount": monto})
    assert [m["title"] for m in ana.get("/goals", params={"sort": "target_amount"}).json()] == ["B", "C", "A"]
    assert len(ana.get("/goals", params={"limit": 1}).json()) == 1
    assert ana.get("/goals", params={"sort": "user_id"}).status_code == 422


# --- Aportes: semántica de cada modo -----------------------------------------
def test_aporte_manual_suma_a_la_meta_y_guarda_el_nombre(ana):
    m = ana.crear("/goals", META)
    r = _aportar(ana, m["id"], mode="manual")
    assert r["contribution"]["amount"] == 40000 and r["contribution"]["mode"] == "manual"
    assert r["contribution"]["goal_title"] == "Notebook" and r["contribution"]["goal_id"] == m["id"]
    assert r["goal"]["current_amount"] == 40000 and r["goal"]["auto_approved_count"] == 0
    assert ana.get(f"/goals/{m['id']}").json()["current_amount"] == 40000


def test_el_aporte_es_manual_si_no_se_indica_modo(ana):
    m = ana.crear("/goals", META)
    assert _aportar(ana, m["id"])["contribution"]["mode"] == "manual"


def test_aporte_aprobado_cuenta_y_mueve_la_proxima_fecha(ana):
    m = ana.crear("/goals", {**META, "next_contribution_date": "2026-09-29"})
    r = _aportar(ana, m["id"], mode="aprobado", next_contribution_date="2026-10-29")
    assert r["goal"]["auto_approved_count"] == 1
    assert r["goal"]["next_contribution_date"] == "2026-10-29"
    r = _aportar(ana, m["id"], mode="aprobado")  # sin fecha: no se toca
    assert r["goal"]["auto_approved_count"] == 2 and r["goal"]["next_contribution_date"] == "2026-10-29"


def test_aporte_auto_no_cuenta_como_aprobado(ana):
    m = ana.crear("/goals", META)
    assert _aportar(ana, m["id"], mode="auto")["goal"]["auto_approved_count"] == 0


def test_la_proxima_fecha_puede_borrarse_con_null_explicito(ana):
    m = ana.crear("/goals", {**META, "next_contribution_date": "2026-09-29"})
    assert _aportar(ana, m["id"], next_contribution_date=None)["goal"]["next_contribution_date"] is None


def test_varios_aportes_acumulan(ana):
    m = ana.crear("/goals", META)
    for monto in (1000, 2500, 400):
        _aportar(ana, m["id"], amount=monto)
    assert ana.get(f"/goals/{m['id']}").json()["current_amount"] == 3900


def test_el_aporte_parte_del_monto_actual_de_la_meta(ana):
    m = ana.crear("/goals", {**META, "current_amount": 100000})
    assert _aportar(ana, m["id"], amount=500)["goal"]["current_amount"] == 100500


@pytest.mark.parametrize(
    "datos",
    [
        {"amount": 0, "date": "2026-09-29"}, {"amount": -5, "date": "2026-09-29"}, {"amount": 1.5, "date": "2026-09-29"},
        {"amount": "100", "date": "2026-09-29"}, {"amount": True, "date": "2026-09-29"},
        {"amount": 100}, {"date": "2026-09-29"}, {"amount": 100, "date": "1999-01-01"},
        {"amount": 100, "date": "2026-09-29", "mode": "regalo"},
        {"amount": 100, "date": "2026-09-29", "goal_id": "x"}, {"amount": 100, "date": "2026-09-29", "user_id": "x"},
        {"amount": 100, "date": "2026-09-29", "goal_title": "Falso"}, {"amount": 100, "date": "2026-09-29", "current_amount": 9},
    ],
)
def test_aporte_invalido_es_422_y_no_cambia_nada(ana, datos):
    m = ana.crear("/goals", META)
    assert ana.post(f"/goals/{m['id']}/contributions", datos).status_code == 422
    assert ana.get(f"/goals/{m['id']}").json() == m
    assert ana.get("/contributions").json() == []


def test_aporte_a_meta_inexistente_es_404(ana):
    import uuid

    assert ana.post(f"/goals/{uuid.uuid4()}/contributions", APORTE).status_code == 404


def test_un_aporte_no_puede_superar_el_monto_maximo_de_la_meta(ana):
    m = ana.crear("/goals", {**META, "current_amount": 10**12})
    r = ana.post(f"/goals/{m['id']}/contributions", {"amount": 1, "date": "2026-09-29"})
    assert r.status_code == 422
    assert ana.get(f"/goals/{m['id']}").json()["current_amount"] == 10**12
    assert ana.get("/contributions").json() == []


# --- Deshacer -----------------------------------------------------------------
def test_deshacer_descuenta_devuelve_la_meta_y_borra_el_aporte(ana):
    m = ana.crear("/goals", META)
    a1 = _aportar(ana, m["id"], amount=1000)["contribution"]
    _aportar(ana, m["id"], amount=2000)
    r = ana.delete(f"/contributions/{a1['id']}")
    assert r.status_code == 200 and r.json()["id"] == m["id"] and r.json()["current_amount"] == 2000
    assert [a["amount"] for a in ana.get("/contributions").json()] == [2000]


def test_deshacer_dos_veces_da_404_y_no_descuenta_dos_veces(ana):
    m = ana.crear("/goals", META)
    a = _aportar(ana, m["id"], amount=1000)["contribution"]
    _aportar(ana, m["id"], amount=5000)
    assert ana.delete(f"/contributions/{a['id']}").status_code == 200
    assert ana.delete(f"/contributions/{a['id']}").status_code == 404
    assert ana.get(f"/goals/{m['id']}").json()["current_amount"] == 5000


def test_deshacer_nunca_deja_la_meta_bajo_cero(ana):
    m = ana.crear("/goals", META)
    a = _aportar(ana, m["id"], amount=9000)["contribution"]
    ana.patch(f"/goals/{m['id']}", {"current_amount": 1000})  # el usuario corrigió el monto a mano
    assert ana.delete(f"/contributions/{a['id']}").json()["current_amount"] == 0


def test_deshacer_un_aporte_aprobado_no_baja_el_contador(ana):
    m = ana.crear("/goals", META)
    a = _aportar(ana, m["id"], mode="aprobado")["contribution"]
    assert ana.delete(f"/contributions/{a['id']}").json()["auto_approved_count"] == 1


# --- Listado de aportes y borrado en cascada ------------------------------------
def test_listado_de_aportes_filtra_por_meta_y_ordena_por_fecha(ana):
    m1, m2 = ana.crear("/goals", META), ana.crear("/goals", {**META, "title": "Viaje"})
    _aportar(ana, m1["id"], amount=1, date="2026-09-01")
    _aportar(ana, m1["id"], amount=2, date="2026-09-20")
    _aportar(ana, m2["id"], amount=3, date="2026-09-10")
    todos = ana.get("/contributions").json()
    assert [a["amount"] for a in todos] == [2, 3, 1]  # fecha descendente
    assert [a["amount"] for a in ana.get("/contributions", params={"goal_id": m1["id"]}).json()] == [2, 1]
    assert [a["amount"] for a in ana.get("/contributions", params={"sort": "date"}).json()] == [1, 3, 2]
    assert ana.get("/contributions", params={"goal_id": "x"}).status_code == 422


def test_borrar_una_meta_borra_sus_aportes_y_solo_los_suyos(ana):
    m1, m2 = ana.crear("/goals", META), ana.crear("/goals", {**META, "title": "Viaje"})
    _aportar(ana, m1["id"], amount=1)
    _aportar(ana, m1["id"], amount=2)
    _aportar(ana, m2["id"], amount=3)
    assert ana.delete(f"/goals/{m1['id']}").status_code == 204
    assert [a["amount"] for a in ana.get("/contributions").json()] == [3]


def test_el_nombre_del_aporte_es_una_copia_del_momento(ana):
    m = ana.crear("/goals", META)
    _aportar(ana, m["id"])
    ana.patch(f"/goals/{m['id']}", {"title": "Notebook gamer"})
    assert ana.get("/contributions").json()[0]["goal_title"] == "Notebook"


# --- Atomicidad -----------------------------------------------------------------
def test_si_falla_al_confirmar_no_queda_ni_aporte_ni_monto_a_medias(ana, cliente, monkeypatch):
    """Simula un corte justo al confirmar: la meta y el aporte deben quedar
    exactamente como estaban (en la plataforma anterior eran dos llamadas y podía quedar a medias)."""
    from fastapi.testclient import TestClient

    from app.main import app

    m = ana.crear("/goals", META)
    original = Session.commit
    llamadas = {"n": 0}

    def _commit_que_falla(self):
        llamadas["n"] += 1
        raise RuntimeError("corte simulado")

    monkeypatch.setattr(Session, "commit", _commit_que_falla)
    inseguro = TestClient(app, raise_server_exceptions=False)
    r = inseguro.post(f"/api/v1/goals/{m['id']}/contributions", json=APORTE, headers=ana.headers)
    monkeypatch.setattr(Session, "commit", original)

    assert r.status_code == 500 and llamadas["n"] >= 1
    assert "corte simulado" not in r.text
    assert ana.get(f"/goals/{m['id']}").json() == m
    assert ana.get("/contributions").json() == []


# --- Concurrencia (solo Postgres) -------------------------------------------------
def _en_paralelo(n, funcion):
    resultados: list = []
    barrera = threading.Barrier(n)

    def _ejecutar():
        barrera.wait()
        resultados.append(funcion())

    hilos = [threading.Thread(target=_ejecutar) for _ in range(n)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    return resultados


@pytest.mark.skipif(not USA_POSTGRES, reason="requiere Postgres real (bloqueo de filas)")
def test_diez_aportes_simultaneos_no_pierden_ninguno(cliente):
    u = Usuario(cliente, "paralelo@correo.cl")
    m = u.crear("/goals", META)
    estados = _en_paralelo(10, lambda: u.post(f"/goals/{m['id']}/contributions", {"amount": 1000, "date": "2026-09-29", "mode": "aprobado"}).status_code)
    assert estados == [201] * 10
    meta = u.get(f"/goals/{m['id']}").json()
    assert meta["current_amount"] == 10000 and meta["auto_approved_count"] == 10  # sin pérdidas
    assert len(u.get("/contributions").json()) == 10


@pytest.mark.skipif(not USA_POSTGRES, reason="requiere Postgres real (bloqueo de filas)")
def test_deshacer_el_mismo_aporte_a_la_vez_descuenta_una_sola_vez(cliente):
    u = Usuario(cliente, "paralelo2@correo.cl")
    m = u.crear("/goals", META)
    aporte = u.post(f"/goals/{m['id']}/contributions", {"amount": 1000, "date": "2026-09-29"}).json()["contribution"]
    u.post(f"/goals/{m['id']}/contributions", {"amount": 5000, "date": "2026-09-29"})
    estados = sorted(_en_paralelo(6, lambda: u.delete(f"/contributions/{aporte['id']}").status_code))
    assert estados == [200, 404, 404, 404, 404, 404]
    assert u.get(f"/goals/{m['id']}").json()["current_amount"] == 5000
