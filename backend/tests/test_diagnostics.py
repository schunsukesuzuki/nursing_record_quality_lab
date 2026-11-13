import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import httpx
from fastapi.testclient import TestClient
import app.inference_client as ic
import app.main as main

client = TestClient(main.app)

def install_transport(monkeypatch, handler):
    actual = httpx.AsyncClient
    monkeypatch.setattr(ic.httpx, 'AsyncClient', lambda **opts: actual(transport=httpx.MockTransport(handler), **opts))

def test_status_when_ready(monkeypatch):
    install_transport(monkeypatch, lambda req: httpx.Response(200, json={'status':'ready', 'model':'qwen3:0.6b'}))
    response = client.get('/api/inference/status')
    assert response.status_code == 200
    assert response.json()['available'] is True

def test_status_when_model_missing(monkeypatch):
    install_transport(monkeypatch, lambda req: httpx.Response(503, json={'detail':{'code':'model_not_found', 'message':'foo'}}))
    response = client.get('/api/inference/status')
    assert response.status_code == 200
    assert response.json()['code'] == 'model_not_found'
    assert 'foo' not in response.text

def test_status_when_inference_down(monkeypatch):
    def fail(request):
        raise httpx.ConnectError('offline', request=request)
    install_transport(monkeypatch, fail)
    response = client.get('/api/inference/status')
    assert response.status_code == 200
    assert response.json()['code'] == 'inference_unreachable'

EXAMPLE = '転倒は認めず。'
BODY = {'record': {'fall_status':'unknown'}, 'narrative':EXAMPLE, 'use_llm':True}

def test_llm_error_message_reaches_ui(monkeypatch):
    install_transport(monkeypatch, lambda req: httpx.Response(503, json={'detail': {'code':'model_runtime_error', 'message':'sensitive detail'}}))
    response = client.post('/api/audit', json=BODY)
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'model_runtime_error'
    assert 'sensitive detail' not in response.text
