"""Cloud-replaceable inference HTTP boundary; Ollama only inside this service."""
import json
import os
import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

Status = Literal['present', 'absent', 'unknown']
MODEL_NAME = os.getenv('MODEL_NAME', 'qwen3:0.6b')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434').rstrip('/')
app = FastAPI(title='Clinical Narrative Inference Adapter', version='1.0.0')

class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    narrative: str = Field(min_length=1, max_length=2000)

class ExtractResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    fall_status: Status = 'unknown'
    dizziness_status: Status = 'unknown'
    assistance_status: Status = 'unknown'
    evidence: dict[str, str] = Field(default_factory=dict)

SYSTEM = (
    'あなたは架空の日本語看護記録の研究用抽出器です。臨床判断をしないでください。'
    '転倒(fall_status)、ふらつき(dizziness_status)、介助(assistance_status)の有無を'
    'present/absent/unknownで返してください。未言及は必ずunknown。'
    '否定表現はabsent。evidenceには判断根拠となる原文の完全一致部分文字列だけを記載。'
    '文章にない事実を補完しない。JSONスキーマに従ってください。'
)

@app.get('/health/live')
def live():
    return {'status':'ok', 'service':'inference', 'model':MODEL_NAME}

@app.post('/v1/extract', response_model=ExtractResponse)
async def extract(body: ExtractRequest):
    request_data = {
        'model': MODEL_NAME,
        'messages': [{'role':'system', 'content':SYSTEM},{'role':'user', 'content':body.narrative}],
        'format': ExtractResponse.model_json_schema(),
        'stream': False,
        'think': False,
        'options': {'temperature': 0, 'num_predict': 256},
    }
    try:
        async with httpx.AsyncClient(timeout=115) as client:
            response = await client.post(f'{OLLAMA_URL}/api/chat', json=request_data)
            response.raise_for_status()
            model_output = json.loads(response.json()['message']['content'])
            proposed = ExtractResponse.model_validate(model_output)
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(503, detail='Model inference failed or returned invalid JSON') from exc
    # A defensible evidence guard; not a substitute for clinical validation.
    values = proposed.model_dump()
    evidence = {}
    for field in ('fall_status','dizziness_status','assistance_status'):
        snippet = proposed.evidence.get(field, '')
        if not isinstance(snippet, str) or not snippet or len(snippet) > 120 or snippet not in body.narrative:
            values[field] = 'unknown'
        else:
            evidence[field] = snippet
    values['evidence'] = evidence
    return ExtractResponse.model_validate(values)
