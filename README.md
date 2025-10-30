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
stripe
uvicorn[standard]
```

## Environment configuration

Create a `.env` file (not committed to git) or provide environment variables at
runtime. A template lives in `.env.example` so fresh clones can be configured
quickly:

| Variable | Description |
| --- | --- |
| `BRAIN_BASE` | Base URL for the upstream Brain/Core API. |
| `SERVICE_TOKEN` | Service token used when calling private Core APIs. |
| `ALLOWED_ORIGINS` | Comma separated list of origins allowed to call this API. Leave empty for local development. |
| `STRIPE_SECRET_KEY` | Stripe secret key (sk_...). Required for the API to boot. |
| `STRIPE_WEBHOOK_SECRET` | Secret used to verify Stripe webhooks. |
| `OPTIONAL_PAYPAL_ENABLED` | Enable experimental PayPal endpoints when set to `true`. |
| `OPTIONAL_PAYPAL_WEBHOOK_SECRET` | Reserved for future PayPal webhook validation. |

> **Note:** `.env` files should only exist on the server or in your local
> development environment. They are intentionally excluded from version control
> so recloning never leaks credentials.

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

## Payments API

The application exposes endpoints for Stripe's Payment Element and optional
PayPal stubs so the frontend can offer multiple payment methods out of the box.

### Create a Stripe PaymentIntent

```bash
curl -X POST http://localhost:8000/api/payment/intent \
  -H 'content-type: application/json' \
  -d '{"plan_id": "pro"}'
```

The response includes a `client_secret` that the frontend can feed directly into
Stripe's Payment Element. The backend automatically enables compatible payment
methods (Apple Pay / Google Pay via Payment Request Button) whenever Stripe
reports they are available.

### Webhook setup

Configure your Stripe webhook endpoint to deliver these events so both Checkout
Sessions and Payment Element flows stay in sync:

* `checkout.session.completed`
* `invoice.paid`
* `payment_intent.succeeded`

The webhook verifies requests with `STRIPE_WEBHOOK_SECRET` and records the latest
status in memory. Optional PayPal endpoints (`/api/paypal/order` and
`/api/paypal/capture`) become available only when `OPTIONAL_PAYPAL_ENABLED=true`
and currently return `501 Not Implemented` to signal future work.

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
