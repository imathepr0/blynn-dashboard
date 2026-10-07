"""Etapa 1: usuarios, categorías, gastos, ingresos, metas y aportes.

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

TABLAS = ("users", "categories", "expenses", "incomes", "goals", "contributions")


def _fecha_hora() -> sa.DateTime:
    return sa.DateTime(timezone=True)


def _endurecer_para_supabase(tabla: str) -> None:
    """Cierra la tabla al "Data API" público de Supabase.

    Supabase expone por HTTP (PostgREST) las tablas del esquema `public`
    a quien tenga la clave pública `anon`. Este backend NO usa ese
    acceso (se conecta directo a Postgres), así que dejamos las tablas
    cerradas de dos formas independientes:

    1. Row Level Security activado y SIN políticas => los roles públicos
       no pueden leer ni escribir nada.
    2. Se quitan los permisos a los roles `anon` y `authenticated` (solo
       si existen, o sea, solo en Supabase).

    El rol con el que se conecta el backend (dueño de las tablas) no se
    ve afectado por RLS. Solo aplica en Postgres; SQLite lo ignora.
    """
    if op.get_bind().dialect.name != "postgresql":
        return
    op.execute(f'ALTER TABLE "{tabla}" ENABLE ROW LEVEL SECURITY')
    op.execute(
        f"""
        DO $$
        BEGIN
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
            REVOKE ALL ON TABLE "{tabla}" FROM anon;
          END IF;
          IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
            REVOKE ALL ON TABLE "{tabla}" FROM authenticated;
          END IF;
        END $$;
        """
    )


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=120), nullable=True),
        sa.Column("photo_url", sa.String(length=2048), nullable=True),
        sa.Column("role", sa.String(length=20), server_default="user", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("onboarded", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("monthly_budget", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column(
            "preferences",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("last_login_date", _fecha_hora(), nullable=True),
        sa.Column("created_date", _fecha_hora(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_date", _fecha_hora(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("email = lower(email)", name=op.f("ck_users_email_lowercase")),
        sa.CheckConstraint("role IN ('user', 'admin')", name=op.f("ck_users_role_valido")),
        sa.CheckConstraint(
            "monthly_budget >= 0", name=op.f("ck_users_monthly_budget_no_negativo")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )

    op.create_table(
        "categories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=20), nullable=False),
        sa.Column("icon", sa.String(length=50), nullable=True),
        sa.Column("budget", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("created_date", _fecha_hora(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_date", _fecha_hora(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("budget >= 0", name=op.f("ck_categories_budget_no_negativo")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_categories_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_categories")),
    )
    op.create_index(op.f("ix_categories_user_id"), "categories", ["user_id"], unique=False)
    op.create_index(
        "uq_categories_user_id_lower_name",
        "categories",
        ["user_id", sa.literal_column("lower(name)")],
        unique=True,
    )

    op.create_table(
        "expenses",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("merchant", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("category", sa.String(length=100), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("payment_method", sa.String(length=20), server_default="debito", nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("is_recurring", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "recurring_active", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("created_date", _fecha_hora(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_date", _fecha_hora(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_expenses_amount_no_negativo")),
        sa.CheckConstraint(
            "payment_method IN ('efectivo', 'debito', 'credito', 'transferencia')",
            name=op.f("ck_expenses_payment_method_valido"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_expenses_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_expenses")),
    )
    op.create_index("ix_expenses_user_id_date", "expenses", ["user_id", "date"], unique=False)

    op.create_table(
        "incomes",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("type", sa.String(length=20), server_default="otros", nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("created_date", _fecha_hora(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_date", _fecha_hora(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_incomes_amount_no_negativo")),
        sa.CheckConstraint(
            "type IN ('sueldo', 'bono', 'transferencia', 'efectivo', 'otros')",
            name=op.f("ck_incomes_type_valido"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_incomes_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_incomes")),
    )
    op.create_index("ix_incomes_user_id_date", "incomes", ["user_id", "date"], unique=False)

    op.create_table(
        "goals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("target_amount", sa.BigInteger(), nullable=False),
        sa.Column("current_amount", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("deadline", sa.Date(), nullable=True),
        sa.Column("color", sa.String(length=20), server_default="#22c55e", nullable=False),
        sa.Column(
            "contribution_mode", sa.String(length=20), server_default="manual", nullable=False
        ),
        sa.Column("contribution_percent", sa.Float(), nullable=True),
        sa.Column("contribution_amount", sa.BigInteger(), nullable=True),
        sa.Column(
            "contribution_frequency", sa.String(length=20), server_default="meses", nullable=False
        ),
        sa.Column("next_contribution_date", sa.Date(), nullable=True),
        sa.Column("auto_approved_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_date", _fecha_hora(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_date", _fecha_hora(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "contribution_frequency IN ('dias', 'semanas', 'meses')",
            name=op.f("ck_goals_contribution_frequency_valida"),
        ),
        sa.CheckConstraint(
            "contribution_mode IN ('manual', 'percent_surplus', 'fixed')",
            name=op.f("ck_goals_contribution_mode_valido"),
        ),
        sa.CheckConstraint("current_amount >= 0", name=op.f("ck_goals_current_amount_no_negativo")),
        sa.CheckConstraint("target_amount >= 0", name=op.f("ck_goals_target_amount_no_negativo")),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_goals_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_goals")),
        sa.UniqueConstraint("id", "user_id", name="uq_goals_id_user_id"),
    )
    op.create_index(op.f("ix_goals_user_id"), "goals", ["user_id"], unique=False)

    op.create_table(
        "contributions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("goal_id", sa.Uuid(), nullable=False),
        sa.Column("goal_title", sa.String(length=255), nullable=True),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("mode", sa.String(length=20), server_default="manual", nullable=False),
        sa.Column("created_date", _fecha_hora(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_date", _fecha_hora(), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("amount >= 0", name=op.f("ck_contributions_amount_no_negativo")),
        sa.CheckConstraint(
            "mode IN ('manual', 'aprobado', 'auto')", name=op.f("ck_contributions_mode_valido")
        ),
        sa.ForeignKeyConstraint(
            ["goal_id", "user_id"],
            ["goals.id", "goals.user_id"],
            name="fk_contributions_goal_owner",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_contributions_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contributions")),
    )
    op.create_index(op.f("ix_contributions_goal_id"), "contributions", ["goal_id"], unique=False)
    op.create_index(
        "ix_contributions_user_id_date", "contributions", ["user_id", "date"], unique=False
    )

    for tabla in TABLAS:
        _endurecer_para_supabase(tabla)


def downgrade() -> None:
    for tabla in reversed(TABLAS):
        op.drop_table(tabla)
