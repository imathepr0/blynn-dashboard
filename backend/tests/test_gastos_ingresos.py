"""Pruebas de la API de gastos e ingresos."""
import pytest

from tests.utils import GASTO, INGRESO

# ===================================================================== #
# Gastos
# ===================================================================== #


def test_crear_gasto_aplica_valores_por_defecto(ana):
    g = ana.crear("/expenses", GASTO)
    assert g["payment_method"] == "debito"
    assert g["is_recurring"] is False and g["recurring_active"] is False
    assert g["description"] is None and g["color"] is None
    assert g["amount"] == 3190 and g["date"] == "2026-09-29"
    assert "user_id" not in g


def test_crear_gasto_completo_como_lo_envia_el_formulario(ana):
    g = ana.crear("/expenses", {
        "merchant": "  Netflix  ", "description": "Plan\nfamiliar", "amount": 8990,
        "category": "Suscripciones", "date": "2026-08-05", "payment_method": "credito",
        "color": "#3B82F6", "is_recurring": True, "recurring_active": True,
    })
    assert g["merchant"] == "Netflix" and g["description"] == "Plan\nfamiliar"
    assert g["color"] == "#3b82f6" and g["is_recurring"] and g["recurring_active"]


def test_descripcion_vacia_se_guarda_como_nula(ana):
    assert ana.crear("/expenses", {**GASTO, "description": ""})["description"] is None
    assert ana.crear("/expenses", {**GASTO, "description": "   "})["description"] is None
    assert ana.crear("/expenses", {**GASTO, "color": ""})["color"] is None


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("amount", 0), ("amount", -5), ("amount", 12.5), ("amount", "3190"), ("amount", True), ("amount", None),
        ("amount", 10**12 + 1), ("amount", 2**63),
        ("merchant", ""), ("merchant", "x" * 256), ("merchant", "a\x00b"), ("merchant", "a\x07b"), ("merchant", 5),
        ("category", ""), ("category", "x" * 101),
        ("description", "x" * 5001),
        ("date", "no-es-fecha"), ("date", "2026-13-40"), ("date", "1999-12-31"), ("date", "2101-01-01"), ("date", 20260929), ("date", None),
        ("payment_method", "bitcoin"), ("payment_method", ""), ("payment_method", None),
        ("color", "rojo"), ("color", "#12"),
        ("is_recurring", "true"), ("is_recurring", 1), ("is_recurring", None),
    ],
)
def test_crear_gasto_con_datos_invalidos_es_422(ana, campo, valor):
    r = ana.post("/expenses", {**GASTO, campo: valor})
    assert r.status_code == 422, (campo, valor, r.text)
    assert ana.get("/expenses").json() == []


@pytest.mark.parametrize("faltante", ["merchant", "amount", "category", "date"])
def test_crear_gasto_sin_campo_obligatorio_es_422(ana, faltante):
    datos = {k: v for k, v in GASTO.items() if k != faltante}
    assert ana.post("/expenses", datos).status_code == 422


def test_gasto_recurrente_activo_requiere_ser_recurrente(ana):
    r = ana.post("/expenses", {**GASTO, "is_recurring": False, "recurring_active": True})
    assert r.status_code == 422
    assert ana.post("/expenses", {**GASTO, "is_recurring": True, "recurring_active": True}).status_code == 201


def test_patch_no_puede_dejar_un_gasto_recurrente_activo_sin_ser_recurrente(ana):
    g = ana.crear("/expenses", GASTO)
    r = ana.patch(f"/expenses/{g['id']}", {"recurring_active": True})
    assert r.status_code == 422
    assert ana.get(f"/expenses/{g['id']}").json() == g  # nada cambió


def test_patch_parcial_solo_cambia_lo_enviado(ana):
    g = ana.crear("/expenses", {**GASTO, "description": "detalle", "color": "#3b82f6"})
    r = ana.patch(f"/expenses/{g['id']}", {"amount": 9999})
    nuevo = r.json()
    assert r.status_code == 200 and nuevo["amount"] == 9999
    assert {k: v for k, v in nuevo.items() if k not in ("amount", "updated_date")} == {
        k: v for k, v in g.items() if k not in ("amount", "updated_date")
    }


def test_patch_puede_borrar_campos_opcionales_pero_no_los_obligatorios(ana):
    g = ana.crear("/expenses", {**GASTO, "description": "detalle", "color": "#3b82f6"})
    r = ana.patch(f"/expenses/{g['id']}", {"description": None, "color": None})
    assert r.status_code == 200 and r.json()["description"] is None and r.json()["color"] is None
    for campo in ("merchant", "amount", "category", "date", "payment_method", "is_recurring"):
        assert ana.patch(f"/expenses/{g['id']}", {campo: None}).status_code == 422, campo


def test_patch_valida_igual_que_crear(ana):
    g = ana.crear("/expenses", GASTO)
    for campo, valor in [("amount", -1), ("amount", 1.5), ("date", "1999-01-01"), ("payment_method", "x"), ("merchant", "x" * 300)]:
        assert ana.patch(f"/expenses/{g['id']}", {campo: valor}).status_code == 422, campo
    assert ana.get(f"/expenses/{g['id']}").json() == g


def test_actualizar_avanza_updated_date(ana):
    g = ana.crear("/expenses", GASTO)
    n = ana.patch(f"/expenses/{g['id']}", {"amount": 1}).json()
    assert n["updated_date"] >= g["updated_date"] and n["created_date"] == g["created_date"]


def test_borrar_gasto(ana):
    g = ana.crear("/expenses", GASTO)
    assert ana.delete(f"/expenses/{g['id']}").status_code == 204
    assert ana.delete(f"/expenses/{g['id']}").status_code == 404
    assert ana.get("/expenses").json() == []


# --- Listado ------------------------------------------------------------
@pytest.fixture
def gastos_variados(ana):
    datos = [
        ("Líder", 5000, "Alimentación", "2026-09-10"),
        ("Copec", 30000, "Transporte", "2026-09-20"),
        ("Netflix", 8990, "Suscripciones", "2026-08-05"),
        ("Jumbo", 15000, "Alimentación", "2026-09-25"),
    ]
    for merchant, amount, cat, fecha in datos:
        ana.crear("/expenses", {**GASTO, "merchant": merchant, "amount": amount, "category": cat, "date": fecha})
    return ana


def test_listado_ordena_por_fecha_descendente_por_defecto(gastos_variados):
    fechas = [g["date"] for g in gastos_variados.get("/expenses").json()]
    assert fechas == sorted(fechas, reverse=True)


def test_listado_otros_ordenes(gastos_variados):
    montos = [g["amount"] for g in gastos_variados.get("/expenses", params={"sort": "amount"}).json()]
    assert montos == sorted(montos)
    montos = [g["amount"] for g in gastos_variados.get("/expenses", params={"sort": "-amount"}).json()]
    assert montos == sorted(montos, reverse=True)


def test_listado_filtra_por_rango_de_fechas(gastos_variados):
    r = gastos_variados.get("/expenses", params={"date_from": "2026-09-01", "date_to": "2026-09-20"}).json()
    assert sorted(g["merchant"] for g in r) == ["Copec", "Líder"]
    r = gastos_variados.get("/expenses", params={"date_from": "2026-09-25"}).json()
    assert [g["merchant"] for g in r] == ["Jumbo"]


def test_listado_filtra_por_categoria_y_recurrencia(gastos_variados):
    ana = gastos_variados
    assert len(ana.get("/expenses", params={"category": "Alimentación"}).json()) == 2
    assert ana.get("/expenses", params={"category": "Inexistente"}).json() == []
    ana.crear("/expenses", {**GASTO, "merchant": "Gym", "is_recurring": True, "recurring_active": True})
    assert [g["merchant"] for g in ana.get("/expenses", params={"is_recurring": "true", "recurring_active": "true"}).json()] == ["Gym"]
    assert len(ana.get("/expenses", params={"is_recurring": "false"}).json()) == 4


def test_filtros_con_valores_invalidos_son_422(ana):
    for params in ({"date_from": "ayer"}, {"is_recurring": "quizás"}, {"category": "x" * 101}, {"sort": "user_id"}):
        assert ana.get("/expenses", params=params).status_code == 422, params


def test_paginacion_no_repite_ni_salta_gastos_con_la_misma_fecha(ana):
    creados = {ana.crear("/expenses", {**GASTO, "merchant": f"Tienda {i}"})["id"] for i in range(25)}
    vistos = []
    for offset in (0, 10, 20):
        pagina = ana.get("/expenses", params={"limit": 10, "offset": offset}).json()
        vistos += [g["id"] for g in pagina]
    assert len(vistos) == 25 and set(vistos) == creados


# --- Lote (cobros recurrentes) -----------------------------------------------
def test_crear_en_lote(ana):
    lote = [{**GASTO, "merchant": f"Cobro {i}"} for i in range(3)]
    r = ana.post("/expenses/bulk", {"items": lote})
    assert r.status_code == 201 and len(r.json()) == 3
    assert len(ana.get("/expenses").json()) == 3


def test_el_lote_es_todo_o_nada(ana):
    lote = [GASTO, {**GASTO, "amount": -1}, GASTO]
    assert ana.post("/expenses/bulk", {"items": lote}).status_code == 422
    assert ana.get("/expenses").json() == []


def test_limites_del_lote(ana):
    assert ana.post("/expenses/bulk", {"items": []}).status_code == 422
    assert ana.post("/expenses/bulk", {"items": [GASTO] * 51}).status_code == 422
    assert ana.post("/expenses/bulk", {"items": [GASTO] * 50}).status_code == 201
    assert ana.post("/expenses/bulk", {"items": [{**GASTO, "user_id": "x"}]}).status_code == 422


# ===================================================================== #
# Ingresos
# ===================================================================== #
def test_crear_ingreso_con_valores_por_defecto(ana):
    i = ana.crear("/incomes", {"source": "Tío", "amount": 20000, "date": "2026-09-05"})
    assert i["type"] == "otros" and i["description"] is None and i["color"] is None


def test_crud_de_ingresos(ana):
    i = ana.crear("/incomes", INGRESO)
    assert ana.get(f"/incomes/{i['id']}").json() == i
    r = ana.patch(f"/incomes/{i['id']}", {"amount": 900000, "type": "bono"})
    assert r.json()["amount"] == 900000 and r.json()["type"] == "bono" and r.json()["source"] == "Empresa SpA"
    assert ana.delete(f"/incomes/{i['id']}").status_code == 204
    assert ana.get(f"/incomes/{i['id']}").status_code == 404


@pytest.mark.parametrize(
    "campo, valor",
    [
        ("amount", 0), ("amount", -1), ("amount", 1.5), ("amount", "5"), ("amount", False),
        ("source", ""), ("source", "x" * 256), ("type", "loteria"), ("type", ""), ("type", None),
        ("date", "2026-02-30"), ("date", "1990-01-01"), ("color", "verde"),
    ],
)
def test_crear_ingreso_con_datos_invalidos_es_422(ana, campo, valor):
    assert ana.post("/incomes", {**INGRESO, campo: valor}).status_code == 422
    assert ana.get("/incomes").json() == []


def test_patch_ingreso_no_acepta_nulos_en_obligatorios(ana):
    i = ana.crear("/incomes", INGRESO)
    for campo in ("source", "amount", "date", "type"):
        assert ana.patch(f"/incomes/{i['id']}", {campo: None}).status_code == 422
    assert ana.patch(f"/incomes/{i['id']}", {"description": None, "color": None}).status_code == 200


def test_listado_de_ingresos_filtros_y_orden(ana):
    for fuente, monto, fecha, tipo in [("A", 100, "2026-07-01", "sueldo"), ("B", 300, "2026-09-01", "bono"), ("C", 200, "2026-08-01", "sueldo")]:
        ana.crear("/incomes", {"source": fuente, "amount": monto, "date": fecha, "type": tipo})
    assert [i["source"] for i in ana.get("/incomes").json()] == ["B", "C", "A"]
    assert [i["source"] for i in ana.get("/incomes", params={"sort": "amount"}).json()] == ["A", "C", "B"]
    assert sorted(i["source"] for i in ana.get("/incomes", params={"type": "sueldo"}).json()) == ["A", "C"]
    assert [i["source"] for i in ana.get("/incomes", params={"date_from": "2026-08-15"}).json()] == ["B"]
    assert ana.get("/incomes", params={"type": "otro"}).status_code == 422
