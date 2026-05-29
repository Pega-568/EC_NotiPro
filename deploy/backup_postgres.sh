#!/bin/sh
set -eu

ENV_FILE="${ENV_FILE:-.env}"
BACKUP_DIR="${BACKUP_DIR:-./backups}"

if [ ! -f "$ENV_FILE" ]; then
    echo "Missing env file: $ENV_FILE" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR"

set -a
. "$ENV_FILE"
set +a

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_FILE="$BACKUP_DIR/ec_notipro_${TIMESTAMP}.dump"

docker compose exec -T db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc > "$OUTPUT_FILE"

echo "Backup created: $OUTPUT_FILE"
