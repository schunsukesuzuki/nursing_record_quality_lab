import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import app, build_messages, FEW_SHOT_EXAMPLES

client=TestClient(app)
SAMPLE = '歩行中に身体が左右に揺れ、看護師が腕を支えた。床に倒れることはなかった。'

def test_semantic_defines_gait_and_excludes_vertigo():
    messages=build_messages('semantic', SAMPLE)
    assert len(messages) == 2
    assert '歩行不安定性' in messages[0]['content']
    assert 'めまいの自覚症状' in messages[0]['content']
    assert messages[-1]['content']==SAMPLE

def test_few_shot_examples_are_separate_messages():
    messages=build_messages('few_shot', SAMPLE)
    assert len(messages)==2+2*len(FEW_SHOT_EXAMPLES)
    assert messages[-1]['content']==SAMPLE
    for role in ('user','assistant'):
        assert role in [m['role'] for m in messages]
    example=json.loads(messages[2]['content'])
    assert example['fall_status']=='absent'
    assert all(quote in messages[1]['content'] for quote in example['evidence'].values())

def test_invalid_variant_is_rejected():
    assert client.post('/v1/extract', json={'narrative':SAMPLE,'prompt_variant':'invented'}).status_code==422


def test_mocked_ollama_uses_selected_prompt_and_schema(monkeypatch):
    import app.main as main
    import httpx
    actual = httpx.AsyncClient
    seen=[]
    def handler(req):
        data=json.loads(req.content)
        seen.append(data)
        answer={
            'fall_status':'absent', 'dizziness_status':'present','assistance_status':'present',
            'evidence':{
                'fall_status':'床に倒れることはなかった',
                'dizziness_status':'身体が左右に揺れ',
                'assistance_status':'看護師が腕を支えた',
            }
        }
        return httpx.Response(200,json={'message':{'content':json.dumps(answer,ensure_ascii=False)}})
    monkeypatch.setattr(main.httpx,'AsyncClient', lambda **kw: actual(transport=httpx.MockTransport(handler),**kw))
    for variant in ['basic','semantic','few_shot']:
        res=client.post('/v1/extract',json={'narrative':SAMPLE,'prompt_variant':variant})
        assert res.status_code==200
        assert res.json()['dizziness_status']=='present'
    assert len(seen)==3
    assert seen[0]['options']['temperature']==0
    assert len(seen[0]['messages'])==2
    assert len(seen[2]['messages'])>2
    assert seen[1]['format']['required']
