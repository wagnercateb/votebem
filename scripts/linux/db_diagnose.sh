#!/usr/bin/env bash
# MariaDB/Compose diagnostic script for VoteBem
# Collects environment, compose config, container health, logs, mounts, and data-dir details
# to help diagnose startup failures that are not simple credential issues.

set -uo pipefail

log()  { echo -e "[INFO]  $*"; }
warn() { echo -e "[WARN]  $*"; }
err()  { echo -e "[ERROR] $*" >&2; }

# Defaults
APP_NAME_DEFAULT="votebem"
STACK_DIR_DEFAULT="/dados/votebem"
COMPOSE_FILE_DEFAULT="${STACK_DIR_DEFAULT}/docker-compose.yml"
MARIADB_DIR_DEFAULT="/dados/mariadb/${APP_NAME_DEFAULT}/data"

usage() {
  cat <<USAGE
Usage: $0 [-n APP_NAME] [-s STACK_DIR] [-f COMPOSE_FILE] [-d MARIADB_DIR]

Options:
  -n APP_NAME     Application name (defaults: ${APP_NAME_DEFAULT})
  -s STACK_DIR    Stack directory (defaults: ${STACK_DIR_DEFAULT})
  -f COMPOSE_FILE Compose file path (defaults: ${COMPOSE_FILE_DEFAULT})
  -d MARIADB_DIR  Host MariaDB data directory (defaults: ${MARIADB_DIR_DEFAULT})

This script prints a comprehensive diagnostic report for the MariaDB service.
Run it and paste the full output here for analysis.
USAGE
}

APP_NAME="${APP_NAME_DEFAULT}"
STACK_DIR="${STACK_DIR_DEFAULT}"
COMPOSE_FILE="${COMPOSE_FILE_DEFAULT}"
MARIADB_DIR="${MARIADB_DIR_DEFAULT}"

while getopts ":n:s:f:d:h" opt; do
  case "$opt" in
    n) APP_NAME="$OPTARG" ;;
    s) STACK_DIR="$OPTARG" ;;
    f) COMPOSE_FILE="$OPTARG" ;;
    d) MARIADB_DIR="$OPTARG" ;;
    h) usage; exit 0 ;;
    :) err "Option -$OPTARG requires an argument"; usage; exit 1 ;;
    \?) err "Invalid option -$OPTARG"; usage; exit 1 ;;
  esac
done

# Compose command detection
if docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker compose"
elif docker-compose version >/dev/null 2>&1; then
  COMPOSE_CMD="docker-compose"
else
  err "Docker Compose is not installed (plugin or legacy)."; exit 1
fi

DB_SERVICE="db"
DB_CONTAINER="${APP_NAME}_db"

echo "============================================================"
echo "VoteBem MariaDB Diagnostic Report"
echo "Time: $(date -Is)"
echo "WSL: $(uname -r 2>/dev/null | grep -qi microsoft && echo yes || echo no)"
echo "Compose: $(${COMPOSE_CMD} version 2>/dev/null | head -n 1 || echo unknown)"
echo "Docker: $(docker --version 2>/dev/null || echo unknown)"
echo "App: ${APP_NAME} | Stack: ${STACK_DIR}"
echo "Compose file: ${COMPOSE_FILE}"
echo "MariaDB data dir: ${MARIADB_DIR}"
echo "============================================================"

echo "\n-- Compose config (service db) --"
${COMPOSE_CMD} -f "${COMPOSE_FILE}" config 2>/dev/null | awk 'p&&/^[^[:space:]]/{exit} p; /(^| )db:/{p=1}' || ${COMPOSE_CMD} -f "${COMPOSE_FILE}" config 2>/dev/null || true

echo "\n-- Compose ps --"
${COMPOSE_CMD} -f "${COMPOSE_FILE}" ps || true

echo "\n-- Container health & inspect --"
DB_ID="$(${COMPOSE_CMD} -f "${COMPOSE_FILE}" ps -q ${DB_SERVICE} 2>/dev/null || echo)"
if [[ -n "${DB_ID}" ]]; then
  docker inspect "${DB_ID}" 2>/dev/null | sed -n \
    -e 's/\r//g' \
    -e '/"Name"/p' \
    -e '/"Image"/p' \
    -e '/"State"/p' \
    -e '/"Health"/p' \
    -e '/"Mounts"/p' || true
  echo "Healthcheck (test): $(docker inspect --format '{{json .Config.Healthcheck.Test}}' "${DB_ID}" 2>/dev/null || echo unknown)"
  echo "Health status: $(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' "${DB_ID}" 2>/dev/null || echo unknown)"
else
  warn "Could not resolve DB container ID via compose; falling back to name ${DB_CONTAINER}."
  docker inspect "${DB_CONTAINER}" 2>/dev/null | sed -n -e '/"Name"/p' -e '/"Image"/p' -e '/"State"/p' -e '/"Health"/p' -e '/"Mounts"/p' || true
  echo "Healthcheck (test): $(docker inspect --format '{{json .Config.Healthcheck.Test}}' "${DB_CONTAINER}" 2>/dev/null || echo unknown)"
  echo "Health status: $(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}n/a{{end}}' "${DB_CONTAINER}" 2>/dev/null || echo unknown)"
fi

echo "\n-- Container env (sanitized) --"
TARGET_CONT="${DB_ID:-${DB_CONTAINER}}"
docker inspect --format '{{range .Config.Env}}{{println .}}{{end}}' "${TARGET_CONT}" 2>/dev/null | sed 's/\r//g' | \
  awk 'BEGIN{FS="="} {val=$0; key=$1; sub(/^[^=]*=/, "", val); if (key ~ /PASSWORD|SECRET|KEY/) { masked=substr(val,1,1)"***"length(val); printf("%s=%s\n", key, masked)} else {print}}' || true

echo "\n-- DB logs (last 300 lines) --"
${COMPOSE_CMD} -f "${COMPOSE_FILE}" logs --tail=300 ${DB_SERVICE} 2>/dev/null || docker logs "${TARGET_CONT}" --tail=300 2>/dev/null || true

echo "\n-- Host data dir listing --"
ls -la "${MARIADB_DIR}" 2>/dev/null || warn "Could not list ${MARIADB_DIR}"
echo "\n-- Host data dir sizes --"
du -h --max-depth=1 "${MARIADB_DIR}" 2>/dev/null || true

echo "\n-- Container /var/lib/mysql listing --"
${COMPOSE_CMD} -f "${COMPOSE_FILE}" exec -T ${DB_SERVICE} sh -lc 'ls -la /var/lib/mysql || true' 2>/dev/null || true

echo "\n-- Container MariaDB version & uname --"
${COMPOSE_CMD} -f "${COMPOSE_FILE}" exec -T ${DB_SERVICE} sh -lc 'mysqld --version || mariadbd --version || mysql --version || true' 2>/dev/null || true
${COMPOSE_CMD} -f "${COMPOSE_FILE}" exec -T ${DB_SERVICE} sh -lc 'uname -a || true' 2>/dev/null || true

echo "\n-- Error log inside container (if present) --"
${COMPOSE_CMD} -f "${COMPOSE_FILE}" exec -T ${DB_SERVICE} sh -lc 'ERR=$(ls /var/lib/mysql/*.err 2>/dev/null | head -n1); if [ -n "$ERR" ]; then echo "Reading $ERR"; tail -n 200 "$ERR"; else echo "No *.err file found"; fi' 2>/dev/null || true

echo "\n-- Pattern detection in logs --"
DB_LOGS_TMP=$(mktemp)
${COMPOSE_CMD} -f "${COMPOSE_FILE}" logs --tail=500 ${DB_SERVICE} 2>/dev/null > "$DB_LOGS_TMP" || docker logs "${TARGET_CONT}" --tail=500 2>/dev/null > "$DB_LOGS_TMP" || true
if [[ -s "$DB_LOGS_TMP" ]]; then
  grep -niE 'Bad magic header in tc log|Access denied for user|Permission denied|InnoDB: .*(error|corrupt|fail)|mysqld:.*error|Aborting|Fatal error|plugin.*unix_socket|Out of memory|io_uring|memory.pressure' "$DB_LOGS_TMP" || echo "No critical patterns matched"
else
  echo "No logs captured"
fi
rm -f "$DB_LOGS_TMP" 2>/dev/null || true

echo "\n-- Healthcheck recent results (if available) --"
docker inspect --format '{{if .State.Health}}{{range .State.Health.Log}}{{println .End .ExitCode .Output}}{{end}}{{else}}no health log{{end}}' "${TARGET_CONT}" 2>/dev/null | tail -n 10 || true

echo "\n-- Recommendations (heuristic) --"
DB_LOGS_TMP=$(mktemp)
${COMPOSE_CMD} -f "${COMPOSE_FILE}" logs --tail=500 ${DB_SERVICE} 2>/dev/null > "$DB_LOGS_TMP" || docker logs "${TARGET_CONT}" --tail=500 2>/dev/null > "$DB_LOGS_TMP" || true
if grep -qi 'Bad magic header in tc log' "$DB_LOGS_TMP"; then
  echo "- Detected tc.log corruption. Remove ${MARIADB_DIR}/tc.log and restart db."
fi
if grep -qi 'Access denied for user' "$DB_LOGS_TMP"; then
  echo "- Detected auth failures. Check .env DB_USER/DB_PASSWORD vs initialized data-dir."
fi
if grep -qi 'Permission denied' "$DB_LOGS_TMP"; then
  echo "- Permission issue on data-dir. Verify ownership on ${MARIADB_DIR} and that WSL/Docker can write."
fi
if grep -qiE 'InnoDB: .*corrupt|InnoDB: .*log.*error' "$DB_LOGS_TMP"; then
  echo "- InnoDB redo log corruption suspected. Consider removing ib_logfile0/1 and restarting."
fi
rm -f "$DB_LOGS_TMP" 2>/dev/null || true

echo "\n============================================================"
echo "End of diagnostic. Please copy-paste this entire output back here."