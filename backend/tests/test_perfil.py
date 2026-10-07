"""Pruebas del perfil (`updateMe`) y del reinicio de cuenta."""
import pytest
from sqlalchemy import select, update

from app.db.models import User
from tests.utils import CATEGORIA, GASTO, INGRESO, META

TOTAL_POR_DEFECTO = 12


def test_get_me_es_igual_a_auth_me(ana):
    assert ana.get("/me").json() == ana.get("/auth/me").json()
    assert ana.get("/me").json()["email"] == "ana@correo.cl"


def test_patch_me_actualiza_los_campos_que_usa_la_app(ana):
    r = ana.patch("/me", {
        "full_name": "  Ana Pérez ", "onboarded": True,
        "monthly_budget": 700000, "preferences": {"notifications": False},
    })
    assert r.status_code == 200
    u = r.json()
    assert u["full_name"] == "Ana Pérez"
    assert u["onboarded"] is True and u["monthly_budget"] == 700000
    assert u["preferences"] == {"notifications": False}
    assert ana.get("/me").json() == u  # quedó guardado


def test_valores_vacios_del_formulario_se_guardan_como_nulos(ana):
    """Ajustes envía "" cuando el nombre está vacío."""
    ana.patch("/me", {"full_name": "Ana"})
    assert ana.patch("/me", {"full_name": ""}).json()["full_name"] is None


def test_la_foto_de_perfil_ya_no_existe_en_la_api(ana):
    """Decisión de producto: no hay foto de perfil, todos usan el mismo avatar."""
    assert "photo_url" not in ana.get("/me").json()
    assert "photo_url" not in ana.get("/auth/me").json()
    antes = ana.get("/me").json()
    for valor in ("https://cdn.ejemplo.cl/ana.png", "", None):
        assert ana.patch("/me", {"photo_url": valor}).status_code == 422
    assert ana.get("/me").json() == antes


def test_patch_solo_cambia_lo_enviado(ana):
    ana.patch("/me", {"full_name": "Ana", "monthly_budget": 500})
    u = ana.patch("/me", {"onboarded": True}).json()
    assert u["full_name"] == "Ana" and u["monthly_budget"] == 500 and u["onboarded"] is True


def test_las_preferencias_se_combinan_no_se_pisan(ana, db):
    db.execute(update(User).where(User.email == "ana@correo.cl").values(preferences={"otra_clave": 1}))
    db.commit()
    u = ana.patch("/me", {"preferences": {"notifications": True}}).json()
    assert u["preferences"] == {"otra_clave": 1, "notifications": True}


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("email", "otro@correo.cl"), ("role", "admin"), ("is_active", False), ("id", "x"), ("password", "Nueva-Clave-123"),
        ("password_hash", "x"), ("created_date", "2020-01-01T00:00:00Z"), ("last_login_date", "2020-01-01T00:00:00Z"),
        ("refresh_tokens", []),
    ],
)
def test_los_campos_protegidos_no_se_pueden_cambiar(ana, db, campo, valor):
    antes = ana.get("/me").json()
    assert ana.patch("/me", {campo: valor}).status_code == 422
    assert ana.get("/me").json() == antes
    fila = db.scalar(select(User).where(User.email == "ana@correo.cl"))
    assert fila.role == "user" and fila.is_active is True


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("full_name", "x" * 121), ("full_name", "a\x00b"),
        ("monthly_budget", -1), ("monthly_budget", 1.5), ("monthly_budget", "700000"), ("monthly_budget", True),
        ("monthly_budget", 10**12 + 1),
        ("onboarded", "true"), ("onboarded", 1), ("onboarded", None), ("monthly_budget", None), ("preferences", None),
        ("preferences", {"notifications": "yes"}), ("preferences", {"notifications": 1}),
        ("preferences", {"clave_nueva": True}), ("preferences", {"notifications": True, "x": {"a": "b" * 10000}}),
        ("preferences", "texto"),
    ],
)
def test_patch_me_con_datos_invalidos_es_422(ana, campo, valor):
    antes = ana.get("/me").json()
    assert ana.patch("/me", {campo: valor}).status_code == 422, (campo, valor)
    assert ana.get("/me").json() == antes


def test_el_nombre_puede_borrarse_con_null(ana):
    ana.patch("/me", {"full_name": "Ana"})
    assert ana.patch("/me", {"full_name": None}).json()["full_name"] is None


def test_un_usuario_no_afecta_el_perfil_de_otro(ana, beto):
    ana.patch("/me", {"full_name": "Ana", "monthly_budget": 999})
    assert beto.get("/me").json()["full_name"] is None and beto.get("/me").json()["monthly_budget"] == 0


# --- Reinicio de cuenta ------------------------------------------------------------
def _llenar(u):
    u.crear("/categories", CATEGORIA)
    u.crear("/expenses", GASTO)
    u.crear("/incomes", INGRESO)
    meta = u.crear("/goals", META)
    u.post(f"/goals/{meta['id']}/contributions", {"amount": 1000, "date": "2026-09-29"})
    u.patch("/me", {"onboarded": True, "monthly_budget": 700000, "full_name": "Con Nombre", "preferences": {"notifications": False}})


@pytest.mark.parametrize("cuerpo", [{}, {"confirm": False}, {"confirm": 1}, {"confirm": "true"}, {"confirm": "yes"}, {"confirm": None}, {"confirm": True, "extra": 1}])
def test_el_reinicio_exige_confirmacion_exacta(ana, cuerpo):
    _llenar(ana)
    assert ana.post("/me/reset", cuerpo).status_code == 422
    assert len(ana.get("/expenses").json()) == 1  # no se borró nada


def test_el_reinicio_sin_cuerpo_es_422(ana):
    assert ana.cliente.post("/api/v1/me/reset", headers=ana.headers).status_code == 422


def test_reiniciar_deja_la_cuenta_como_nueva_y_conserva_lo_esencial(ana):
    _llenar(ana)
    r = ana.post("/me/reset", {"confirm": True})
    assert r.status_code == 200
    u = r.json()
    assert u["onboarded"] is False and u["monthly_budget"] == 0
    assert u["email"] == "ana@correo.cl" and u["full_name"] == "Con Nombre"
    assert u["preferences"] == {"notifications": False}
    assert ana.get("/expenses").json() == [] and ana.get("/incomes").json() == []
    assert ana.get("/goals").json() == [] and ana.get("/contributions").json() == []
    categorias = ana.get("/categories").json()
    assert len(categorias) == TOTAL_POR_DEFECTO
    assert "Mascotas" not in [c["name"] for c in categorias]  # la personalizada se fue


def test_reiniciar_no_toca_a_otros_usuarios(ana, beto):
    _llenar(ana)
    _llenar(beto)
    ana.post("/me/reset", {"confirm": True})
    assert len(beto.get("/expenses").json()) == 1 and len(beto.get("/incomes").json()) == 1
    assert len(beto.get("/goals").json()) == 1 and len(beto.get("/contributions").json()) == 1
    assert "Mascotas" in [c["name"] for c in beto.get("/categories").json()]
    assert beto.get("/me").json()["monthly_budget"] == 700000


def test_despues_de_reiniciar_la_cuenta_sigue_funcionando(ana, cliente):
    _llenar(ana)
    ana.post("/me/reset", {"confirm": True})
    r = cliente.post("/api/v1/auth/login", json={"email": "ana@correo.cl", "password": "Tr3s-Tristes-Tigres"})
    assert r.status_code == 200
    assert ana.post("/expenses", GASTO).status_code == 201
    assert ana.post("/categories/defaults").json().__len__() == TOTAL_POR_DEFECTO  # idempotente tras reiniciar


def test_reiniciar_dos_veces_es_seguro(ana):
    _llenar(ana)
    assert ana.post("/me/reset", {"confirm": True}).status_code == 200
    assert ana.post("/me/reset", {"confirm": True}).status_code == 200
    assert len(ana.get("/categories").json()) == TOTAL_POR_DEFECTO


def test_si_el_reinicio_falla_a_mitad_no_se_pierde_nada(ana, monkeypatch):
    """Todo el reinicio es UNA transacción: un fallo al recrear las
    categorías no puede dejar los gastos ya borrados."""
    from fastapi.testclient import TestClient

    import app.services.datos_usuario as modulo
    from app.main import app

    _llenar(ana)
    antes = {r: ana.get(r).json() for r in ("/expenses", "/incomes", "/goals", "/contributions", "/categories", "/me")}

    def _falla(*a, **k):
        raise RuntimeError("fallo simulado al recrear categorías")

    monkeypatch.setattr(modulo, "agregar_categorias_faltantes", _falla)
    inseguro = TestClient(app, raise_server_exceptions=False)
    r = inseguro.post("/api/v1/me/reset", json={"confirm": True}, headers=ana.headers)
    monkeypatch.undo()

    assert r.status_code == 500 and "simulado" not in r.text
    despues = {k: ana.get(k).json() for k in antes}
    assert despues == antes
