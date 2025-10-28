#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="aserras-frontend.service"

systemctl daemon-reload
systemctl restart "${SERVICE_NAME}"
systemctl status "${SERVICE_NAME}" --no-pager
