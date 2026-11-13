import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from app.main import app
from app.rules import baseline_extract, compare_record
from app.schemas import StructuredRecord

client = TestClient(app)

EXAMPLE = '歩行時ふらつきあり。移乗時は看護師が介助。転倒は認めず。'

def test_baseline_extract():
    result = baseline_extract(EXAMPLE)
    assert result.fall_status == 'absent'
    assert result.dizziness_status == 'present'
    assert result.assistance_status == 'present'

def test_missing_is_not_absent():
    observed = baseline_extract('転倒は認めず。')
    flags = compare_record(StructuredRecord(fall_status='unknown'), observed, 'rule')
    assert len(flags) == 1
    assert flags[0].kind == 'missing_structured'
    assert flags[0].observed == 'absent'

def test_conflict():
    observed = baseline_extract('転倒した。')
    flags = compare_record(StructuredRecord(fall_status='absent'), observed, 'rule')
    assert flags[0].kind == 'conflict'

def test_ambiguous_abstains():
    assert baseline_extract('転倒したが、現在は転倒なし。').fall_status == 'unknown'

def test_api_rule_only():
    response = client.post('/api/audit', json={'record': {'fall_status': 'unknown', 'dizziness_status': 'present', 'assistance_status':'present'},
                                               'narrative': EXAMPLE, 'use_llm': False})
    assert response.status_code == 200
    result = response.json()
    assert result['source'] == 'rule'
    assert len(result['flags']) == 1
    assert result['flags'][0]['field'] == 'fall_status'

def test_validation_rejects_extra_field():
    response = client.post('/api/audit', json={'record': {'patient_name': 'X'}, 'narrative': EXAMPLE,'use_llm':False})
    assert response.status_code == 422


def test_api_llm_contract_without_real_model(monkeypatch):
    import app.main as main
    from app.schemas import NarrativeExtraction

    async def fake_extract(_note: str, prompt_variant="semantic"):
        return NarrativeExtraction(
            fall_status='absent', dizziness_status='present', assistance_status='present',
            evidence={'fall_status':'転倒は認めず'}
        )

    monkeypatch.setattr(main, 'extract', fake_extract)
    response = client.post('/api/audit', json={
        'record': {'fall_status':'unknown','dizziness_status':'present','assistance_status':'present'},
        'narrative':EXAMPLE,'use_llm':True
    })
    assert response.status_code == 200
    data = response.json()
    assert data['source'] == 'llm'
    assert data['flags'][0]['source'] == 'llm'
