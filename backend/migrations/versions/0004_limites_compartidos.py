"""Límites de intentos y escaneos compartidos entre instancias (en la base de datos).

Revision ID: 0004
Revises: 0003

Antes los contadores vivían en la memoria de cada proceso: con varias instancias
(Vercel, Cloud Run) cada una contaba por separado y el límite de intentos de contraseña
casi no protegía. Ahora se guardan aquí.
"""
import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

_TABLAS = ("intentos_limitados", "escaneos_en_curso")


def upgrade() -> None:
    op.create_table(
        "intentos_limitados",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("nombre", sa.String(length=40), nullable=False),
        sa.Column("clave", sa.String(length=64), nullable=False),
        sa.Column("ts", sa.Float(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_intentos_limitados")),
    )
    op.create_index(
        "ix_intentos_limitados_nombre_clave_ts", "intentos_limitados", ["nombre", "clave", "ts"], unique=False
    )
    op.create_table(
        "escaneos_en_curso",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("iniciado_ts", sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_escaneos_en_curso_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_escaneos_en_curso")),
    )

    # Misma protección que las demás tablas (ver 0001 y 0002): cerradas al Data API público de Supabase.
    if op.get_bind().dialect.name == "postgresql":
        for tabla in _TABLAS:
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


def downgrade() -> None:
    op.drop_table("escaneos_en_curso")
    op.drop_table("intentos_limitados")
