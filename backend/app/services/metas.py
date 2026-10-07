"""
Aportes a metas de ahorro, como operaciones ATÓMICAS.

En la plataforma anterior un aporte eran dos llamadas separadas (crear el aporte y luego
actualizar el monto de la meta), así que un corte a mitad dejaba la meta
con un monto que no coincidía con sus aportes. Aquí cada operación es una
sola transacción, y la meta se bloquea (`FOR UPDATE`) mientras se
modifica, para que dos aportes simultáneos no se pisen el monto.
"""
from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.db.models import Contribution, Goal
from app.schemas.comunes import MAX_MONTO
from app.schemas.metas import AporteIn
from app.services.acceso import obtener_propio
from app.services.errores import DatoInvalido


def registrar_aporte(
    db: Session, usuario_id: uuid.UUID, meta_id: uuid.UUID, datos: AporteIn
) -> tuple[Contribution, Goal]:
    meta = obtener_propio(db, Goal, meta_id, usuario_id, bloquear=True)

    nuevo_total = meta.current_amount + datos.amount
    if nuevo_total > MAX_MONTO:
        raise DatoInvalido("El monto acumulado de la meta superaría el máximo permitido.")

    aporte = Contribution(
        user_id=usuario_id,
        goal_id=meta.id,
        goal_title=meta.title,  # copia del nombre al momento del aporte
        amount=datos.amount,
        date=datos.date,
        mode=datos.mode,
    )
    db.add(aporte)
    meta.current_amount = nuevo_total
    if datos.mode == "aprobado":
        meta.auto_approved_count += 1
    if "next_contribution_date" in datos.model_fields_set:
        meta.next_contribution_date = datos.next_contribution_date
    db.commit()
    return aporte, meta


def deshacer_aporte(db: Session, usuario_id: uuid.UUID, aporte_id: uuid.UUID) -> Goal:
    """Borra el aporte y descuenta su monto de la meta (nunca bajo cero)."""
    aporte = obtener_propio(db, Contribution, aporte_id, usuario_id)
    # Se bloquea la META primero y se vuelve a leer el aporte: si otra
    # petición lo deshizo mientras tanto, esta responde 404 y no descuenta
    # el monto dos veces.
    meta = obtener_propio(db, Goal, aporte.goal_id, usuario_id, bloquear=True)
    aporte = obtener_propio(db, Contribution, aporte_id, usuario_id)

    meta.current_amount = max(0, meta.current_amount - aporte.amount)
    db.delete(aporte)
    db.commit()
    return meta
