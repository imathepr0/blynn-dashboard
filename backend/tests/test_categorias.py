"""Pruebas de la API de categorías."""
import threading

import pytest

from app.services.categorias import CATEGORIAS_POR_DEFECTO
from tests.conftest import USA_POSTGRES
from tests.utils import CATEGORIA, GASTO, Usuario


def test_crear_listar_obtener_actualizar_borrar(ana):
    c = ana.crear("/categories", {**CATEGORIA, "icon": "Dog", "budget": 50000})
    assert c["name"] == "Mascotas" and c["budget"] == 50000 and c["icon"] == "Dog"
    assert "user_id" not in c  # salida en lista blanca

    assert ana.get("/categories").json() == [c]
    assert ana.get(f"/categories/{c['id']}").json() == c

    r = ana.patch(f"/categories/{c['id']}", {"budget": 70000})
    assert r.status_code == 200 and r.json()["budget"] == 70000 and r.json()["name"] == "Mascotas"

    assert ana.delete(f"/categories/{c['id']}").status_code == 204
    assert ana.get(f"/categories/{c['id']}").status_code == 404


def test_valores_por_defecto_al_crear(ana):
    c = ana.crear("/categories", CATEGORIA)
    assert c["budget"] == 0 and c["icon"] is None


def test_el_nombre_se_limpia_de_espacios(ana):
    assert ana.crear("/categories", {**CATEGORIA, "name": "  Mascotas  "})["name"] == "Mascotas"


def test_color_se_normaliza_a_minusculas(ana):
    assert ana.crear("/categories", {**CATEGORIA, "color": "#3B82F6"})["color"] == "#3b82f6"


# --- Nombre único por usuario -------------------------------------------
def test_nombre_repetido_sin_distinguir_mayusculas_es_409(ana):
    ana.crear("/categories", {**CATEGORIA, "name": "Hogar"})
    r = ana.post("/categories", {**CATEGORIA, "name": "hogar"})
    assert r.status_code == 409 and "Ya existe" in r.json()["detail"]
    assert len(ana.get("/categories").json()) == 1


@pytest.mark.skipif(not USA_POSTGRES, reason="SQLite solo pliega mayúsculas ASCII")
def test_unicidad_sin_distinguir_mayusculas_tambien_con_tildes_y_enes(ana):
    ana.crear("/categories", {**CATEGORIA, "name": "Alimentación"})
    assert ana.post("/categories", {**CATEGORIA, "name": "ALIMENTACIÓN"}).status_code == 409
    ana.crear("/categories", {**CATEGORIA, "name": "Ñandú"})
    assert ana.post("/categories", {**CATEGORIA, "name": "ñandú"}).status_code == 409


def test_otro_usuario_si_puede_usar_el_mismo_nombre(ana, beto):
    ana.crear("/categories", CATEGORIA)
    assert beto.post("/categories", CATEGORIA).status_code == 201


def test_renombrar_a_un_nombre_existente_es_409_y_no_cambia_nada(ana):
    ana.crear("/categories", {**CATEGORIA, "name": "Hogar"})
    otra = ana.crear("/categories", {**CATEGORIA, "name": "Mascotas"})
    r = ana.patch(f"/categories/{otra['id']}", {"name": "HOGAR"})
    assert r.status_code == 409
    assert ana.get(f"/categories/{otra['id']}").json()["name"] == "Mascotas"


def test_cambiar_solo_mayusculas_de_la_propia_categoria_es_valido(ana):
    c = ana.crear("/categories", {**CATEGORIA, "name": "mascotas"})
    assert ana.patch(f"/categories/{c['id']}", {"name": "Mascotas"}).json()["name"] == "Mascotas"


# --- Renombrar mantiene los gastos ligados --------------------------------
def test_renombrar_actualiza_los_gastos_de_esa_categoria(ana):
    c = ana.crear("/categories", {**CATEGORIA, "name": "Comida"})
    ana.crear("/expenses", {**GASTO, "category": "Comida"})
    ana.crear("/expenses", {**GASTO, "category": "Comida", "merchant": "Otro"})
    ana.crear("/expenses", {**GASTO, "category": "Transporte"})

    ana.patch(f"/categories/{c['id']}", {"name": "Alimentos"})

    por_categoria = sorted(g["category"] for g in ana.get("/expenses").json())
    assert por_categoria == ["Alimentos", "Alimentos", "Transporte"]


def test_renombrar_no_toca_los_gastos_de_otros_usuarios(ana, beto):
    c = ana.crear("/categories", {**CATEGORIA, "name": "Comida"})
    gasto_de_beto = beto.crear("/expenses", {**GASTO, "category": "Comida"})
    ana.patch(f"/categories/{c['id']}", {"name": "Alimentos"})
    assert beto.get(f"/expenses/{gasto_de_beto['id']}").json()["category"] == "Comida"


def test_cambiar_otro_campo_no_toca_los_gastos(ana):
    c = ana.crear("/categories", {**CATEGORIA, "name": "Comida"})
    g = ana.crear("/expenses", {**GASTO, "category": "Comida"})
    ana.patch(f"/categories/{c['id']}", {"budget": 1000})
    assert ana.get(f"/expenses/{g['id']}").json()["category"] == "Comida"


def test_borrar_una_categoria_conserva_sus_gastos(ana):
    c = ana.crear("/categories", {**CATEGORIA, "name": "Comida"})
    g = ana.crear("/expenses", {**GASTO, "category": "Comida"})
    ana.delete(f"/categories/{c['id']}")
    assert ana.get(f"/expenses/{g['id']}").status_code == 200


# --- Categorías por defecto -----------------------------------------------
def test_crear_por_defecto_deja_las_12(ana):
    r = ana.post("/categories/defaults")
    assert r.status_code == 200
    assert sorted(c["name"] for c in r.json()) == sorted(c["name"] for c in CATEGORIAS_POR_DEFECTO)
    assert len(r.json()) == 12


def test_crear_por_defecto_es_idempotente(ana):
    for _ in range(4):
        assert len(ana.post("/categories/defaults").json()) == 12
    assert len(ana.get("/categories").json()) == 12


def test_por_defecto_respeta_las_que_el_usuario_ya_tiene_sin_distinguir_mayusculas(ana):
    propia = ana.crear("/categories", {"name": "hogar", "color": "#000000", "budget": 999})
    r = ana.post("/categories/defaults")
    assert len(r.json()) == 12
    hogares = [c for c in r.json() if c["name"].lower() == "hogar"]
    assert len(hogares) == 1 and hogares[0]["id"] == propia["id"] and hogares[0]["budget"] == 999


def test_por_defecto_no_afecta_a_otros_usuarios(ana, beto):
    ana.post("/categories/defaults")
    assert beto.get("/categories").json() == []


@pytest.mark.skipif(not USA_POSTGRES, reason="requiere Postgres real (carrera entre conexiones)")
def test_crear_por_defecto_desde_varias_pestanas_a_la_vez(cliente):
    usuario = Usuario(cliente, "carrera@correo.cl")
    estados: list[int] = []
    barrera = threading.Barrier(6)

    def _llamar():
        barrera.wait()
        estados.append(usuario.post("/categories/defaults").status_code)

    hilos = [threading.Thread(target=_llamar) for _ in range(6)]
    [h.start() for h in hilos]
    [h.join() for h in hilos]

    assert estados == [200] * 6  # ninguna falla, ninguna da 500
    assert len(usuario.get("/categories").json()) == 12  # y no hay duplicados


# --- Validación -----------------------------------------------------------
@pytest.mark.parametrize(
    "campo, valor",
    [
        ("name", ""), ("name", "   "), ("name", "x" * 101), ("name", "malo\x00nombre"), ("name", 123),
        ("color", "red"), ("color", "#fff"), ("color", "#12345g"), ("color", "javascript:alert(1)"),
        ("color", "#3b82f6; background:url(x)"), ("color", ""),
        ("icon", "../etc"), ("icon", "Icon Name"), ("icon", "x" * 51),
        ("budget", -1), ("budget", 1.5), ("budget", "1000"), ("budget", True), ("budget", 10**12 + 1),
    ],
)
def test_crear_con_datos_invalidos_es_422(ana, campo, valor):
    r = ana.post("/categories", {**CATEGORIA, campo: valor})
    assert r.status_code == 422, (campo, valor, r.text)
    assert ana.get("/categories").json() == []


def test_faltan_campos_obligatorios(ana):
    assert ana.post("/categories", {"name": "Solo nombre"}).status_code == 422
    assert ana.post("/categories", {"color": "#3b82f6"}).status_code == 422
    assert ana.post("/categories", {}).status_code == 422


def test_patch_no_acepta_nulo_en_campos_obligatorios_pero_si_borra_icono(ana):
    c = ana.crear("/categories", {**CATEGORIA, "icon": "Dog"})
    for campo in ("name", "color", "budget"):
        assert ana.patch(f"/categories/{c['id']}", {campo: None}).status_code == 422
    r = ana.patch(f"/categories/{c['id']}", {"icon": None})
    assert r.status_code == 200 and r.json()["icon"] is None


def test_patch_vacio_no_cambia_nada(ana):
    c = ana.crear("/categories", CATEGORIA)
    r = ana.patch(f"/categories/{c['id']}", {})
    assert r.status_code == 200 and r.json() == c


# --- Orden y paginación -----------------------------------------------------
def test_orden_y_paginacion(ana):
    for n in ("Carne", "Auto", "Banco"):
        ana.crear("/categories", {**CATEGORIA, "name": n})
    assert [c["name"] for c in ana.get("/categories", params={"sort": "name"}).json()] == ["Auto", "Banco", "Carne"]
    assert [c["name"] for c in ana.get("/categories", params={"sort": "-name"}).json()] == ["Carne", "Banco", "Auto"]
    pagina = ana.get("/categories", params={"sort": "name", "limit": 2, "offset": 1}).json()
    assert [c["name"] for c in pagina] == ["Banco", "Carne"]


@pytest.mark.parametrize(
    "params",
    [{"sort": "password"}, {"sort": "user_id"}, {"sort": "-id;drop table users"}, {"limit": 0}, {"limit": 1001}, {"offset": -1}, {"limit": "x"}],
)
def test_parametros_de_listado_invalidos_son_422(ana, params):
    assert ana.get("/categories", params=params).status_code == 422


def test_respuesta_de_error_de_orden_no_expone_detalles_internos(ana):
    r = ana.get("/categories", params={"sort": "password_hash"})
    assert r.status_code == 422 and "password" not in r.text.lower().replace("'password_hash'", "")
