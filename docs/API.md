# API EC_NotiPro

## Roles

- `Administrador del sistema`: administra catalogos, usuarios, configuracion, logs y tambien puede operar reuniones.
- `Secretaria`: opera reuniones, calendario y participantes, pero no administra seguridad ni catalogos maestros.
- `Colaborador`: consulta y responde sus reuniones.

## Auth web/API

- `POST /api/auth/login`
  - Publico.
  - Devuelve `csrf_token` y perfil seguro.
- `POST /api/auth/logout`
  - Requiere sesion.
- `GET /api/auth/me`
  - Requiere sesion.

## Auth movil

- `POST /api/mobile/auth/login`
  - Publico.
  - Devuelve `access_token`, `csrf_token` y perfil seguro.
- `POST /api/mobile/auth/logout`
  - Requiere Bearer token.
- `GET /api/mobile/auth/me`
  - Requiere Bearer token.

## Usuarios

- `GET /api/usuarios`
  - Roles: `Administrador del sistema`, `Secretaria`.
- `GET /api/usuarios/buscar`
  - Roles: `Administrador del sistema`, `Secretaria`.
  - Filtros: `q`, `area_id`.
- `POST /api/usuarios`
  - Roles: `Administrador del sistema`.
- `PATCH /api/usuarios/{id}`
  - Roles: `Administrador del sistema`.
- `PATCH /api/usuarios/{id}/desactivar`
  - Roles: `Administrador del sistema`.

## Areas

- `GET /api/areas`
  - Roles: autenticado.
- `POST /api/areas`
  - Roles: `Administrador del sistema`.
- `PATCH /api/areas/{id}`
  - Roles: `Administrador del sistema`.

## Zonas

- `GET /api/zonas`
  - Roles: autenticado.
- `POST /api/zonas`
  - Roles: `Administrador del sistema`.
- `PATCH /api/zonas/{id}`
  - Roles: `Administrador del sistema`.

## Reuniones

- `GET /api/reuniones`
  - Roles: autenticado.
  - `Administrador del sistema` y `Secretaria` ven el tablero completo.
  - `Colaborador` ve solo reuniones en las que participa.
- `GET /api/reuniones/{id}`
  - Requiere acceso por rol operativo o participacion.
- `GET /api/reuniones/{id}/historial`
  - Devuelve cambios historicos persistidos para reportes y auditoria.
- `POST /api/reuniones`
  - Roles: `Administrador del sistema`, `Secretaria`.
  - Campos obligatorios:
    - `titulo`
    - `motivo`
    - `zona_id`
    - `fecha`
    - `hora_inicio`
    - `hora_fin`
    - `participant_ids`
    - `responsable_reunion_id`
- `PATCH /api/reuniones/{id}`
  - Roles: `Administrador del sistema`, `Secretaria`.
- `POST /api/reuniones/{id}/cancelar`
  - Roles: `Administrador del sistema`, `Secretaria`.
- `POST /api/reuniones/{id}/aceptar`
  - Roles: participante autenticado.
- `POST /api/reuniones/{id}/rechazar`
  - Roles: participante autenticado.
  - Requiere `razon`.

## Móvil

- `GET /api/mobile/reuniones`
  - Devuelve reuniones visibles para el usuario autenticado.
- `GET /api/mobile/reuniones/{id}`
  - Incluye `responsable`.
- `POST /api/mobile/reuniones/{id}/aceptar`
- `POST /api/mobile/reuniones/{id}/rechazar`
- `POST /api/mobile/device-token`
  - Registra FCM token para push real.

## Operacion interna

- `GET /api/logs`
  - Roles: `Administrador del sistema`.
- `GET /api/configuracion`
  - Roles: `Administrador del sistema`.
- `PATCH /api/configuracion`
  - Roles: `Administrador del sistema`.

## Comportamiento de notificaciones y correo

- Crear, editar, cancelar o responder una reunion genera eventos de push y correo.
- Los eventos inmediatos se despachan justo despues del commit.
- Los recordatorios a 30 y 10 minutos quedan persistidos para despacho automatico.
- El historial de reuniones se guarda en `reunion_historial`.
