# Despliegue de Produccion Interna

## Alcance

Esta guia cubre la base productiva interna de EC_NotiPro:

- PostgreSQL
- migraciones
- semillas
- roles separados
- push FCM
- correos SMTP
- despacho automatico de recordatorios

No cubre IA, audio ni integraciones Google/Microsoft.

## 1. Variables requeridas

Parta de [.env.example](/e:/Outlook_Agenda_Movil/.env.example) y defina como minimo:

```env
SECRET_KEY=valor-seguro
DATABASE_URL=postgresql+psycopg://usuario:clave@host:5432/ec_notipro
SESSION_COOKIE_SECURE=true
APP_ALLOWED_ORIGINS=https://notipro.interno.ecuamatriz.local
INTERNAL_BASE_URL=https://notipro.interno.ecuamatriz.local
BACKGROUND_DISPATCH_ENABLED=true
BACKGROUND_DISPATCH_INTERVAL_SECONDS=30
```

Para push:

```env
FCM_ENABLED=true
FCM_SERVER_KEY=...
FCM_ENDPOINT=https://fcm.googleapis.com/fcm/send
```

Para correo:

```env
MAIL_ENABLED=true
MAIL_HOST=smtp.office365.com
MAIL_PORT=587
MAIL_USERNAME=...
MAIL_PASSWORD=...
MAIL_USE_TLS=true
MAIL_USE_SSL=false
MAIL_FROM=notificaciones@ecuamatriz.com
MAIL_REPLY_TO=secretaria@ecuamatriz.com
MAIL_SUBJECT_PREFIX=[Ecuamatriz]
```

## 2. Provisionar PostgreSQL

Ejemplo base:

1. Crear base `ec_notipro`.
2. Crear usuario dedicado con permisos sobre esa base.
3. Configurar backups y retencion.
4. Verificar conectividad desde el servidor de la app.

## 3. Instalar dependencias

```powershell
python -m pip install -e .[dev]
```

## 4. Ejecutar migraciones

```powershell
$env:FLASK_APP = "run.py"
flask db upgrade
```

La revision actual es:

- `e186e44cc682` `production foundation baseline`

## 5. Inicializar catalogos y usuarios semilla

```powershell
flask init-db
```

Esto asegura:

- roles base
- areas
- zonas iniciales
- configuracion inicial
- usuarios de ejemplo

En produccion, cambie inmediatamente las credenciales semilla o elimine los usuarios de ejemplo no requeridos.

## 6. Despacho automatico

El proceso web puede despachar eventos pendientes si `BACKGROUND_DISPATCH_ENABLED=true`.

Recomendacion operativa interna:

1. Mantener un unico proceso de app con el despachador habilitado por entorno.
2. Si se usa mas de una replica, deshabilitar el despachador embebido en replicas secundarias.
3. Como respaldo operativo, usar el comando manual:

```powershell
flask dispatch-notifications
```

## 7. Validacion posterior al despliegue

Verifique:

1. Login web con `Administrador del sistema`.
2. Creacion de reunion con `responsable_reunion_id`.
3. Registro de token FCM desde la app.
4. Llegada de correo formal al crear una reunion.
5. Cambio de estado en `notification_events`, `notification_logs`, `email_events` y `email_logs`.
6. Registro historico en `reunion_historial`.

## 8. Pruebas

Comando usado en esta consolidacion:

```powershell
pytest -q
```

Resultado verificado:

- `55 passed`

## 9. Android

Build local esperado:

```powershell
cd android
.\gradlew.bat assembleDebug
```

La app sigue usando los endpoints `/api/mobile/*`. El backend nuevo agrega `responsable` en el detalle de reunion sin romper compatibilidad hacia atras.
