"""Run 24 synthetic cases against local rule baseline without starting Docker."""
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from app.rules import baseline_extract,compare_record
from evaluate_models import evaluate

cases=json.loads((ROOT/'sample_data/evaluation_cases.json').read_text(encoding='utf-8'))
replies=[]
for case in cases:
    prediction=baseline_extract(case['narrative'])
    from app.schemas import StructuredRecord
    flags=compare_record(StructuredRecord(**case['record']),prediction,'rule')
    replies.append({'baseline':prediction.model_dump(), 'extraction':prediction.model_dump(),
                    'baseline_flags':[f.model_dump() for f in flags], 'flags':[f.model_dump() for f in flags]})
summary=evaluate(cases,replies)
print(json.dumps({'case_count':len(cases),'baseline':summary['baseline'], 'flags':summary['baseline_flags']},ensure_ascii=False,indent=2))
