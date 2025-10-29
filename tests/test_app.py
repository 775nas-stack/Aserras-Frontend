import sys
from pathlib import Path

from fastapi.testclient import TestClient

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
    assert response.json() == {"status": "ok"}


def test_login_flow_success():
    response = client.post(
        '/api/auth/login',
        json={'email': 'visionary@example.com', 'password': 'supersecure'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ok'
    assert payload['user']['email'] == 'visionary@example.com'
    assert payload['redirect'] == '/dashboard'


def test_signup_requires_password_length():
    response = client.post(
        '/api/auth/signup',
        json={
            'fullName': 'Alex Visionary',
            'email': 'alex@example.com',
            'password': 'short',
        },
    )

    assert response.status_code == 400


def test_chat_flow_records_history():
    before = client.get('/api/user/history')
    assert before.status_code == 200
    before_len = len(before.json().get('messages', []))

    response = client.post('/api/chat/send', json={'message': 'Hello from the test suite!'})
    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ok'
    assert payload['reply']

    after = client.get('/api/user/history')
    assert after.status_code == 200
    after_len = len(after.json().get('messages', []))
    assert after_len >= before_len + 2


def test_contact_endpoint_returns_reference():
    response = client.post(
        '/api/contact/send',
        json={'name': 'QA', 'email': 'qa@example.com', 'message': 'Ping'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['status'] == 'ok'
    assert payload['reference']
