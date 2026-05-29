#!/bin/sh
set -eu

python - <<'PY'
import os
import sys
import time

import psycopg
from sqlalchemy.engine import make_url

database_url = os.environ.get("DATABASE_URL", "").strip()
if not database_url:
    print("DATABASE_URL is required.", file=sys.stderr)
    sys.exit(1)

url = make_url(database_url)
connect_kwargs = {
    "host": url.host,
    "port": url.port,
    "dbname": url.database,
    "user": url.username,
    "password": url.password,
}

last_error = None
for attempt in range(30):
    try:
        with psycopg.connect(**connect_kwargs) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
        print("Database is ready.")
        break
    except Exception as exc:  # pragma: no cover
        last_error = exc
        print(f"Waiting for database ({attempt + 1}/30): {exc}", file=sys.stderr)
        time.sleep(2)
else:
    print(f"Database did not become ready: {last_error}", file=sys.stderr)
    sys.exit(1)
PY

flask db upgrade

exec "$@"
