# API del sistema

## Auth

- `POST /api/auth/login`
  - Roles: publico
  - Datos: `correo`, `password`
  - Valida: credenciales, usuario activo, limite de intentos
  - Errores: `401`, `422`
  - Logs: `login`, `login_fallido`
- `POST /api/auth/logout`
  - Roles: autenticado
  - Datos: cookie de sesion + CSRF
  - Logs: `logout`
- `GET /api/auth/me`
  - Roles: autenticado
  - Devuelve perfil seguro

## Usuarios

- `GET /api/usuarios`
  - Roles: `Admin`, `Agendador`
  - Area: Admin ve todo; Agendador solo su area
  - Logs: ninguno
- `POST /api/usuarios`
  - Roles: `Admin`
  - Datos: `nombre`, `correo`, `password`, `role_id`, `area_id`
  - Logs: `creacion_usuario`
- `PATCH /api/usuarios/{id}`
  - Roles: `Admin`
  - Logs: `edicion_usuario`
- `PATCH /api/usuarios/{id}/desactivar`
  - Roles: `Admin`
  - Logs: `desactivacion_usuario`

## Areas

- `GET /api/areas`
  - Roles: autenticado
- `POST /api/areas`
  - Roles: `Admin`
  - Logs: `creacion_area`
- `PATCH /api/areas/{id}`
  - Roles: `Admin`
  - Logs: `edicion_area`

## Zonas

- `GET /api/zonas`
  - Roles: autenticado
- `POST /api/zonas`
  - Roles: `Admin`
  - Logs: `creacion_zona`
- `PATCH /api/zonas/{id}`
  - Roles: `Admin`
  - Logs: `edicion_zona`

## Reuniones

- `GET /api/reuniones`
  - Roles: autenticado
  - Objeto: Admin todo; Agendador solo creadas por el o donde participa; Usuario natural solo propias
- `GET /api/reuniones/{id}`
  - Roles: autenticado
  - Objeto: acceso por participacion o privilegio Admin
- `POST /api/reuniones`
  - Roles: `Admin`, `Agendador`
  - Valida: area, participantes, conflictos de agenda, zona activa, horario laboral, multi area
  - Logs: `creacion_reunion`
- `PATCH /api/reuniones/{id}`
  - Roles: `Admin`
  - Logs: `modificacion_reunion`
- `POST /api/reuniones/{id}/cancelar`
  - Roles: `Admin`
  - Logs: `cancelacion_reunion`
- `POST /api/reuniones/{id}/aceptar`
  - Roles: participante autenticado
  - Logs: `aceptacion_reunion`
- `POST /api/reuniones/{id}/rechazar`
  - Roles: participante autenticado
  - Datos: `razon`
  - Logs: `rechazo_reunion`

## Logs

- `GET /api/logs`
  - Roles: `Admin`
  - Devuelve auditoria segura, sin secretos

