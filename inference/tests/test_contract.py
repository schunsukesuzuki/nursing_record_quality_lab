import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import app, ExtractResponse

client = TestClient(app)

def test_health():
    assert client.get('/health/live').status_code == 200

def test_contract():
    r = ExtractResponse(fall_status='absent', dizziness_status='unknown', assistance_status='unknown', evidence={'fall_status':'転倒なし'})
    assert r.model_dump()['fall_status'] == 'absent'

def test_empty_payload_is_rejected():
    assert client.post('/v1/extract', json={'narrative':''}).status_code == 422


def test_adapter_preserves_reported_status_for_backend_validation(monkeypatch):
    import json
    import httpx
    import app.main as main
    real_client = httpx.AsyncClient

    def handler(request):
        assert request.url.path == '/api/chat'
        proposed = {
            'fall_status': 'present', 'dizziness_status':'unknown', 'assistance_status':'unknown',
            'evidence': {'fall_status':'転倒した'}
        }
        return httpx.Response(200, json={'message': {'content':json.dumps(proposed)}})

    monkeypatch.setattr(main.httpx, 'AsyncClient', lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    response = client.post('/v1/extract',json={'narrative':'血圧を測定した。'})
    assert response.status_code == 200
    assert response.json()['fall_status'] == 'present'
    assert response.json()['evidence']['fall_status'] == '転倒した'


def test_missing_status_is_not_silently_treated_as_unknown(monkeypatch):
    import json
    import httpx
    import app.main as main
    actual = httpx.AsyncClient
    def handler(request):
        return httpx.Response(200, json={'message':{'content':json.dumps({'fall_status':'absent'})}})
    monkeypatch.setattr(main.httpx, 'AsyncClient', lambda **kw: actual(transport=httpx.MockTransport(handler), **kw))
    response = client.post('/v1/extract', json={'narrative':'転倒なし。'})
    assert response.status_code == 502
    assert response.json()['detail']['code'] == 'invalid_model_output'
