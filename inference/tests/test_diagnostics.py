import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from fastapi.testclient import TestClient
import app.main as main

client = TestClient(main.app)

def install_transport(monkeypatch, handler):
    actual = httpx.AsyncClient
    monkeypatch.setattr(main.httpx, 'AsyncClient', lambda **opts: actual(transport=httpx.MockTransport(handler), **opts))

def test_ready_when_model_installed(monkeypatch):
    install_transport(monkeypatch, lambda request: httpx.Response(200, json={'models':[{'name':main.MODEL_NAME}]}))
    response = client.get('/health/ready')
    assert response.status_code == 200
    assert response.json()['model'] == main.MODEL_NAME

def test_ready_when_model_missing(monkeypatch):
    install_transport(monkeypatch, lambda request: httpx.Response(200, json={'models':[]}))
    response = client.get('/health/ready')
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'model_not_found'

def test_ready_when_ollama_down(monkeypatch):
    def fail(request):
        raise httpx.ConnectError('offline', request=request)
    install_transport(monkeypatch, fail)
    response = client.get('/health/ready')
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'ollama_unreachable'

def test_ollama_oom_returns_actionable_code(monkeypatch):
    install_transport(monkeypatch, lambda request: httpx.Response(500, json={'error':'not included in output'}))
    response = client.post('/v1/extract', json={'narrative':'架空の記録'})
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'model_runtime_error'
    assert 'not included in output' not in response.text

def test_model_bad_json_returns_clear_error(monkeypatch):
    install_transport(monkeypatch, lambda request: httpx.Response(200, json={'message':{'content':'not json'}}))
    response = client.post('/v1/extract', json={'narrative':'架空の記録'})
    assert response.status_code == 502
    assert response.json()['detail']['code'] == 'invalid_model_output'

def test_model_timeout_returns_clear_error(monkeypatch):
    def fail(request):
        raise httpx.ReadTimeout('timeout', request=request)
    install_transport(monkeypatch, fail)
    response = client.post('/v1/extract', json={'narrative':'架空の記録'})
    assert response.status_code == 504
    assert response.json()['detail']['code'] == 'model_timeout'
