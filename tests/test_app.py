import base64
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_dummy_secret")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_dummy_secret")
os.environ.setdefault("STRIPE_PRICE_PRO", "price_test_pro")
os.environ.setdefault("STRIPE_PRICE_ENTERPRISE", "price_test_enterprise")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402

client = TestClient(app)


def _build_jwt(payload: dict[str, str]) -> str:
    header = {"alg": "none", "typ": "JWT"}

    def _encode(segment: dict[str, str]) -> str:
        return (
            base64.urlsafe_b64encode(json.dumps(segment).encode("utf-8")).decode("utf-8").rstrip("=")
        )

    return f"{_encode(header)}.{_encode(payload)}."


def test_primary_pages_render():
    paths = [
        '/',
        '/about',
        '/contact',
        '/pricing',
        '/upgrade',
        '/chat',
        '/login',
        '/signup',
        '/dashboard',
    ]

    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        assert 'text/html' in response.headers.get('content-type', '')


def test_static_assets_served():
    response = client.get('/static/css/style.css')
    assert response.status_code == 200
    assert 'text/css' in response.headers.get('content-type', '')
    assert '.site-header' in response.text


def test_service_files_available():
    robots = client.get('/robots.txt')
    sitemap = client.get('/sitemap.xml')

    assert robots.status_code == 200
    assert 'User-agent' in robots.text

    assert sitemap.status_code == 200
    assert '<urlset' in sitemap.text


def test_health_endpoint():
    response = client.get('/health')

    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_create_checkout_session_requires_auth():
    response = client.post("/api/payments/create-checkout-session", json={"plan": "pro"})
    assert response.status_code == 401


def test_create_checkout_session_success():
    class DummySession:
        url = "https://stripe.example/checkout"

    token = _build_jwt({"email": "user@example.com"})

    with patch(
        "app.routers.payments.stripe.checkout.Session.create",
        return_value=DummySession(),
    ) as mock_create:
        response = client.post(
            "/api/payments/create-checkout-session",
            json={"plan": "pro"},
            headers={"Authorization": f"Bearer {token}"},
        )

    assert response.status_code == 201
    body = response.json()
    assert body == {"url": "https://stripe.example/checkout"}

    assert mock_create.called
    _, kwargs = mock_create.call_args
    assert kwargs["line_items"][0]["price"] == "price_test_pro"
    assert kwargs["metadata"]["email"] == "user@example.com"


def test_subscription_status_defaults_to_free():
    token = _build_jwt({"email": "status@example.com"})
    response = client.get(
        "/api/payments/subscription-status",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"plan": "free"}


def test_webhook_updates_subscription_plan():
    email = "subscriber@example.com"
    token = _build_jwt({"email": email})

    event_payload = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "metadata": {"email": email, "plan": "pro"},
            }
        },
    }

    with patch(
        "app.routers.payments.stripe.Webhook.construct_event",
        return_value=event_payload,
    ):
        response = client.post(
            "/api/payments/webhook",
            data=json.dumps({}),
            headers={"stripe-signature": "test"},
        )

    assert response.status_code == 200

    status_response = client.get(
        "/api/payments/subscription-status",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert status_response.status_code == 200
    assert status_response.json() == {"plan": "pro"}


def test_payment_intent_unknown_plan():
    response = client.post('/api/payment/intent', json={'plan_id': 'unknown'})
    assert response.status_code == 404


def test_payment_intent_success():
    class DummyIntent:
        id = 'pi_dummy'
        status = 'requires_payment_method'
        client_secret = 'pi_dummy_secret'

    with patch('app.stripe.PaymentIntent.create', return_value=DummyIntent()):
        response = client.post('/api/payment/intent', json={'plan_id': 'pro'})

    assert response.status_code == 200
    assert response.json() == {'client_secret': 'pi_dummy_secret'}


def test_payment_selftest_reports_env():
    with patch('app.stripe.Balance.retrieve', return_value={'available': []}):
        response = client.get('/api/payment/selftest')

    assert response.status_code == 200
    payload = response.json()
    assert payload['env']['STRIPE_SECRET_KEY'] is True
def test_login_page_mentions_dashboard_redirect():
    response = client.get('/login')
    assert response.status_code == 200
    body = response.text
    assert 'window.ASERRAS_CONFIG' in body
    assert 'https://core.aserras.com/api/auth/login' in body
    assert '/dashboard' in body
