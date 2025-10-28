#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
DEFAULT_APP_ROOT="${APP_ROOT:-${PROJECT_ROOT}}"
DEFAULT_APP_USER="${APP_USER:-aserras}"
DEFAULT_APP_PORT="${APP_PORT:-8080}"
LOG_DIR="${LOG_DIR:-/var/log/aserras}"
SERVICE_NAME="aserras-frontend.service"
SERVICE_PATH="/etc/systemd/system/${SERVICE_NAME}"
NGINX_SITE_AVAILABLE="/etc/nginx/sites-available/aserras.com.conf"
NGINX_SITE_ENABLED="/etc/nginx/sites-enabled/aserras.com.conf"

SERVICE_TEMPLATE="${SCRIPT_DIR}/aserras-frontend.service"
NGINX_TEMPLATE="${SCRIPT_DIR}/nginx/aserras.com.conf"
TEMP_SERVICE=$(mktemp)
TEMP_NGINX=$(mktemp)
trap 'rm -f "${TEMP_SERVICE}" "${TEMP_NGINX}"' EXIT

cp "${SERVICE_TEMPLATE}" "${TEMP_SERVICE}"
cp "${NGINX_TEMPLATE}" "${TEMP_NGINX}"

if [[ "${DEFAULT_APP_ROOT}" != "/opt/aserras-frontend" ]]; then
  sed -i "s|/opt/aserras-frontend|${DEFAULT_APP_ROOT}|g" "${TEMP_SERVICE}"
  sed -i "s|/opt/aserras-frontend|${DEFAULT_APP_ROOT}|g" "${TEMP_NGINX}"
fi

if [[ "${DEFAULT_APP_USER}" != "aserras" ]]; then
  sed -i "s|User=aserras|User=${DEFAULT_APP_USER}|" "${TEMP_SERVICE}"
  sed -i "s|Group=aserras|Group=${DEFAULT_APP_USER}|" "${TEMP_SERVICE}"
fi

if [[ "${DEFAULT_APP_PORT}" != "8080" ]]; then
  sed -i "s|--port 8080|--port ${DEFAULT_APP_PORT}|" "${TEMP_SERVICE}"
  sed -i "s|http://127.0.0.1:8080|http://127.0.0.1:${DEFAULT_APP_PORT}|" "${TEMP_NGINX}"
fi

if [[ "${LOG_DIR}" != "/var/log/aserras" ]]; then
  sed -i "s|/var/log/aserras|${LOG_DIR}|g" "${TEMP_SERVICE}"
fi

function info() { echo "[setup] $*"; }

if ! id -u "${DEFAULT_APP_USER}" >/dev/null 2>&1; then
  info "Service user '${DEFAULT_APP_USER}' does not exist yet. Create it before running the service."
fi

info "Ensuring Python virtual environment exists"
if [[ ! -d "${PROJECT_ROOT}/.venv" ]]; then
  python3 -m venv "${PROJECT_ROOT}/.venv"
fi

info "Installing Python dependencies"
"${PROJECT_ROOT}/.venv/bin/pip" install --upgrade pip
"${PROJECT_ROOT}/.venv/bin/pip" install -r "${PROJECT_ROOT}/requirements.txt"

info "Preparing log directory at ${LOG_DIR}"
mkdir -p "${LOG_DIR}"
chown "${DEFAULT_APP_USER}:${DEFAULT_APP_USER}" "${LOG_DIR}" || true
chmod 750 "${LOG_DIR}"

info "Syncing systemd service"
if [[ ! -f "${SERVICE_PATH}" ]]; then
  install -o root -g root -m 0644 "${TEMP_SERVICE}" "${SERVICE_PATH}"
  SERVICE_UPDATED=1
else
  if ! cmp -s "${TEMP_SERVICE}" "${SERVICE_PATH}"; then
    cp "${SERVICE_PATH}" "${SERVICE_PATH}.bak"
    install -o root -g root -m 0644 "${TEMP_SERVICE}" "${SERVICE_PATH}"
    SERVICE_UPDATED=1
  else
    SERVICE_UPDATED=0
  fi
fi

if [[ ${SERVICE_UPDATED:-0} -eq 1 ]]; then
  info "Reloading systemd daemon"
  systemctl daemon-reload
fi

info "Enabling service"
systemctl enable --now "${SERVICE_NAME}"

info "Deploying nginx configuration"
mkdir -p "$(dirname "${NGINX_SITE_AVAILABLE}")" "$(dirname "${NGINX_SITE_ENABLED}")"
install -o root -g root -m 0644 "${TEMP_NGINX}" "${NGINX_SITE_AVAILABLE}"
if [[ -L "${NGINX_SITE_ENABLED}" ]]; then
  ln -sf "${NGINX_SITE_AVAILABLE}" "${NGINX_SITE_ENABLED}"
elif [[ -e "${NGINX_SITE_ENABLED}" ]]; then
  mv "${NGINX_SITE_ENABLED}" "${NGINX_SITE_ENABLED}.bak"
  ln -s "${NGINX_SITE_AVAILABLE}" "${NGINX_SITE_ENABLED}"
else
  ln -s "${NGINX_SITE_AVAILABLE}" "${NGINX_SITE_ENABLED}"
fi

info "Testing nginx configuration"
nginx -t

info "Reloading nginx"
systemctl reload nginx

cat <<SUMMARY

Deployment complete.
Service root: ${DEFAULT_APP_ROOT}
Service user: ${DEFAULT_APP_USER}
Uvicorn port: ${DEFAULT_APP_PORT}
Logs stored in ${LOG_DIR}
SUMMARY
