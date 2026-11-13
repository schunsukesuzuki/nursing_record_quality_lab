import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import app
from app.rules import baseline_extract, verify_llm_extraction
from app.schemas import NarrativeExtraction

client = TestClient(app)
NOTE = '10:30 歩行時ふらつきあり。移乗時は看護師が介助。転倒は認めず。'
BODY = {'record':{'fall_status':'unknown','dizziness_status':'present','assistance_status':'present'},
        'narrative':NOTE,'use_llm':True}

def test_llm_missing_evidence_rule_can_corroborate():
    baseline = baseline_extract(NOTE)
    raw = NarrativeExtraction(fall_status='absent', dizziness_status='present', assistance_status='present')
    verified, checks = verify_llm_extraction(NOTE, raw, baseline)
    assert verified.fall_status == 'absent'
    assert verified.evidence['fall_status'] == '転倒は認めず'
    assert all(v == 'rule_supported' for v in checks.values())

def test_model_unknown_must_remain_unknown():
    baseline = baseline_extract(NOTE)
    raw = NarrativeExtraction()
    verified, checks = verify_llm_extraction(NOTE, raw, baseline)
    assert verified.fall_status == 'unknown'
    assert checks['fall_status'] == 'model_unknown'

def test_unverified_hallucination_abstains():
    note = '血圧を測定した。'
    baseline = baseline_extract(note)
    raw = NarrativeExtraction(fall_status='present', evidence={'fall_status':'転倒あり'})
    verified, checks = verify_llm_extraction(note, raw, baseline)
    assert verified.fall_status == 'unknown'
    assert checks['fall_status'] == 'unverified_quote'

def test_disagreement_abstains():
    baseline = baseline_extract(NOTE)
    raw = NarrativeExtraction(fall_status='present', evidence={'fall_status':'転倒は認めず'})
    verified, checks = verify_llm_extraction(NOTE, raw, baseline)
    assert verified.fall_status == 'unknown'
    assert checks['fall_status'] == 'rule_disagreement'

def test_api_displays_rule_candidates_when_model_abstains(monkeypatch):
    import app.main as main
    async def fake_extract(_, prompt_variant="semantic"):
        return NarrativeExtraction()
    monkeypatch.setattr(main, 'extract', fake_extract)
    data = client.post('/api/audit', json=BODY).json()
    assert data['source'] == 'llm'
    assert len(data['flags']) == 0
    assert len(data['baseline_flags']) == 1
    assert data['baseline_flags'][0]['field'] == 'fall_status'
    assert data['evidence_checks']['fall_status'] == 'model_unknown'
    assert data['raw_extraction']['fall_status'] == 'unknown'

def test_api_corroborated_model_retains_flag(monkeypatch):
    import app.main as main
    async def fake_extract(_, prompt_variant="semantic"):
        return NarrativeExtraction(fall_status='absent', dizziness_status='present', assistance_status='present')
    monkeypatch.setattr(main, 'extract', fake_extract)
    data = client.post('/api/audit', json=BODY).json()
    assert len(data['flags']) == 1
    assert data['flags'][0]['evidence'] == '転倒は認めず'
    assert data['evidence_checks']['fall_status'] == 'rule_supported'
