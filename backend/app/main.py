import os
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .schemas import AuditRequest, AuditResponse
from .rules import baseline_extract, compare_record
from .inference_client import extract

app = FastAPI(title='Nursing Record Quality Lab API', version='0.1.0')
allowed = [origin.strip() for origin in os.getenv('CORS_ORIGINS','http://localhost:5173').split(',') if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=allowed, allow_methods=['GET','POST'],
                   allow_headers=['Content-Type', 'Authorization'])

@app.get('/health/live')
def live():
    return {'status': 'ok', 'service': 'backend'}

@app.post('/api/audit', response_model=AuditResponse)
async def audit(payload: AuditRequest):
    start = time.perf_counter()
    baseline = baseline_extract(payload.narrative)
    source = 'llm' if payload.use_llm else 'rule'
    extracted = await extract(payload.narrative) if payload.use_llm else baseline
    flags = compare_record(payload.record, extracted, source)
    return AuditResponse(baseline=baseline, extraction=extracted, flags=flags,
                         source=source, elapsed_ms=round((time.perf_counter()-start)*1000, 1))
