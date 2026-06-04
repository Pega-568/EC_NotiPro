ROLE_ADMIN = "Administrador del sistema"
ROLE_AGENDADOR = "Agendador de área"
ROLE_SECRETARIA = "Secretaria"
ROLE_COLABORADOR = "Colaborador"

OPERATOR_ROLES = (ROLE_SECRETARIA, ROLE_AGENDADOR)

ROLE_DISPLAY_NAMES = {
    ROLE_AGENDADOR: "Encargado de Área",
}


def display_role_name(role_name: str | None) -> str:
    if not role_name:
        return ""
    return ROLE_DISPLAY_NAMES.get(role_name, role_name)

