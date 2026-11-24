#!/usr/bin/env bash
# Back up the MySQL database to backups/student_finance_YYYYmmdd_HHMM.sql.gz
# Reads DB_* values from .env. Schedule daily with cron, e.g.:
#   15 2 * * * /path/to/student-finance-system/scripts/backup_mysql.sh
set -euo pipefail
cd "$(dirname "$0")/.."
# Read only the DB_* settings from .env (other lines may not be valid shell)
while IFS='=' read -r key value; do
  case "$key" in DB_*) export "$key=$value" ;; esac
done < <(grep -E '^DB_[A-Z_]+=' .env | tr -d '\r')
mkdir -p backups
FILE="backups/${DB_NAME}_$(date +%Y%m%d_%H%M).sql.gz"
MYSQL_PWD="$DB_PASSWORD" mysqldump --single-transaction --routines --no-tablespaces \
  -h "$DB_HOST" -P "$DB_PORT" -u "$DB_USER" "$DB_NAME" | gzip > "$FILE"
chmod 600 "$FILE"
# keep the 14 most recent backups
ls -1t backups/*.sql.gz | tail -n +15 | xargs -r rm --
echo "Backup written to $FILE"
