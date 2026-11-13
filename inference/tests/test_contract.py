import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import app, ExtractResponse

client = TestClient(app)

def test_health():
    assert client.get('/health/live').status_code == 200

def test_contract():
    r = ExtractResponse(fall_status='absent', evidence={'fall_status':'転倒なし'})
    assert r.model_dump()['fall_status'] == 'absent'

def test_empty_payload_is_rejected():
    assert client.post('/v1/extract', json={'narrative':''}).status_code == 422


def test_evidence_guard_abstains_if_source_quote_missing(monkeypatch):
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
    assert response.json()['fall_status'] == 'unknown'
    assert response.json()['evidence'] == {}
