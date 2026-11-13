import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import app
from app.rules import baseline_extract,verify_llm_extraction
from app.schemas import NarrativeExtraction

client=TestClient(app)
NOTE='歩行中に身体が左右に揺れ、看護師が腕を支えた。床に倒れることはなかった。'

def test_paraphrase_baseline_abstains_by_design():
    res=baseline_extract(NOTE)
    assert res.fall_status=='unknown'
    assert res.dizziness_status=='unknown'
    assert res.assistance_status=='unknown'

def test_literal_quote_acceptance_is_not_semantic_validation():
    raw=NarrativeExtraction(fall_status='absent',dizziness_status='present',assistance_status='present',
        evidence={'fall_status':'床に倒れることはなかった','dizziness_status':'身体が左右に揺れ',
                  'assistance_status':'看護師が腕を支えた'})
    checked,reasons=verify_llm_extraction(NOTE,raw,baseline_extract(NOTE))
    assert all(reasons[f]=='quoted' for f in ['fall_status','dizziness_status','assistance_status'])
    assert checked.fall_status=='absent'

def test_response_keeps_raw_variant_and_accepted_distinct(monkeypatch):
    import app.main as main
    called=[]
    async def mocked(note, variant):
        called.append((note,variant))
        return NarrativeExtraction(fall_status='absent',dizziness_status='present',assistance_status='present')
    monkeypatch.setattr(main,'extract',mocked)
    resp=client.post('/api/audit',json={'narrative':NOTE,'record':{'fall_status':'unknown'},
                                         'prompt_variant':'few_shot','use_llm':True})
    assert resp.status_code==200
    data=resp.json()
    assert called==[(NOTE,'few_shot')]
    assert data['prompt_variant']=='few_shot'
    assert data['raw_extraction']['fall_status']=='absent'
    assert data['extraction']['fall_status']=='unknown'
    assert data['evidence_checks']['fall_status']=='missing_quote'


def test_invalid_prompt_variant_is_rejected_without_model_call():
    r=client.post('/api/audit',json={'record':{},'narrative':NOTE,'use_llm':False,'prompt_variant':'none'})
    assert r.status_code==422
