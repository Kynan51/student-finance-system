#!/usr/bin/env bash
# Restore a backup made by backup_mysql.sh:  scripts/restore_mysql.sh backups/FILE.sql.gz
# WARNING: replaces the current contents of the database in .env.
set -euo pipefail
cd "$(dirname "$0")/.."
[ $# -eq 1 ] || { echo "Usage: $0 backups/FILE.sql.gz"; exit 1; }
# Read only the DB_* settings from .env (other lines may not be valid shell)
while IFS='=' read -r key value; do
  case "$key" in DB_*) export "$key=$value" ;; esac
done < <(grep -E '^DB_[A-Z_]+=' .env | tr -d '\r')
read -r -p "Restore $1 into database '$DB_NAME'? This overwrites current data. Type yes: " ok
[ "$ok" = "yes" ] || { echo "Cancelled."; exit 1; }
gunzip -c "$1" | MYSQL_PWD="$DB_PASSWORD" mysql -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" "$DB_NAME"
echo "Restore complete."
