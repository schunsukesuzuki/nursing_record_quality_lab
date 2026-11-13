import os
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .schemas import AuditRequest, AuditResponse
from .rules import baseline_extract, compare_record, verify_llm_extraction
from .inference_client import extract, inference_status

app = FastAPI(title='Nursing Record Quality Lab API', version='1.5.0')
allowed = [origin.strip() for origin in os.getenv('CORS_ORIGINS','http://localhost:5173').split(',') if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed, allow_methods=['GET','POST'],
                   allow_headers=['Content-Type', 'Authorization'])

@app.get('/health/live')
def live():
    return {'status': 'ok', 'service': 'backend'}

@app.get('/api/inference/status')
async def status():
    return await inference_status()

@app.post('/api/audit', response_model=AuditResponse)
async def audit(payload: AuditRequest):
    start = time.perf_counter()
    baseline = baseline_extract(payload.narrative)
    source = 'llm' if payload.use_llm else 'rule'
    baseline_flags = compare_record(payload.record, baseline, 'rule')
    raw = await extract(payload.narrative, payload.prompt_variant) if payload.use_llm else None
    extracted, checks = verify_llm_extraction(payload.narrative, raw, baseline) if raw else (baseline, {})
    flags = compare_record(payload.record, extracted, source) if raw else baseline_flags
    return AuditResponse(baseline=baseline, baseline_flags=baseline_flags,
                         raw_extraction=raw, evidence_checks=checks,
                         extraction=extracted, flags=flags, source=source, prompt_variant=payload.prompt_variant,
                         elapsed_ms=round((time.perf_counter()-start)*1000, 1))
