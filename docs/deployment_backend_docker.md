# Despliegue del Backend con Docker Compose

Esta guia reutiliza el hardening del backend ya aplicado: `/health`, validaciones de produccion, `create-admin`, separacion de usuarios demo y arranque con `gunicorn`.

## 1. Requisitos del servidor

- Docker Engine 27+ o Docker Desktop reciente
- Docker Compose v2+
- Git
- 2 GB RAM o mas
- Puerto 8000 libre para backend
- Carpeta local `secrets/` para material sensible fuera de la imagen

## 2. Instalar Docker

En Ubuntu:

```bash
sudo apt update
sudo apt install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

## 3. Clonar el repositorio

```bash
git clone https://github.com/Pega-568/EC_NotiPro.git
cd EC_NotiPro
git checkout feature/server-deployment-hardening
```

## 4. Crear `.env`

Use `.env.docker.example` como base:

```bash
cp .env.docker.example .env
```

Ajustes importantes:

- Para produccion real:
  - `SESSION_COOKIE_SECURE=true`
  - `APP_ALLOWED_ORIGINS=https://dominio-real`
  - `INTERNAL_BASE_URL=https://dominio-real`
  - `SECRET_KEY` fuerte
  - `POSTGRES_PASSWORD` fuerte
- Para prueba Docker local se pueden usar valores temporales, pero si `APP_ENV=production` las validaciones siguen exigiendo orígenes y URL no locales.

## 5. Firebase service account

No suba el archivo al repositorio.

```bash
mkdir -p secrets
cp /ruta/segura/firebase-service-account.json ./secrets/firebase-service-account.json
chmod 600 ./secrets/firebase-service-account.json
```

El contenedor lo monta en:

`/run/secrets/firebase-service-account.json`

## 6. Build

```bash
docker compose build
```

## 7. Levantar servicios

```bash
docker compose up -d
docker compose ps
docker compose logs backend
```

Servicios:

- `db`: PostgreSQL 16 con volumen persistente
- `backend`: Flask + Gunicorn en `http://localhost:8000`

Para un frente Nginx opcional:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

## 8. Inicializar base

Migraciones:

```bash
docker compose exec backend flask db upgrade
```

Catalogos base y zonas operativas:

```bash
docker compose exec backend flask init-db
```

En `APP_ENV=production`, `init-db` no crea usuarios demo, pero si deja roles, areas, configuracion y zonas minimas.

## 9. Crear administrador seguro

Defina `ADMIN_EMAIL`, `ADMIN_PASSWORD` y `ADMIN_NAME` en `.env`, luego:

```bash
docker compose exec backend flask create-admin
```

## 10. Verificaciones HTTP

Salud:

```bash
curl -i http://localhost:8000/health
```

Login movil:

```bash
curl -i -X POST http://localhost:8000/api/mobile/auth/login \
  -H "Content-Type: application/json" \
  -d '{"correo":"admin.seguro@empresa.com","password":"clave-segura"}'
```

## 11. Backups

Desde host:

```bash
./deploy/backup_postgres.sh
```

Genera un `.dump` en `./backups/`.

## 12. Restore

Ejemplo:

```bash
cat ./backups/ec_notipro_YYYYMMDD_HHMMSS.dump | docker compose exec -T db pg_restore -U "$POSTGRES_USER" -d "$POSTGRES_DB" --clean --if-exists
```

## 13. Actualizacion

```bash
git pull
docker compose build
docker compose up -d
docker compose exec backend flask db upgrade
```

## 14. Rollback

```bash
git checkout <tag-o-commit-estable>
docker compose build
docker compose up -d
```

Si el esquema cambió, valide compatibilidad antes de restaurar datos o código antiguo.

## 15. Logs

```bash
docker compose logs -f backend
docker compose logs -f db
```

## 16. Checklist post-despliegue

- `docker compose ps` sin servicios reiniciando
- `/health` responde `200`
- `flask init-db` crea catalogos y zonas
- `flask create-admin` crea el admin seguro
- login movil responde correctamente
- no existen usuarios demo en produccion
- el JSON de Firebase no esta dentro de la imagen
