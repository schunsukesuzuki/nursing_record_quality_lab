import importlib.util
import json
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('metrics', ROOT/'scripts/evaluate_models.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

class MetricsTests(unittest.TestCase):
    def test_fixture_ids_unique_and_distinct_from_examples(self):
        cases=json.loads((ROOT/'sample_data/evaluation_cases.json').read_text(encoding='utf-8'))
        self.assertEqual(len(cases),24)
        self.assertEqual(len({c['id'] for c in cases}),len(cases))
        self.assertTrue(any(c['category']=='paraphrase' for c in cases))
        self.assertTrue(any(c['category']=='unknown' for c in cases))

    def test_accuracy_and_non_semantic_quote_match(self):
        note='床に倒れることはなかった。'
        case={'narrative':note,'record':{'fall_status':'unknown','dizziness_status':'unknown','assistance_status':'unknown'},
              'expected':{'fall_status':'absent','dizziness_status':'unknown','assistance_status':'unknown'}}
        extraction=dict(case['expected'],evidence={'fall_status':'床に倒れることはなかった'})
        reply={'baseline':extraction, 'raw_extraction':extraction, 'extraction':extraction,
               'baseline_flags':[{'field':'fall_status','kind':'missing_structured','observed':'absent'}],
               'flags':[{'field':'fall_status','kind':'missing_structured','observed':'absent'}],
               'evidence_checks':{'fall_status':'quoted'},'elapsed_ms':100.0}
        output=module.evaluate([case],[reply])
        self.assertEqual(output['raw_extraction']['status_accuracy'],1.0)
        self.assertEqual(output['literal_evidence_quote_rate'],1.0)
        self.assertEqual(output['flags']['recall'],1.0)

if __name__=='__main__':unittest.main()
