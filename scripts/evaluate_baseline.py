"""Run a tiny, reproducible synthetic fixture evaluation (NOT clinical validation)."""
import json
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root/'backend'))
from app.rules import baseline_extract, FIELDS
cases=json.loads((root/'sample_data/fixtures.json').read_text(encoding='utf-8'))
correct = total = 0
for idx, case in enumerate(cases, 1):
    prediction=baseline_extract(case['narrative'])
    ok=sum(getattr(prediction, f)==case['expected'][f] for f in FIELDS)
    print(f'case={idx} correct={ok}/{len(FIELDS)}')
    correct += ok; total += len(FIELDS)
print(f'Field accuracy: {correct}/{total} = {correct/total:.1%} (synthetic fixtures only)')
