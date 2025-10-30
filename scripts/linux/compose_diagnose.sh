#!/usr/bin/env bash
set -euo pipefail

# Compose path diagnostic — helps explain "no such file or directory" errors
# Usage: ./compose_diagnose.sh [/absolute/path/to/docker-compose.yml]

TARGET_PATH="${1:-/dados/votebem/docker-compose.yml}"
ALT_PATH="/tmp/compose-diagnose.yml"

log()  { echo -e "[INFO]  $*"; }
warn() { echo -e "[WARN]  $*"; }
err()  { echo -e "[ERROR] $*" >&2; }
hr()   { echo "========================================================================"; }
section() { hr; echo "# $*"; hr; }

strip_cr() { printf '%s' "$1" | tr -d '\r'; }
safe_q() { printf '%q' "$1"; }

section "Environment"
log "User: $(id -un) (uid=$(id -u)) Groups: $(id -Gn)"
log "Shell: $SHELL"
log "Uname: $(uname -a)"
if [[ -f /etc/os-release ]]; then
  log "OS: $(. /etc/os-release; echo "$NAME $VERSION")"
fi
if grep -qi microsoft /proc/version 2>/dev/null; then
  warn "WSL environment detected (Microsoft kernel string present)."
fi

section "Docker Binaries"
DOCKER_BIN="$(command -v docker || true)"
COMPOSE_BIN="$(command -v docker-compose || true)"
log "docker: ${DOCKER_BIN:-not found}"
log "docker-compose: ${COMPOSE_BIN:-not found}"
if [[ -n "${DOCKER_BIN}" ]]; then
  DOCKER_FILE_DESC="$(file "${DOCKER_BIN}" 2>/dev/null || echo unknown)"
  log "docker file type: ${DOCKER_FILE_DESC}"
fi
if docker compose version >/dev/null 2>&1; then
  log "docker compose plugin: $(docker compose version | head -n1)"
else
  warn "docker compose plugin not available."
fi
if docker-compose version >/dev/null 2>&1; then
  log "legacy docker-compose: $(docker-compose version | head -n1)"
fi
if docker version >/dev/null 2>&1; then
  docker version | sed 's/^/  /'
else
  warn "docker client not responding; daemon may be unavailable."
fi

IS_WINDOWS_DOCKER=false
if [[ -n "${DOCKER_FILE_DESC:-}" ]] && ([[ "${DOCKER_FILE_DESC}" == *PE32* ]] || [[ "${DOCKER_BIN}" == *.exe ]]); then
  IS_WINDOWS_DOCKER=true
  warn "docker appears to be a Windows executable invoked via WSL interop."
  warn "Windows docker.exe cannot open WSL Linux paths like ${TARGET_PATH}."
  warn "Enable Docker Desktop WSL integration for this distro, or use Linux docker within WSL."
fi

section "Path Inspection"
RAW_TARGET="${TARGET_PATH}"
CR_STRIPPED_TARGET="$(strip_cr "${TARGET_PATH}")"
log "Raw path: [${RAW_TARGET}]"
log "Quoted path: $(safe_q "${RAW_TARGET}")"
log "Bytes (hex) of raw path: $(echo -n "${RAW_TARGET}" | od -An -t x1 | tr -s ' ')"
if [[ "${RAW_TARGET}" != "${CR_STRIPPED_TARGET}" ]]; then
  warn "Carriage return detected in path; sanitized path: [${CR_STRIPPED_TARGET}]"
fi

for P in "${RAW_TARGET}" "${CR_STRIPPED_TARGET}"; do
  echo
  log "Stat for: ${P}"
  if [[ -e "${P}" ]]; then
    ls -la "${P}" | sed 's/^/  /'
    if command -v stat >/dev/null 2>&1; then
      stat "${P}" | sed 's/^/  /'
    fi
    if command -v readlink >/dev/null 2>&1; then
      RL="$(readlink -f "${P}" 2>/dev/null || true)"; [[ -n "${RL}" ]] && log "Resolved: ${RL}"
    fi
    if command -v df >/dev/null 2>&1; then
      df -T "${P}" | sed 's/^/  /'
    fi
    head -n 3 "${P}" | sed 's/^/  > /'
  else
    err "File does not exist: ${P}"
  fi
done

section "Copy to /tmp and inspect"
cp -f "${CR_STRIPPED_TARGET}" "${ALT_PATH}" 2>/dev/null || true
if [[ -f "${ALT_PATH}" ]]; then
  log "Copied to ${ALT_PATH}"
  ls -la "${ALT_PATH}" | sed 's/^/  /'
  head -n 3 "${ALT_PATH}" | sed 's/^/  > /'
else
  warn "Failed to copy to ${ALT_PATH}; permissions or source missing."
fi

section "Compose Parsing Trials"
set +e
OUT1="$(docker compose -f "${CR_STRIPPED_TARGET}" config 2>&1)"; RC1=$?
echo "docker compose -f ${CR_STRIPPED_TARGET} config => rc=${RC1}"; echo "${OUT1}" | sed 's/^/  /'
OUT2="$(docker compose -f "${ALT_PATH}" config 2>&1)"; RC2=$?
echo "docker compose -f ${ALT_PATH} config => rc=${RC2}"; echo "${OUT2}" | sed 's/^/  /'
if command -v docker-compose >/dev/null 2>&1; then
  OUT3="$(docker-compose -f "${CR_STRIPPED_TARGET}" config 2>&1)"; RC3=$?
  echo "docker-compose -f ${CR_STRIPPED_TARGET} config => rc=${RC3}"; echo "${OUT3}" | sed 's/^/  /'
  OUT4="$(docker-compose -f "${ALT_PATH}" config 2>&1)"; RC4=$?
  echo "docker-compose -f ${ALT_PATH} config => rc=${RC4}"; echo "${OUT4}" | sed 's/^/  /'
fi
set -e

section "Python open() sanity"
export RAW_TARGET="${RAW_TARGET}"
export CR_STRIPPED_TARGET="${CR_STRIPPED_TARGET}"
export ALT_PATH="${ALT_PATH}"
python3 - <<PY 2>&1 | sed 's/^/  /'
import os, sys
paths = [os.environ.get('RAW_TARGET'), os.environ.get('CR_STRIPPED_TARGET'), os.environ.get('ALT_PATH')]
for p in paths:
    if not p:
        continue
    print(f"Trying to open: {p}")
    try:
        with open(p, 'rb') as f:
            data = f.read(64)
        print(f"  OK, first 64 bytes: {data[:32]!r}… size={len(data)}")
    except Exception as e:
        print(f"  FAILED: {e}")
PY

section "Summary"
if [[ "${IS_WINDOWS_DOCKER}" == true ]]; then
  warn "docker is a Windows executable in WSL; Linux paths cannot be opened by it."
  warn "Fix: Enable Docker Desktop WSL integration for this distro or use Linux docker inside WSL."
fi
if [[ ! -f "${CR_STRIPPED_TARGET}" ]]; then
  err "Primary compose file missing at: ${CR_STRIPPED_TARGET}"
else
  log "Primary compose file exists at: ${CR_STRIPPED_TARGET}"
fi
if [[ -f "${ALT_PATH}" ]]; then
  log "Temp compose file present at: ${ALT_PATH}"
else
  warn "Temp compose file not present at: ${ALT_PATH}"
fi
hr