from pathlib import Path
import sys

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
