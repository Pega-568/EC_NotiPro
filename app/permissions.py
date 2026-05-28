from flask import g

from app.constants import ROLE_ADMIN, ROLE_SECRETARIA
from app.errors import ForbiddenError, NotFoundError
from app.models import Reunion


def can_view_meeting(reunion: Reunion) -> bool:
    user = g.current_user
    if user.role.nombre in (ROLE_ADMIN, ROLE_SECRETARIA):
        return True
    if reunion.creador_id == user.id or reunion.responsable_reunion_id == user.id:
        return True
    return any(item.usuario_id == user.id for item in reunion.participantes)


def ensure_meeting_access(reunion: Reunion) -> None:
    if not reunion:
        raise NotFoundError("Reunion no encontrada.")
    if not can_view_meeting(reunion):
        raise ForbiddenError("No tiene permiso para ver esta reunion.")
