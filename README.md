# Aserras Frontend

Static marketing site and chat UI for the Aserras platform served through a FastAPI
application. The project exposes multiple marketing pages, authentication flows,
and a chat workspace rendered with Jinja templates.

## Project structure

```
├── app.py              # FastAPI application factory and routes
├── config.py           # Environment aware settings using pydantic-settings
├── deploy/             # Systemd + nginx configs and setup scripts
├── static/             # Compiled assets (CSS, JS, sitemap, robots)
├── templates/          # Jinja templates for every page and error view
└── tests/              # FastAPI smoke tests for the main routes
```

## Requirements

The app depends on FastAPI plus Starlette's optional `aiofiles` package so static
assets can be streamed correctly. All dependencies are listed in
`requirements.txt`:

```
aiofiles
fastapi
jinja2
openai
pydantic-settings
python-dotenv
uvicorn[standard]
```

## Local development

1. Create and activate a virtual environment (optional).
2. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application with Uvicorn:
   ```bash
   uvicorn app:app --reload
   ```
4. Visit `http://localhost:8000` to browse the marketing pages and chat UI.

## Deployment

The `deploy/` directory mirrors the production environment that is currently
running on the Aserras server. Everything required to stand up the application
after a fresh clone — systemd unit, nginx site configuration, and helper
scripts — ships with the repository so nothing is lost on future redeploys.

### System prerequisites

* Ubuntu 22.04 LTS (or compatible systemd-based distro)
* Python 3.10+
* nginx installed and enabled
* `aserras` (or your chosen) service user with access to `/opt/aserras-frontend`

### One-time bootstrap

> **Run as root (or with sudo)** so system packages, logs, and services can be
> configured without manual intervention.

```bash
sudo bash deploy/setup.sh
```

The script performs the following idempotent actions:

1. Creates `.venv/` if it does not exist and installs `requirements.txt`.
2. Ensures `/var/log/aserras/` exists with permissions for the service user.
3. Copies `deploy/aserras-frontend.service` into
   `/etc/systemd/system/aserras-frontend.service`, preserving an on-server copy
   if it already differs, then enables and starts the service.
4. Publishes the nginx site definition at
   `/etc/nginx/sites-available/aserras.com.conf`, symlinks it into
   `sites-enabled/`, validates the configuration, and reloads nginx.

The service and nginx manifests are rewritten on the fly to match the current
repository path (or an overridden `APP_ROOT`) so recloning into a different
directory never breaks the runtime configuration.

All operations are safe to re-run. Existing, modified service definitions are
backed up with a `.bak` suffix so manual overrides are never lost.

Environment specific overrides can be supplied by exporting variables when
invoking the script:

```bash
sudo APP_USER=ubuntu APP_PORT=9000 bash deploy/setup.sh
```

`APP_ROOT` defaults to the path you run the script from, keeping the systemd
unit aligned with the actual clone.

### Updating a running deployment

After pulling new application code:

```bash
sudo bash deploy/reload.sh
```

This reloads the systemd unit (in case the service file changed), restarts the
FastAPI process, and prints the latest status for quick verification.

### nginx + systemd assets

* `deploy/aserras-frontend.service` – runs Uvicorn from the repo’s `.venv`,
  binds to port 8080, writes logs to `/var/log/aserras/`, and loads any secrets
  from `.env`.
* `deploy/nginx/aserras.com.conf` – proxies application traffic to Uvicorn and
  serves `/static/` directly for maximal performance.
* `deploy/setup.sh` – idempotent bootstrapper to provision Python packages,
  systemd, and nginx.
* `deploy/reload.sh` – lightweight helper for restarts during updates.

## Tests

Basic smoke tests confirm that the most important routes render without errors:

```bash
pytest
```

The smoke suite exercises all critical marketing routes plus static asset
delivery. Run it before commits or deployments to confirm the application and
asset pipeline remain healthy.
