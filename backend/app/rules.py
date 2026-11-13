"""Deterministic baseline for synthetic Japanese nursing-note patterns.

This is explicitly NOT a clinically validated extraction system.
"""
import re
from .schemas import NarrativeExtraction, StructuredRecord, AuditFlag

FIELDS = ('fall_status', 'dizziness_status', 'assistance_status')
LABELS = {'fall_status': '転倒', 'dizziness_status': 'ふらつき', 'assistance_status': '介助'}
# Negative cues are intentionally checked before positives.
PATTERNS = {
    'fall_status': (
        r'転倒(?:は|を)?(?:認めず|なし|ない|していない|せず)|転倒していない',
        r'転倒(?:した|あり|を認めた|を確認|があった)',
    ),
    'dizziness_status': (
        r'ふらつき(?:は|を)?(?:なし|認めず|ない)',
        r'ふらつき(?:あり|を認めた|がみられる|がある)',
    ),
    'assistance_status': (
        r'介助(?:なし|不要)|介助を要さず',
        r'看護師が介助|介助(?:した|あり|実施|を行った|。)|付き添い',
    ),
}

def baseline_extract(note: str) -> NarrativeExtraction:
    values = {}
    evidence = {}
    for field, (negative, positive) in PATTERNS.items():
        neg = re.search(negative, note)
        pos = re.search(positive, note)
        # If both positive and negative cues are present, abstain: demo baseline
        # cannot resolve temporal or contextual negation safely.
        if neg and pos:
            values[field] = 'unknown'
        elif neg:
            values[field] = 'absent'
            evidence[field] = neg.group(0)
        elif pos:
            values[field] = 'present'
            evidence[field] = pos.group(0)
        else:
            values[field] = 'unknown'
    return NarrativeExtraction(**values, evidence=evidence)

def compare_record(record: StructuredRecord, extracted: NarrativeExtraction, source: str) -> list[AuditFlag]:
    flags = []
    for field in FIELDS:
        recorded = getattr(record, field)
        observed = getattr(extracted, field)
        if observed == 'unknown' or recorded == observed:
            continue
        kind = 'missing_structured' if recorded == 'unknown' else 'conflict'
        msg = ('構造化項目が未記録ですが、自由記述に手掛かりがあります。' if kind == 'missing_structured'
               else '構造化項目と自由記述の候補が一致しません。')
        flags.append(AuditFlag(field=field, kind=kind, recorded=recorded,
                               observed=observed, evidence=extracted.evidence.get(field, ''),
                               message=f'{LABELS[field]}: {msg}', source=source))
    return flags
