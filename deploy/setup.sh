#!/bin/bash
# === Initial setup for Aserras Frontend ===
cd /var/www || exit
git clone git@github.com-frontend:775nas-stack/Aserras-Frontend.git
cd Aserras-Frontend

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
deactivate

# enable and start the FastAPI service
systemctl enable aserras-frontend
systemctl restart aserras-frontend
