from pathlib import Path
import sys

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app  # noqa: E402

client = TestClient(app)


def test_public_pages_render():
    paths = [
        '/',
        '/login',
        '/signup',
        '/pricing',
        '/about',
        '/contact',
    ]

    for path in paths:
        response = client.get(path)
        assert response.status_code == 200, path
        assert 'text/html' in response.headers.get('content-type', '')


def test_protected_pages_require_authentication():
    secure_paths = ['/chat', '/image', '/code', '/history', '/dashboard']
    for path in secure_paths:
        response = client.get(path, follow_redirects=False)
        assert response.status_code in (401, 303, 307)


def test_health_endpoint():
    response = client.get('/health')
    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_static_assets_and_service_files():
    css_response = client.get('/static/css/style.css')
    assert css_response.status_code == 200

    robots = client.get('/robots.txt')
    assert robots.status_code == 200
    assert 'User-agent' in robots.text

    sitemap = client.get('/sitemap.xml')
    assert sitemap.status_code == 200
    assert '<urlset' in sitemap.text


def test_chat_api_requires_authentication():
    response = client.post('/api/chat', json={'prompt': 'hello'})
    assert response.status_code == 401
