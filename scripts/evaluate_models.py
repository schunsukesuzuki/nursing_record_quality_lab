"""Compare rule / raw LLM / evidence-gated audit on synthetic held-out examples.

Uses only Python stdlib and calls the running backend. Never use real patient notes.
Example: python scripts/evaluate_models.py --variants basic semantic few_shot
"""
import argparse
import json
import math
import statistics
from pathlib import Path
from urllib import request, error

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('fall_status','dizziness_status','assistance_status')
LABELS = ('absent','present','unknown')


def macro_f1(golds, preds):
    """All 3 labels including unknown; failed requests count as misses."""
    scores = []
    for status in LABELS:
        tp = sum(g == status and p == status for g,p in zip(golds,preds))
        fp = sum(g != status and p == status for g,p in zip(golds,preds))
        fn = sum(g == status and p != status for g,p in zip(golds,preds))
        scores.append(2 * tp / (2*tp + fp + fn) if 2*tp + fp + fn else 0)
    return round(sum(scores)/len(scores), 4)


def evaluate(cases, replies):
    result = {}
    for key in ('baseline', 'raw_extraction', 'extraction'):
        gold = [c['expected'][field] for c in cases for field in FIELDS]
        pred = [(r.get(key) or {}).get(field) for r in replies for field in FIELDS]
        result[key] = {
            'status_accuracy': round(sum(a==b for a,b in zip(gold,pred))/len(gold),4),
            'macro_f1': macro_f1(gold,pred),
            'per_field_accuracy': {field:round(sum(c['expected'][field] == (r.get(key) or {}).get(field)
                 for c,r in zip(cases,replies))/len(cases),4) for field in FIELDS},
        }
    for key in ('baseline_flags','flags'):
        tp=fp=fn=0
        for c,r in zip(cases,replies):
            expected={(field, 'missing_structured' if c['record'][field]=='unknown' else 'conflict', c['expected'][field])
                     for field in FIELDS if c['expected'][field]!='unknown' and c['record'][field] != c['expected'][field]}
            predicted={(flag['field'],flag['kind'],flag['observed']) for flag in r.get(key,[])}
            tp+=len(expected & predicted);fp+=len(predicted-expected);fn+=len(expected-predicted)
        result[key]={'precision':round(tp/(tp+fp),4) if (tp+fp) else None,
                     'recall':round(tp/(tp+fn),4) if (tp+fn) else None,
                     'tp':tp,'fp':fp,'fn':fn}
    all_positive = 0
    verbatim = 0
    reasons = {}
    for c,r in zip(cases,replies):
        raw = r.get('raw_extraction') or {}
        evidence = raw.get('evidence') or {}
        for field in FIELDS:
            if raw.get(field) in ('present','absent'):
                all_positive+=1
                if evidence.get(field) and evidence[field] in c['narrative']:
                    verbatim+=1
            code=(r.get('evidence_checks') or {}).get(field)
            if code: reasons[code]=reasons.get(code,0)+1
    result['literal_evidence_quote_rate'] = round(verbatim/all_positive,4) if all_positive else None
    result['literal_evidence_definition'] = '原文中に同一文字列がある割合。意味の正確さは検証していない。'
    result['evidence_checks'] = reasons
    times = sorted(r['elapsed_ms'] for r in replies if isinstance(r.get('elapsed_ms'), (int,float)))
    result['latency_ms'] = {'p50':round(statistics.median(times),1) if times else None,
                            'p95':round(times[min(len(times)-1,math.ceil(.95*len(times))-1)],1) if times else None}
    result['successful_responses'] = len(times)
    result['total_cases'] = len(cases)
    return result


def post_audit(base_url, case, variant, timeout):
    obj={'record':case['record'],'narrative':case['narrative'],
         'use_llm':True,'prompt_variant':variant}
    req=request.Request(base_url.rstrip('/')+'/api/audit',
        data=json.dumps(obj,ensure_ascii=False).encode('utf-8'),
        headers={'Content-Type':'application/json'}, method='POST')
    with request.urlopen(req,timeout=timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--base-url',default='http://localhost:8000')
    ap.add_argument('--variants', nargs='+', choices=['basic','semantic','few_shot'],default=['semantic'])
    ap.add_argument('--limit',type=int,default=0,help='0 means all synthetic cases')
    ap.add_argument('--timeout',type=float,default=240)
    ap.add_argument('--output',default='',help='Optional path for JSON metrics (no raw patient data)')
    args=ap.parse_args()
    cases=json.loads((ROOT/'sample_data/evaluation_cases.json').read_text(encoding='utf-8'))
    if args.limit:cases=cases[:args.limit]
    summary={'_meta': {
        'dataset':'24 synthetic developer-authored diagnostic cases',
        'n_cases':len(cases), 'model_status':'unverified',
        'note':'No clinical validation; raw model status is scored independently of evidence verification.'
    }}
    try:
        with request.urlopen(args.base_url.rstrip('/')+'/api/inference/status',timeout=10) as response:
            status=json.loads(response.read().decode('utf-8'))
            summary['_meta']['model_status']={key:status.get(key) for key in ('model','available','code')}
    except (error.URLError,TimeoutError,ValueError):
        pass
    # Iterate in the same fixture order; model and temperature remain fixed.
    # For a larger, credible study, randomize variant ordering and repeat seeds.
    for variant in args.variants:
        replies=[]
        for idx,case in enumerate(cases,1):
            try:
                result=post_audit(args.base_url,case,variant,args.timeout)
                print(f'{variant} {idx}/{len(cases)} {case["id"]}: OK {result.get("elapsed_ms")}ms')
                replies.append(result)
            except (error.URLError, TimeoutError, ValueError) as exc:
                print(f'{variant} {idx}/{len(cases)} {case["id"]}: ERROR {type(exc).__name__}')
                replies.append({})
        summary[variant]=evaluate(cases,replies)
        print(json.dumps({variant:summary[variant]},ensure_ascii=False,indent=2))
    if args.output:
        out=Path(args.output)
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f'Saved: {out}')

if __name__=='__main__':
    main()
