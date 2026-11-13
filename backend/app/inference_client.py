"""Backend-to-inference contract with sanitized, actionable failure codes."""
import asyncio
import os
import httpx
from fastapi import HTTPException
from .schemas import NarrativeExtraction, PromptVariant

INFERENCE_URL = os.getenv('INFERENCE_URL', 'http://localhost:8100').rstrip('/')
TIMEOUT = float(os.getenv('INFERENCE_TIMEOUT_SECONDS', '195'))

ERRORS = {
    'ollama_unreachable': 'Ollamaに接続できません。docker compose ps と ollama のログを確認してください。',
    'model_not_found': 'モデルが見つかりません。model-init のログと ollama list を確認してください。',
    'model_timeout': '推論がタイムアウトしました。初回ロード・CPU負荷・メモリを確認してください。',
    'model_runtime_error': 'モデル実行に失敗しました。Ollamaのログと利用可能なメモリを確認してください。',
    'invalid_model_output': 'LLMのJSON出力が不正です。小型モデルの出力制約やログを確認してください。',
    'ollama_http_error': 'Ollamaがエラーを返しました。推論コンテナのログを確認してください。',
    'inference_unreachable': '推論APIに接続できません。inference コンテナの状態を確認してください。',
}

def _google_token(audience: str) -> str:
    from google.auth.transport.requests import Request
    from google.oauth2.id_token import fetch_id_token
    return fetch_id_token(Request(), audience)

async def _auth_headers() -> dict[str, str]:
    mode = os.getenv('INFERENCE_AUTH_MODE', 'none')
    if mode == 'none':
        return {}
    if mode != 'google_id_token':
        raise HTTPException(503, detail={'code':'auth_unconfigured','message':'推論APIの認証設定が不正です'})
    audience = os.getenv('INFERENCE_AUDIENCE')
    if not audience:
        raise HTTPException(503, detail={'code':'auth_unconfigured','message':'推論APIの認証先が未設定です'})
    try:
        token = await asyncio.to_thread(_google_token, audience)
    except Exception as exc:
        raise HTTPException(503, detail={'code':'auth_unavailable','message':'推論APIの認証に失敗しました'}) from exc
    return {'Authorization': f'Bearer {token}'}

def _upstream_failure(response: httpx.Response) -> HTTPException:
    code = 'inference_unavailable'
    try:
        detail = response.json().get('detail')
        if isinstance(detail, dict) and detail.get('code') in ERRORS:
            code = detail['code']
    except (ValueError, TypeError, AttributeError):
        pass
    return HTTPException(status_code=503, detail={'code':code, 'message':ERRORS.get(code, '推論サービスが利用できません')})

async def extract(note: str, prompt_variant: PromptVariant = 'semantic') -> NarrativeExtraction:
    headers = await _auth_headers()
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(f'{INFERENCE_URL}/v1/extract', json={'narrative': note, 'prompt_variant': prompt_variant}, headers=headers)
            if response.is_error:
                raise _upstream_failure(response)
            return NarrativeExtraction.model_validate(response.json())
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=503, detail={
            'code':'inference_unreachable', 'message':ERRORS['inference_unreachable']
        }) from exc

async def inference_status() -> dict:
    """Safe non-patient diagnostic. Always 200 for the UI, never exposes internal hostnames."""
    headers = await _auth_headers()
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            response = await client.get(f'{INFERENCE_URL}/health/ready', headers=headers)
            if response.is_error:
                err = _upstream_failure(response)
                return {'available': False, 'code': err.detail['code'], 'message': err.detail['message']}
            data = response.json()
            return {'available': True, 'code': 'ready', 'message': 'Local LLMは利用可能です', 'model': data.get('model')}
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        return {'available': False, 'code':'inference_unreachable', 'message':ERRORS['inference_unreachable']}
