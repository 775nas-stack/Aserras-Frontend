# Aserras Frontend

Modern FastAPI + Jinja application that delivers the full Aserras user experience.
The frontend authenticates against **Aserras Brain**, proxies all AI workloads
(text, image, automation), and renders a responsive dashboard powered by
TailwindCSS.

## Project structure

```
├── app/
│   ├── main.py            # Application factory, middleware, exception handling
│   ├── settings.py        # Environment-aware configuration
│   ├── routers/           # Route modules (home, auth, chat, image, code, history, settings)
│   ├── services/          # Brain API client abstraction
│   ├── dependencies/      # Authentication helpers and shared dependencies
│   ├── templates/         # Jinja templates for pages and workspaces
│   └── static/            # CSS, JS, sitemap, robots, and other assets
├── app.py                 # Compatibility export for `uvicorn app:app`
├── config.py              # Backwards-compatible re-export of Settings helpers
├── deploy/                # Systemd + nginx configuration and helper scripts
├── requirements.txt       # Python dependencies
└── tests/                 # Smoke tests for routes and APIs
```

## Requirements

Install the dependencies listed in `requirements.txt`:

```
aiofiles
fastapi
httpx
jinja2
openai
pydantic-settings
python-dotenv
python-multipart
uvicorn[standard]
```

## Local development

1. (Optional) create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the application with Uvicorn:
   ```bash
   uvicorn app:app --reload
   ```
4. Visit `http://localhost:8000` to access the landing page, login, dashboard,
   and all workspaces.

The application expects the Brain API to be reachable at the URL defined by the
`ASERRAS_BRAIN_API_URL` environment variable (defaults to
`https://brain.aserras.com`).

## Deployment

Production hosts consume the assets inside `deploy/`:

* `deploy/systemd/aserras-frontend.service` – runs Uvicorn behind systemd.
* `deploy/nginx/` – nginx site configuration that proxies to Uvicorn and serves
  static assets efficiently.
* `deploy/setup.sh` – one-shot bootstrapper that clones the repo, builds a
  virtualenv, installs dependencies, and enables the systemd service.
* `deploy/reload.sh` – repeatable helper to pull, reinstall, and restart in
  place.

## Tests

Run the FastAPI smoke tests before committing or deploying:

```bash
pytest
```

The suite verifies public pages, protected routes, API authentication, and
static/service file delivery.
