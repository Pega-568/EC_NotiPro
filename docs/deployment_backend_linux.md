# Despliegue Seguro del Backend en Linux

Esta guia prepara el backend de EC_NotiPro para un servidor Linux sin alterar el flujo local actual con `python run.py`.

## 1. Requisitos del servidor

- Ubuntu 22.04 LTS o equivalente
- Acceso `sudo`
- Python 3.11 o superior
- `python3-venv`
- Git
- Nginx
- PostgreSQL local o acceso a PostgreSQL corporativo
- Certificados TLS validos

## 2. Instalacion base

```bash
sudo apt update
sudo apt install -y git python3 python3-venv python3-pip nginx
```

Si PostgreSQL vive en el mismo servidor:

```bash
sudo apt install -y postgresql postgresql-contrib
```

## 3. Clonar y preparar el proyecto

```bash
sudo mkdir -p /opt/ec-notipro
sudo chown "$USER":"$USER" /opt/ec-notipro
git clone https://github.com/Pega-568/EC_NotiPro.git /opt/ec-notipro
cd /opt/ec-notipro
git checkout feature/server-deployment-hardening
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

## 4. PostgreSQL

Puede usar PostgreSQL local o corporativo. Lo importante es que `DATABASE_URL` apunte a una base dedicada.

Ejemplo local:

```bash
sudo -u postgres psql
CREATE DATABASE ec_notipro;
CREATE USER ec_notipro_user WITH ENCRYPTED PASSWORD 'cambiar-por-segura';
GRANT ALL PRIVILEGES ON DATABASE ec_notipro TO ec_notipro_user;
\q
```

Ejemplo `DATABASE_URL`:

```env
DATABASE_URL=postgresql+psycopg://ec_notipro_user:clave-segura@127.0.0.1:5432/ec_notipro
```

## 5. Archivo de entorno de produccion

No suba `.env` real al repositorio. Cree un archivo protegido:

```bash
sudo mkdir -p /etc/ec-notipro
sudo chmod 750 /etc/ec-notipro
sudo nano /etc/ec-notipro/.env
sudo chmod 640 /etc/ec-notipro/.env
```

Base recomendada:

```env
APP_ENV=production
SECRET_KEY=valor-largo-y-aleatorio
DATABASE_URL=postgresql+psycopg://ec_notipro_user:clave-segura@127.0.0.1:5432/ec_notipro
DB_POOL_RECYCLE_SECONDS=1800
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_SAMESITE=Lax
APP_ALLOWED_ORIGINS=https://notipro.midominio.com
SESSION_TTL_MINUTES=480
LOGIN_LOCK_MINUTES=15
INTERNAL_BASE_URL=https://notipro.midominio.com
FCM_ENABLED=true
FCM_SERVICE_ACCOUNT_PATH=/etc/ec-notipro/firebase-service-account.json
BACKGROUND_DISPATCH_ENABLED=true
BACKGROUND_DISPATCH_INTERVAL_SECONDS=30
MAIL_ENABLED=true
MAIL_HOST=smtp.office365.com
MAIL_PORT=587
MAIL_USERNAME=usuario
MAIL_PASSWORD=clave
MAIL_USE_TLS=true
MAIL_USE_SSL=false
MAIL_FROM=notificaciones@midominio.com
MAIL_REPLY_TO=secretaria@midominio.com
MAIL_SUBJECT_PREFIX=[EC_NotiPro]
LOG_LEVEL=INFO
LOG_FILE=/var/log/ec-notipro/app.log
ALLOW_DEMO_SEED=false
ADMIN_EMAIL=admin.seguro@midominio.com
ADMIN_PASSWORD=clave-admin-muy-segura
ADMIN_NAME=Administrador Principal
```

## 6. Firebase service account

No suba el JSON al repositorio.

Ubicacion sugerida:

```bash
sudo install -d -m 750 /etc/ec-notipro
sudo cp firebase-service-account.json /etc/ec-notipro/firebase-service-account.json
sudo chown root:www-data /etc/ec-notipro/firebase-service-account.json
sudo chmod 640 /etc/ec-notipro/firebase-service-account.json
```

## 7. Dependencias

Dentro del entorno virtual:

```bash
cd /opt/ec-notipro
source .venv/bin/activate
python -m pip install -e .
```

## 8. Migraciones

```bash
cd /opt/ec-notipro
source .venv/bin/activate
export FLASK_APP=run.py
flask db upgrade
```

## 9. Inicializar catalogos base

```bash
cd /opt/ec-notipro
source .venv/bin/activate
export FLASK_APP=run.py
flask init-db
```

En `APP_ENV=production`, `init-db` crea catalogos base y zonas iniciales, pero no crea usuarios demo.

## 10. Crear administrador seguro

```bash
cd /opt/ec-notipro
source .venv/bin/activate
export FLASK_APP=run.py
flask create-admin
```

Usa `ADMIN_EMAIL`, `ADMIN_PASSWORD` y `ADMIN_NAME` desde `/etc/ec-notipro/.env`.

## 11. Gunicorn

Prueba manual:

```bash
cd /opt/ec-notipro
source .venv/bin/activate
export FLASK_APP=run.py
gunicorn --workers 3 --bind 127.0.0.1:8000 run:app
```

## 12. systemd

Copie el ejemplo incluido:

```bash
sudo cp deploy/ec-notipro.service.example /etc/systemd/system/ec-notipro.service
sudo systemctl daemon-reload
sudo systemctl enable ec-notipro
sudo systemctl start ec-notipro
sudo systemctl status ec-notipro
```

## 13. Nginx

Copie el ejemplo incluido:

```bash
sudo cp deploy/nginx_ec_notipro.conf.example /etc/nginx/sites-available/ec-notipro.conf
sudo ln -s /etc/nginx/sites-available/ec-notipro.conf /etc/nginx/sites-enabled/ec-notipro.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 14. HTTPS

Opciones recomendadas:

- terminacion TLS en balanceador corporativo
- o `certbot` con Nginx

Ejemplo con Certbot:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d notipro.midominio.com
```

## 15. Pruebas con curl

Salud interna:

```bash
curl -i http://127.0.0.1:8000/health
```

Salud publica:

```bash
curl -i https://notipro.midominio.com/health
```

Login movil:

```bash
curl -i -X POST https://notipro.midominio.com/api/mobile/auth/login \
  -H "Content-Type: application/json" \
  -d '{"correo":"usuario@midominio.com","password":"clave"}'
```

## 16. Rollback basico

1. Identifique el commit estable previo.
2. Cambie el checkout al commit o tag aprobado.
3. Reinstale dependencias si cambiaron.
4. Ejecute `flask db upgrade` solo si la version objetivo es compatible.
5. Reinicie `systemd`.

Ejemplo:

```bash
cd /opt/ec-notipro
git fetch --all --tags
git checkout beta-local-1-stable
source .venv/bin/activate
python -m pip install -e .
sudo systemctl restart ec-notipro
```

## 17. Backups

- backup diario de PostgreSQL con retencion definida
- copia del archivo `/etc/ec-notipro/.env`
- copia segura del JSON de Firebase
- registro del commit desplegado

Ejemplo:

```bash
pg_dump -Fc ec_notipro > /var/backups/ec_notipro_$(date +%F).dump
```

## 18. Checklist post-despliegue

- `systemctl status ec-notipro` sin errores
- `nginx -t` valido
- `curl /health` devuelve `200`
- login web funcional
- login movil funcional
- `flask create-admin` ejecutado o verificado
- no existen usuarios demo en produccion
- FCM configurado solo si el JSON existe y es legible
- logs de app y nginx sin errores criticos
