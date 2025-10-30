import os
import sys
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_dummy_secret")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_dummy_secret")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402

client = TestClient(app)


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
