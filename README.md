# Sistema de Gestion de Reuniones

Sistema web y API para administrar reuniones por areas con backend seguro, control de permisos, auditoria y base de datos propia.

## Stack

- Flask
- SQLAlchemy
- SQLite por defecto
- Jinja para la web inicial
- pytest para pruebas

## Ejecucion local

```bash
python -m pip install -e .[dev]
set FLASK_APP=run.py
flask init-db
python run.py
```

La web queda en `http://127.0.0.1:5000`.

## Credenciales semilla

- `admin@empresa.local` / `Admin123!`
- `agendador.contabilidad@empresa.local` / `Agenda123!`
- `usuario1.contabilidad@empresa.local` / `Usuario123!`

## Rutas principales

- Web Admin: `/admin`
- Web Agendador: `/scheduler`
- API: `/api/*`

## Android

El prototipo Android vive en [android](/e:/Outlook_Agenda_Movil/android) y usa Kotlin + Jetpack Compose.

Build local validado:

```bash
set JAVA_HOME=C:\Program Files\Android\Android Studio\jbr
cd android
gradlew.bat assembleDebug
```

APK debug:

- `android/app/build/outputs/apk/debug/app-debug.apk`

Base URL configurable desde Login y Perfil:

- Emulador Android: `http://10.0.2.2:5000`
- Telefono fisico en tu Wi-Fi actual: `http://192.168.0.139:5000`
- Demo por internet: `https://TU_URL_NGROK`

Modo visual:

- `debug` -> `DEBUG_UI=true`: muestra URL backend, versión, IDs y último error técnico
- `release` -> `DEBUG_UI=false`: oculta URL backend, IDs y detalles técnicos

Endpoints moviles:

- `POST /api/mobile/auth/login`
- `POST /api/mobile/auth/logout`
- `GET /api/mobile/auth/me`
- `POST /api/mobile/device-token`
- `GET /api/mobile/reuniones`
- `GET /api/mobile/reuniones/{id}`
- `POST /api/mobile/reuniones/{id}/aceptar`
- `POST /api/mobile/reuniones/{id}/rechazar`

Notificaciones push preparadas:

- Canales Android: `Reuniones`, `Recordatorios`, `Urgentes`
- Permiso `POST_NOTIFICATIONS` en Android 13+
- Registro de token FCM al existir configuracion Firebase valida
- Backend con `device_tokens`, `notification_events` y `notification_logs`
- Despacho manual local:

```bash
flask dispatch-notifications
```

Variables nuevas:

- `FCM_ENABLED=false`
- `FCM_SERVER_KEY=`
- `FCM_ENDPOINT=https://fcm.googleapis.com/fcm/send`

## Seguridad aplicada

- El frontend no decide permisos ni area efectiva.
- El backend obtiene identidad y rol desde sesion autenticada.
- No se exponen hashes de contrasena ni sesiones.
- Validaciones de horario, zona, area y participantes corren en servicios de negocio.
- Logs de auditoria registran acciones e intentos rechazados.

## Entregables incluidos

- Backend/API
- Base de datos y seeds
- Web Admin y Web Agendador iniciales
- Documentacion de API
- Modelo de datos
- Checklist OWASP
- Pruebas de permisos y seguridad
