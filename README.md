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

The setup helper performs a clean clone into `/var/www/`, provisions a fresh
virtual environment, installs `requirements.txt`, and ensures the
`aserras-frontend` systemd unit is enabled and running. Because it always
targets the canonical clone path, running it on a freshly provisioned host
results in the same layout and permissions every time.

### Updating a running deployment

After pulling new application code:

```bash
sudo bash deploy/reload.sh
```

This helper fetches the latest `origin/main`, force-syncs the working tree,
rebuilds the `.venv`, and restarts the FastAPI service so new code and
dependencies land atomically.

### nginx + systemd assets

* `deploy/systemd/aserras-frontend.service` – runs Uvicorn from the repo’s
  `.venv`, binds to port 8080, writes logs to `/var/log/aserras/`, and loads any
  secrets from `.env`.
* `deploy/nginx/aserras.com` – proxies application traffic to Uvicorn and
  serves `/static/` directly for maximal performance.
* `deploy/setup.sh` – one-shot bootstrapper for cloning, virtualenv creation,
  dependency installation, and service enablement.
* `deploy/reload.sh` – repeatable helper that syncs `origin/main`, rebuilds the
  environment, and restarts the service.

## Tests

Basic smoke tests confirm that the most important routes render without errors:

```bash
pytest
```

The smoke suite exercises all critical marketing routes plus static asset
delivery. Run it before commits or deployments to confirm the application and
asset pipeline remain healthy.
