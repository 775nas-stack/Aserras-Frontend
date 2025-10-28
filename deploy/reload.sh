#!/bin/bash
# === Aserras Frontend Auto-Reload Script ===
cd /var/www/Aserras-Frontend || exit

echo "→ Pulling latest changes from GitHub..."
git fetch --all
git reset --hard origin/main

echo "→ Updating Python environment..."
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
deactivate

echo "→ Restarting FastAPI service..."
systemctl restart aserras-frontend

echo "✅ Frontend reloaded successfully!"
