# EC_NotiPro

Base de produccion interna para agenda institucional, confirmaciones de reuniones y notificaciones operativas de Ecuamatriz.

## Estado actual

- PostgreSQL listo como base principal por `DATABASE_URL`.
- Migraciones versionadas con Flask-Migrate en [migrations](/e:/Outlook_Agenda_Movil/migrations).
- Roles separados:
  - `Administrador del sistema`
  - `Secretaria`
  - `Colaborador`
- `responsable_reunion_id` obligatorio en reuniones.
- Push y correos formales modelados como eventos persistidos.
- Historial de reuniones persistido en `reunion_historial`.
- Web con identidad Ecuamatriz y calendario operativo mejorado.

## Stack

- Flask
- SQLAlchemy
- Flask-Migrate / Alembic
- PostgreSQL
- Jinja
- Kotlin + Jetpack Compose (app Android)
- pytest

## Arranque local

```powershell
python -m pip install -e .[dev]
$env:FLASK_APP = "run.py"
flask db upgrade
flask init-db
python run.py
```

La web queda en `http://127.0.0.1:5000`.

## Credenciales semilla

- `admin@empresa.local` / `Admin123!`
- `secretaria.general@empresa.local` / `Agenda123!`
- `usuario1.contabilidad@empresa.local` / `Usuario123!`

## Rutas principales

- Panel sistema: `/web/admin`
- Operacion secretaria: `/scheduler`
- API: `/api/*`
- API movil: `/api/mobile/*`

## Android

La app Android vive en [android](/e:/Outlook_Agenda_Movil/android).

Build local:

```powershell
cd android
.\gradlew.bat assembleDebug
```

APK debug:

- `android/app/build/outputs/apk/debug/app-debug.apk`

## Documentacion clave

- API: [docs/API.md](/e:/Outlook_Agenda_Movil/docs/API.md)
- Modelo de datos: [docs/MODELO_DATOS.md](/e:/Outlook_Agenda_Movil/docs/MODELO_DATOS.md)
- Despliegue interno: [docs/DEPLOY_PRODUCCION.md](/e:/Outlook_Agenda_Movil/docs/DEPLOY_PRODUCCION.md)
