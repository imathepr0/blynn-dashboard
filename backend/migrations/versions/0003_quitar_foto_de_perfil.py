"""Quita la foto de perfil: todos los usuarios usan el mismo avatar.

Revision ID: 0003
Revises: 0002

La columna solo guardaba una URL y nunca se usó en producción (los datos
existentes eran de prueba), así que borrarla no pierde nada importante.
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("users", "photo_url")


def downgrade() -> None:
    op.add_column("users", sa.Column("photo_url", sa.String(length=2048), nullable=True))
