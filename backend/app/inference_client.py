import asyncio
import os
import httpx
from fastapi import HTTPException
from .schemas import NarrativeExtraction

INFERENCE_URL = os.getenv('INFERENCE_URL', 'http://localhost:8100').rstrip('/')
TIMEOUT = float(os.getenv('INFERENCE_TIMEOUT_SECONDS', '120'))

def _google_token(audience: str) -> str:
    from google.auth.transport.requests import Request
    from google.oauth2.id_token import fetch_id_token
    return fetch_id_token(Request(), audience)

async def extract(note: str) -> NarrativeExtraction:
    # Google Cloud Run private service: use per-service identity and ID token.
    mode = os.getenv('INFERENCE_AUTH_MODE', 'none')
    headers = {}
    if mode == 'google_id_token':
        audience = os.getenv('INFERENCE_AUDIENCE')
        if not audience:
            raise HTTPException(503, detail='Inference identity is not configured')
        token = await asyncio.to_thread(_google_token, audience)
        headers['Authorization'] = f'Bearer {token}'
    elif mode != 'none':
        raise HTTPException(503, detail='Unsupported inference auth mode')
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(f'{INFERENCE_URL}/v1/extract', json={'narrative': note}, headers=headers)
            response.raise_for_status()
            return NarrativeExtraction.model_validate(response.json())
    except (httpx.HTTPError, ValueError) as exc:
        # Never include the narrative or raw upstream response in error messages/logs.
        raise HTTPException(status_code=503, detail='Inference service unavailable or response invalid') from exc
