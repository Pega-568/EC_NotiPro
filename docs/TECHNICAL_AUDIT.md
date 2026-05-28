# Auditoría Técnica y Diagnóstico: EC_NotiPro

## 1. Qué está instalado
- **Python**: 3.11.9
- **pip**: 26.0.1
- **Flask**: 3.1.3
- **Android Build (Gradle)**: Exitoso (`assembleDebug` compila correctamente).
- **Base de datos / Migraciones**: Flask-Migrate al día, con revisión head `9c9dd1d9c4f7` aplicada.
- **Pruebas**: pytest 8.4.2 (55 pasadas, 5 fallidas relacionadas con hardening).

## 2. Qué tecnologías se están usando
- **Backend**: Flask 3.1.3, SQLAlchemy 2.0.50, psycopg 3.3.4 (para PostgreSQL).
- **Seguridad**: argon2-cffi (para contraseñas seguras).
- **Notificaciones**: `smtplib` nativo para correo, `urllib` nativo para FCM legacy (sin dependencias extra).
- **Móvil**: Kotlin + Jetpack Compose (se verifica en `android/`).

## 3. Qué funciona hoy
- Registro y autenticación (login web y móvil) con cifrado Argon2, manejo de sesiones HTTPOnly y Bearer tokens.
- Bloqueo de cuentas por múltiples intentos fallidos.
- CRUD básico de usuarios, áreas y zonas desde panel web y API.
- Flujo completo de reuniones (creación, edición, cancelación y respuestas).
- Validaciones de horarios laborales y conflictos cruzados de zona/personas.
- Despacho automático de notificaciones mediante hilo de background (`start_background_dispatcher`).
- Historial de reuniones inmutable y log de auditoría básica de sistema.

## 4. Qué está parcialmente implementado
- **Notificaciones Push**: Funcionales pero utilizan el protocolo obsoleto FCM Legacy con server key. Se requiere migrar a HTTP v1.
- **Configuración de Producción**: La configuración actual tiene fallbacks inseguros que provocan que las pruebas de entorno estricto fallen.

## 5. Qué falta configurar
- Variables obligatorias de entorno para producción en `.env` (el `.env.example` asume datos locales).
- Configuración de un proveedor de correo real (SMTP) para habilitar correos formales.
- Nuevo Firebase Service Account para migración de Push Notifications.

## 6. Qué falta desarrollar
- **Roles**: Falta el rol `Agendador de área` indicado en requerimientos.
- **Tablas/Módulos faltantes**: `email_templates`, `asistencias`, `qr_asistencia_tokens`, `actas_reunion`, `acta_orden_dia`, `acta_acuerdos`, `acta_asistentes_snapshot`, `reunion_archivos`, `audio_transcripciones`, `acta_borradores_ia`.

## 7. Qué está duplicado o redundante
- **Acoplamiento**: La lógica de envíos de push y correos está unificada en `app/services/notifications.py`. Conviene separar un `email_service.py`.
- **Sobre-notificación**: El sistema despacha recordatorios de 30 y 10 minutos a través de ambos canales (Push y Email). El envío por email para avisos tan cortos genera excesivo ruido y debe limitarse solo a notificaciones Push.

## 8. Qué está quemado/hardcodeado
- Correos quemados directamente en código dentro de la función `_build_email_message`.
- Textos genéricos de notificación push quemados en `_build_push_message`.
- Defaults inseguros directamente en `app/config.py` (`change-me`, fallback a SQLite `sqlite:///agenda.db`).

## 9. Qué depende de credenciales externas
- Servidor SMTP externo para envío de invitaciones/correos (`MAIL_HOST`, `MAIL_USERNAME`, `MAIL_PASSWORD`).
- Firebase Cloud Messaging para push notifications (`FCM_SERVER_KEY`).

## 10. Qué conviene mantener
- El modelo actual de reuniones (validaciones robustas contra colisiones de zonas y participantes).
- Las migraciones basadas en Alembic y el uso de SQLAlchemy 2.0.
- El despachador de notificaciones (robusto al manejar eventos asíncronos para desacoplar las respuestas web).
- La arquitectura monolítica y limpia basada en Blueprints.

## 11. Qué conviene corregir
- **FCM**: Migrar de manera urgente de FCM Legacy a Firebase Admin SDK / HTTP v1.
- **Pérdida de datos en edición**: Corregir `update_meeting`, ya que `meeting.participantes.clear()` elimina irreversiblemente todas las respuestas y razones de rechazo previas.
- **Hardening de Configuración**: Forzar crash de la aplicación si se inicia en `production` utilizando SQLite o claves maestras inseguras.
- **Desacoplamiento**: Extraer correos hacia un servicio propio (`email_service.py`).

## 12. Qué conviene eliminar o posponer
- **Posponer**: Funciones relacionadas con IA (borradores IA, transcripción de audios) y asistencia física (códigos QR, actas) hasta estabilizar el hardening core del backend y la migración FCM.

---

## VALIDACIÓN DEL ENTORNO

Resultados comprobados en el entorno actual de Windows:
- `python --version`: **Pasa** (Python 3.11.9).
- `pip --version`: **Pasa** (pip 26.0.1).
- `flask --version`: **Pasa** (Flask 3.1.3).
- `flask --app run.py routes`: **Pasa** (Todas las rutas y endpoints cargan correctamente).
- `flask db current`: **Pasa** (`9c9dd1d9c4f7`).
- `flask db heads`: **Pasa** (`9c9dd1d9c4f7`).
- `flask db upgrade`: **Pasa** (Sin novedades).
- `pytest -q`: **Falla parcialmente** (55 pasadas, 5 fallidas). Los fallos se dan intencionalmente en `test_hardening.py` porque la configuración tolera claves genéricas y bases de datos locales.
- `android/gradlew.bat assembleDebug`: **Pasa** (`BUILD SUCCESSFUL in 37s`, 39 actionable tasks).

---

## VALIDACIÓN DE DEPENDENCIAS PYTHON

**Se comprobó el uso real de:**
- Flask, SQLAlchemy, Flask-SQLAlchemy, Flask-Migrate, Alembic, psycopg, argon2-cffi, python-dotenv, email-validator, pytest.
- `smtplib` nativo y `urllib` nativo.

**Hallazgos:**
- **Firebase Admin SDK**: **No instalada/No declarada**. La app usa `urllib` para realizar llamadas directas a FCM Legacy API. Se requerirá agregar la dependencia oficial de Firebase para la migración.
- No se identificaron dependencias instaladas no utilizadas (el `pyproject.toml` está optimizado).

---

## VALIDACIÓN DE BASE DE DATOS

1. **Motor usado por defecto**: SQLite (`sqlite:///agenda.db`).
2. **Si DATABASE_URL no existe**: Realiza un fallback automático a SQLite, riesgoso para un entorno productivo real.
3. **Soporte PostgreSQL**: 100% soportado mediante `psycopg` v3 (incluido).
4. **SQLite como fallback**: Sí, sigue operando de esta forma.
5. **Tablas existentes**: `roles`, `areas`, `usuarios`, `zonas_reunion`, `reuniones`, `reunion_participantes`, `reunion_historial`, `configuracion`, `sesiones`, `logs_sistema`, `device_tokens`, `notification_events`, `notification_logs`, `email_events`, `email_logs`.
6. **Tablas en migraciones**: Sincronizadas (coinciden exactamente con los modelos listados).
7. **Tablas faltantes**: `asistencias`, `qr_asistencia_tokens`, `actas_reunion`, `acta_orden_dia`, `acta_acuerdos`, `acta_asistentes_snapshot`, `reunion_archivos`, `audio_transcripciones`, `acta_borradores_ia`, `email_templates`.
8. **docs/MODELO_DATOS.md refleja la realidad**: Parcialmente. Lista las tablas principales, pero ignora la mitad del ecosistema transaccional (notificaciones, correos, dispositivos, etc.).
9. **Migraciones pendientes**: No.
10. **init-db crea datos correctamente**: Sí.

**Estado de Implementación:**
- roles, areas, usuarios, zonas_reunion, reuniones, reunion_participantes, reunion_historial, configuracion, sesiones, logs_sistema, device_tokens, notification_events, notification_logs, email_events, email_logs: **Implementada**
- email_templates: **Faltante**
- asistencias, qr_asistencia_tokens, actas_reunion, acta_orden_dia, acta_acuerdos, acta_asistentes_snapshot, reunion_archivos, audio_transcripciones, acta_borradores_ia: **No prioritaria todavía**

---

## VALIDACIÓN DE CONFIGURACIÓN

1. **Defaults seguros**: `SESSION_COOKIE_HTTPONLY`, `MAIL_USE_TLS=true`.
2. **Defaults peligrosos**: `SECRET_KEY`, `DATABASE_URL` hacia sqlite, `SESSION_COOKIE_SECURE=false`.
3. **No deberían estar quemados**: `SECRET_KEY`, `MAIL_PASSWORD`, `FCM_SERVER_KEY`, base de datos.
4. **Obligatorias para production**: `SECRET_KEY`, `DATABASE_URL` estricto, `SESSION_COOKIE_SECURE=true`.
5. **Apuntando a localhost**: `INTERNAL_BASE_URL` (crea enlaces de correo hacia 127.0.0.1) y `APP_ALLOWED_ORIGINS`.
6. **Deben cambiar para servidor real**: `DATABASE_URL`, `INTERNAL_BASE_URL`, `FCM_ENDPOINT`.

---

## VALIDACIÓN DE ROLES Y PERMISOS

**Confirmar roles actuales:**
- Administrador del sistema
- Secretaria
- Colaborador

**Permisos reales detectados:**
1. Crear usuarios / áreas / zonas / modificar config / ver logs: Solo **ROLE_ADMIN**.
2. Crear / cancelar reuniones: **Admin** y **Secretaria** (`OPERATOR_ROLES`).
3. Crear reuniones multiárea: Cualquiera de los `OPERATOR_ROLES` sin restricción local.
4. Responder reuniones: Solo el participante involucrado o el responsable de la reunión.
5. Ver reuniones ajenas: **Admin** y **Secretaria**. (Colaboradores solo ven propias).

**Riesgos detectados:**
- **Admin sigue operando reuniones**: Sí, tiene capacidades operativas.
- **Falta Agendador de área**: SÍ. No existe el rol.
- **Falta limitar por área**: Las Secretarias (y el Administrador) actualmente pueden reservar reuniones en **cualquier** zona activa en el sistema, no existe filtro forzoso limitando las zonas según el área de la secretaria.

---

## VALIDACIÓN DE REUNIONES

**Confirmación de validaciones:**
- Crear funciona, y `responsable_reunion_id` es estrictamente obligatorio.
- Todas las validaciones de horario laboral (08:00 a 17:00 por defecto), zona activa, conflicto de zonas y de participantes (descanso) funcionan satisfactoriamente.
- Rechazar exige string en `razón`.
- Cancelación y actualización general correos y notificaciones y adjunta a historial inmutable.

**Riesgos detectados:**
- **Pérdida de respuestas**: Al invocar `update_meeting()`, la lógica actual realiza un `meeting.participantes.clear()`. Esto resetea las respuestas previas (Aceptada/Rechazada) y **borra** permanentemente las razones de rechazo introducidas por los usuarios.
- **Responsable excluido**: Controlado correctamente, la API arroja error si el responsable no es participante o creador.

---

## VALIDACIÓN DE NOTIFICACIONES PUSH Y CORREO

**Eventos, Logs y Endpoint Móvil:**
- Modelos transaccionales `device_tokens`, `_events`, `_logs` implementados completamente y el guardado de tokens funciona en `POST /api/mobile/device-token`.
- Despacho inmediato implementado y recordatorios pre-programados.

**FCM y Correo - Riesgos Identificados:**
- FCM está en versión obsoleto (Legacy con server key).
- El correo está altamente acoplado a notificaciones.
- El sistema de recordatorios satura al usuario: recibir correo para reuniones que inician en 10 minutos no es práctico, se sugiere usar *exclusivamente push* para los avisos urgentes.
- `INTERNAL_BASE_URL` se usa en los correos (links al detalle), de estar mal configurado en producción generará links rotos (`127.0.0.1`).

---

## VALIDACIÓN DE API Y SEGURIDAD

**Rutas documentadas vs Código Real:**
- Todas las 22 rutas web y 8 rutas móviles coinciden al 100% en métodos y sufijos definidos.
- Web Backend incluye formularios sanos, sin fugas obvias de información, inyectando adecuadamente las variables. No hay rutas duplicadas y el login exige credenciales validadas.

**Seguridad General:**
- Bearer API y Cookies de sesión encriptadas correctas, previniendo leak de `password_hash`. Bloqueo de fuerza bruta activo.
- **Riesgo**: El default inseguro del `SECRET_KEY` permite suplantación de cookies si el SysAdmin sube el app en producción sin modificar `.env`. Se guardan `token` de firebase en base de datos en texto plano (riesgo mínimo dado que no autentican, solo enrutan, pero vale la pena mencionarlo).
- **Riesgo**: Credenciales semillas (Admin123!) exponen riesgo si se lanza un entorno expuesto a internet sin cambiar contraseñas.

---

## VALIDACIÓN DE WEB BACKEND

**Rutas Confirmadas:**
1. Login web: Sí (`/login`).
2. Dashboard Admin: Sí (`/web/admin`).
3. Panel Secretaria: Sí (`/scheduler`).
4. Calendario: Sí (`/web/admin/calendario`).
5. CRUD usuarios: Sí.
6. CRUD áreas: Sí.
7. CRUD zonas: Sí.
8. Crear reunión: Sí.
9. Editar reunión: Sí.
10. Cancelar reunión: Sí.
11. Logs: Sí (vía API web o vista en admin/logs).
12. Configuración: Sí.

**Detecciones Adicionales:**
- Los formularios envían `responsable_reunion_id` de forma correcta.

---

## VALIDACIÓN DE DOCUMENTACIÓN

**Hallazgos en documentación:**
- Rutas locales/quemadas en referencias del Markdown.
- Contraseñas expuestas en `README.md` (credenciales semilla).
- Faltan comandos pormenorizados de migración PostgreSQL en la guía de Despliegue.

---

## PROPUESTA FINAL DEL AUDITOR

### 1. Estado general
**AMARILLO**: Excelente base y diseño arquitectónico, pero contiene deuda de seguridad en las validaciones de entorno (configuración) y deuda tecnológica crítica (FCM Legacy) que impide salida a producción inminente.

### 2. Tabla de componentes
| Componente | Estado | Evidencia | Riesgo | Acción recomendada |
|---|---|---|---|---|
| Core / API Base | Verde | El enrutamiento, pruebas básicas e inyecciones están correctas. Autenticación con Argon2 y Anti-Bruteforce. | Bajo | Ninguna urgente. |
| Gestión de Reuniones | Amarillo | Rutas funcionales, pero `update_meeting` elimina respuestas anteriores. | Medio | Modificar la actualización de participantes en la DB para preservar estados previos. |
| Notificaciones Push | Rojo | Llamada explícita a FCM endpoint legacy (`https://fcm.googleapis.com/fcm/send`). | Alto | Migrar urgente a Firebase Admin SDK (HTTP v1). |
| Notificaciones Correo | Amarillo | Funcional pero acoplado. Genera exceso de correos de 10/30 min. | Medio | Extraer `email_service.py` y anular recordatorios cortos por email. |
| Entorno (Hardening) | Amarillo | 5 fallos en testing relacionados a defaults inseguros. | Alto | Rechazar explícitamente arrancar con config local en modo producción. |

### 3. Lista de acciones prioritarias
- **P0 Crítico**: Migrar notificaciones FCM a HTTP v1.
- **P0 Crítico**: Eliminar `meeting.participantes.clear()` al editar reuniones para evitar pérdida de datos de respuestas/rechazos.
- **P1 Importante**: Hardening del Backend (validación `APP_ENV=production` y rechazo de variables default y fallback SQLite).
- **P1 Importante**: Desacoplar envío de correos (crear servicio `email_service.py`) y limpiar exceso de alertas de correo corto.
- **P2 Mejora**: Refinar modelo de roles para agregar restricción de Zonas por Área y crear `Agendador de área`.
- **P3 Futuro**: Iniciar módulos modulares para asistencia QR, actas y transcripciones IA.

### 4. Recomendación
**Continuar sobre este repo.**
La arquitectura interna monolítica usando Flask 3 y SQLAlchemy 2.0 es sólida, legible y está bien estructurada con `Blueprint`. El esfuerzo para estabilizar y endurecer este backend es bajo en comparación a rehacerlo.

### 5. Próximo plan de trabajo en orden
1. **Backend hardening** (Solucionar vulnerabilidades de entorno).
2. **FCM/SMTP real** (Actualización a SDK moderno y servicio dedicado de email).
3. **App mobile refinement** (Pruebas manuales finales).
4. **Staging** (Despliegue simulado y validación cruzada).
5. **QR/asistencia**.
6. **Actas**.
