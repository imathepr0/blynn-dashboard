"""Pruebas de los modelos (Etapa 1): valores por defecto, restricciones,
aislamiento entre usuarios y borrados en cascada. Corren en SQLite por
defecto y en Postgres real si se define TEST_DATABASE_URL."""
import datetime as dt
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.db.models import (
    Category,
    Contribution,
    Expense,
    Goal,
    Income,
    RefreshToken,
    User,
)

HOY = dt.date(2026, 9, 29)


def _usuario(email="ana@correo.cl") -> User:
    return User(email=email, password_hash="$2b$04$hashdeprueba")


@pytest.fixture
def ana(db) -> User:
    u = _usuario()
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def beto(db) -> User:
    u = _usuario("beto@correo.cl")
    db.add(u)
    db.commit()
    return u


def test_usuario_valores_por_defecto(db, ana):
    db.expire_all()
    u = db.get(User, ana.id)
    assert isinstance(u.id, uuid.UUID)
    assert (u.role, u.is_active, u.onboarded, u.monthly_budget) == ("user", True, False, 0)
    assert u.preferences == {}
    assert u.created_date.tzinfo is not None  # siempre con zona horaria
    assert u.last_login_date is None


def test_preferencias_json_se_guardan_y_leen(db, ana):
    ana.preferences = {"notifications": {"budget_alerts": True}}
    db.commit()
    db.expire_all()
    assert db.get(User, ana.id).preferences == {"notifications": {"budget_alerts": True}}


def test_email_debe_ser_unico(db, ana):
    db.add(_usuario("ana@correo.cl"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_la_base_de_datos_rechaza_email_con_mayusculas(db):
    db.add(_usuario("Ana@Correo.cl"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_rol_invalido_se_rechaza(db):
    u = _usuario()
    u.role = "superadmin"
    db.add(u)
    with pytest.raises(IntegrityError):
        db.commit()


def test_presupuesto_mensual_negativo_se_rechaza(db):
    u = _usuario()
    u.monthly_budget = -1
    db.add(u)
    with pytest.raises(IntegrityError):
        db.commit()


def test_categoria_nombre_unico_por_usuario_sin_distinguir_mayusculas(db, ana, beto):
    db.add(Category(user_id=ana.id, name="Alimentación", color="#3b82f6"))
    db.commit()

    db.add(Category(user_id=ana.id, name="ALIMENTACIÓN".replace("Ó", "ó"), color="#000000"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    # Otro usuario SÍ puede tener una categoría con ese nombre.
    db.add(Category(user_id=beto.id, name="Alimentación", color="#3b82f6"))
    db.commit()


def test_categoria_presupuesto_negativo_se_rechaza(db, ana):
    db.add(Category(user_id=ana.id, name="Hogar", color="#fb923c", budget=-5))
    with pytest.raises(IntegrityError):
        db.commit()


def test_gasto_completo_y_montos_grandes(db, ana):
    db.add(
        Expense(
            user_id=ana.id, merchant="Líder", amount=9_876_543_210, category="Alimentación",
            date=HOY, description="Pan 1200\nLeche 1990",
        )
    )
    db.commit()
    g = db.scalar(select(Expense))
    assert g.amount == 9_876_543_210  # BigInteger: sin pérdida de precisión
    assert g.date == HOY
    assert g.payment_method == "debito"
    assert (g.is_recurring, g.recurring_active) == (False, False)


def test_gasto_metodo_de_pago_invalido_o_monto_negativo(db, ana):
    db.add(Expense(user_id=ana.id, merchant="X", amount=1, category="Otros", date=HOY,
                   payment_method="bitcoin"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(Expense(user_id=ana.id, merchant="X", amount=-1, category="Otros", date=HOY))
    with pytest.raises(IntegrityError):
        db.commit()


def test_ingreso_tipo_por_defecto_y_validacion(db, ana):
    db.add(Income(user_id=ana.id, source="Empresa", amount=850_000, date=HOY))
    db.commit()
    assert db.scalar(select(Income)).type == "otros"
    db.add(Income(user_id=ana.id, source="Y", amount=1, date=HOY, type="loteria"))
    with pytest.raises(IntegrityError):
        db.commit()


def test_meta_valores_por_defecto(db, ana):
    db.add(Goal(user_id=ana.id, title="Notebook", target_amount=600_000))
    db.commit()
    m = db.scalar(select(Goal))
    assert (m.current_amount, m.contribution_mode, m.contribution_frequency) == (0, "manual", "meses")
    assert m.color == "#22c55e" and m.auto_approved_count == 0


def test_un_aporte_no_puede_colgar_de_la_meta_de_otro_usuario(db, ana, beto):
    """La clave foránea compuesta (goal_id, user_id) lo impide en la
    propia base de datos, aunque un endpoint tuviera un descuido."""
    meta_de_ana = Goal(user_id=ana.id, title="Viaje", target_amount=1_000_000)
    db.add(meta_de_ana)
    db.commit()

    db.add(Contribution(user_id=beto.id, goal_id=meta_de_ana.id, amount=1000, date=HOY))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()

    db.add(Contribution(user_id=ana.id, goal_id=meta_de_ana.id, amount=1000, date=HOY))
    db.commit()  # el dueño sí puede


def test_aporte_a_meta_inexistente_se_rechaza(db, ana):
    db.add(Contribution(user_id=ana.id, goal_id=uuid.uuid4(), amount=1, date=HOY))
    with pytest.raises(IntegrityError):
        db.commit()


def test_borrar_una_meta_borra_sus_aportes(db, ana):
    meta = Goal(user_id=ana.id, title="Auto", target_amount=5_000_000)
    db.add(meta)
    db.commit()
    db.add_all([Contribution(user_id=ana.id, goal_id=meta.id, amount=10_000, date=HOY) for _ in range(3)])
    db.commit()
    assert len(db.scalars(select(Contribution)).all()) == 3

    db.delete(meta)
    db.commit()
    assert db.scalars(select(Contribution)).all() == []


def test_borrar_un_usuario_borra_todos_sus_datos_y_solo_los_suyos(db, ana, beto):
    for u in (ana, beto):
        meta = Goal(user_id=u.id, title="Meta", target_amount=1000)
        db.add_all([
            meta,
            Category(user_id=u.id, name="Hogar", color="#000000"),
            Expense(user_id=u.id, merchant="X", amount=1, category="Hogar", date=HOY),
            Income(user_id=u.id, source="Y", amount=1, date=HOY),
            RefreshToken(user_id=u.id, family_id=uuid.uuid4(), token_hash=uuid.uuid4().hex * 2,
                         expires_at=dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc)),
        ])
        db.commit()
        db.add(Contribution(user_id=u.id, goal_id=meta.id, amount=1, date=HOY))
        db.commit()

    db.delete(db.get(User, ana.id))
    db.commit()

    for modelo in (Category, Expense, Income, Goal, Contribution, RefreshToken):
        filas = db.scalars(select(modelo)).all()
        assert len(filas) == 1, modelo.__name__
        assert filas[0].user_id == beto.id


def test_refresh_token_hash_unico(db, ana):
    exp = dt.datetime(2030, 1, 1, tzinfo=dt.timezone.utc)
    db.add(RefreshToken(user_id=ana.id, family_id=uuid.uuid4(), token_hash="a" * 64, expires_at=exp))
    db.commit()
    db.add(RefreshToken(user_id=ana.id, family_id=uuid.uuid4(), token_hash="a" * 64, expires_at=exp))
    with pytest.raises(IntegrityError):
        db.commit()


def test_fecha_sin_zona_horaria_se_rechaza(db, ana):
    db.add(RefreshToken(user_id=ana.id, family_id=uuid.uuid4(), token_hash="b" * 64,
                        expires_at=dt.datetime(2030, 1, 1)))  # ingenua
    with pytest.raises(Exception, match="zona horaria"):
        db.commit()
