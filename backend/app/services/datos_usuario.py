"""Reinicio de la cuenta (el "Reiniciar aplicación" de Ajustes)."""
from __future__ import annotations

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db.models import Category, Contribution, Expense, Goal, Income, User
from app.services.categorias import agregar_categorias_faltantes


def reiniciar_cuenta(db: Session, usuario: User) -> None:
    """Borra TODOS los datos del usuario (gastos, ingresos, metas con sus
    aportes y categorías), vuelve a crear las categorías por defecto y
    devuelve el perfil al estado inicial (encuesta de bienvenida pendiente
    y presupuesto en cero). La cuenta, el correo, la contraseña y las
    preferencias se conservan.

    Todo ocurre en UNA transacción: si algo falla a mitad, no se pierde
    nada (en la plataforma anterior eran tres llamadas separadas).
    """
    uid = usuario.id
    try:
        for modelo in (Contribution, Goal, Income, Expense, Category):
            db.execute(delete(modelo).where(modelo.user_id == uid))
        agregar_categorias_faltantes(db, uid)
        usuario.onboarded = False
        usuario.monthly_budget = 0
        db.commit()
    except Exception:
        db.rollback()
        raise
