"""Replaceable inference HTTP boundary. Never log/return clinical narrative or raw model outputs."""
import json
import logging
import os
from typing import Literal

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError

logger = logging.getLogger(__name__)
Status = Literal['present', 'absent', 'unknown']
MODEL_NAME = os.getenv('MODEL_NAME', 'qwen3:0.6b')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434').rstrip('/')
OLLAMA_TIMEOUT = float(os.getenv('OLLAMA_TIMEOUT_SECONDS', '180'))
app = FastAPI(title='Clinical Narrative Inference Adapter', version='1.5.0')

class ExtractRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    narrative: str = Field(min_length=1, max_length=2000)
    prompt_variant: Literal['basic', 'semantic', 'few_shot'] = 'semantic'

class ExtractResponse(BaseModel):
    model_config = ConfigDict(extra='forbid')
    # Required: missing fields must be reported as invalid_model_output, not silently unknown.
    fall_status: Status
    dizziness_status: Status
    assistance_status: Status
    evidence: dict[str, str] = Field(default_factory=dict)

# Keep v1.4 prompt as a controlled baseline ("basic"). In semantic/few_shot,
# the API field dizziness_status is retained for compatibility, but explicitly
# represents gait unsteadiness, NOT subjective vertigo. Future API v2 should
# rename it to gait_unsteadiness_status with explicit schema migration.
BASIC_SYSTEM = (
    'あなたは架空の日本語看護記録の研究用抽出器です。臨床判断をしないでください。'
    '転倒(fall_status)、ふらつき(dizziness_status)、介助(assistance_status)の有無を'
    'present/absent/unknownで返してください。未言及は必ずunknown。'
    '否定表現はabsent。evidenceには判断根拠となる原文の完全一致部分文字列だけを記載。'
    '文章にない事実を補完しない。3つのstatusはすべて必須。'
    'statusがunknownの場合はevidenceを空にしてください。'
    'それ以外は原文から短い文字列をそのまま引用してください。JSONスキーマに従ってください。'
)
SEMANTIC_SYSTEM = ("""
あなたは架空の日本語看護記録からイベントを抽出する研究用アノテータです。
医療判断や診断をせず、文章に書かれたことだけを判断してください。
必ず fall_status, dizziness_status, assistance_status の3項目を分類してください。
分類値: present=事象が起きたと明示、absent=起きていないと明示、unknown=言及なし・判断不能。
重要: unknownはabsentと同じではありません。証拠がないことを「なし」としないでください。

項目の操作的定義:
- fall_status（転倒）: 本当に床等に倒れた/転倒したならpresent。
  「床に倒れることはなかった」「転倒せず」「転倒なし」はabsent。
  単に歩行が不安定なだけならunknown。
- dizziness_status（※API名は互換性維持）: ここでは「めまいの自覚症状」ではなく
  歩行時のふらつき・よろめき・身体が左右に揺れる等の歩行不安定性を表す。
  それが観察・記載されればpresent、明確に安定/ふらつきなしならabsent、未言及はunknown。
- assistance_status（介助）: 看護師/スタッフ等が腕を支える・身体を支える・移動を手助けする等の
  実際の身体的介助があればpresent。明確に介助不要/介助なしならabsent、未言及はunknown。

evidenceはキーを各status名とし、原文の連続した完全一致部分文字列を引用してください。
意訳・要約・推測した説明をevidenceへ入れないでください。
分類の根拠が書かれていない場合はunknownにし、対応するevidenceを省略してください。
他の患者・過去の出来事・推測の記述を現在の出来事と混同しないでください。
JSONスキーマ以外の文章は出力しないでください。
""").strip()

FEW_SHOT_EXAMPLES = (
    (
        '立ち上がった際に足元がよろけた。職員が肩を支えたが、転倒はしなかった。',
        {'fall_status': 'absent', 'dizziness_status': 'present', 'assistance_status': 'present',
         'evidence': {'fall_status': '転倒はしなかった', 'dizziness_status': '足元がよろけた',
                      'assistance_status': '職員が肩を支えた'}}
    ),
    (
        '検温を行い、食事量を記録した。',
        {'fall_status': 'unknown', 'dizziness_status': 'unknown', 'assistance_status': 'unknown',
         'evidence': {}}
    ),
)

def build_messages(prompt_variant: str, narrative: str) -> list[dict[str, str]]:
    if prompt_variant == 'basic':
        system = BASIC_SYSTEM
    elif prompt_variant in ('semantic', 'few_shot'):
        system = SEMANTIC_SYSTEM
    else:
        raise ValueError('Invalid prompt variant')
    messages = [{'role': 'system', 'content': system}]
    if prompt_variant == 'few_shot':
        for example_note, expected in FEW_SHOT_EXAMPLES:
            messages.append({'role': 'user', 'content': example_note})
            messages.append({'role': 'assistant', 'content': json.dumps(expected, ensure_ascii=False)})
    messages.append({'role': 'user', 'content': narrative})
    return messages

def failure(code: str, message: str, status: int = 503) -> HTTPException:
    return HTTPException(status_code=status, detail={'code': code, 'message': message})

@app.get('/health/live')
def live():
    return {'status': 'ok', 'service': 'inference'}

@app.get('/health/ready')
async def ready():
    """Unlike /live, checks Ollama reachability AND availability of the configured model."""
    try:
        async with httpx.AsyncClient(timeout=6) as client:
            response = await client.get(f'{OLLAMA_URL}/api/tags')
            response.raise_for_status()
            models = response.json().get('models', [])
            names = {m.get('name') or m.get('model') for m in models if isinstance(m, dict)}
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        logger.warning('Ollama readiness failed: %s', type(exc).__name__)
        raise failure('ollama_unreachable', 'Ollamaサーバーに接続できません') from exc
    if MODEL_NAME not in names:
        raise failure('model_not_found', '指定モデルが未取得です。model-initを確認してください')
    return {'status':'ready', 'service':'inference', 'model': MODEL_NAME}

@app.post('/v1/extract', response_model=ExtractResponse)
async def extract(body: ExtractRequest):
    request_data = {
        'model': MODEL_NAME,
        'messages': build_messages(body.prompt_variant, body.narrative),
        'format': ExtractResponse.model_json_schema(),
        'stream': False,
        'think': False,
        'options': {'temperature': 0, 'num_predict': 384},
    }
    try:
        async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
            response = await client.post(f'{OLLAMA_URL}/api/chat', json=request_data)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        logger.warning('Ollama inference timed out')
        raise failure('model_timeout', 'モデル推論がタイムアウトしました。初回ロードやCPU負荷を確認してください', 504) from exc
    except httpx.ConnectError as exc:
        logger.warning('Cannot connect to Ollama')
        raise failure('ollama_unreachable', 'Ollamaサーバーに接続できません') from exc
    except httpx.HTTPStatusError as exc:
        status = exc.response.status_code
        logger.warning('Ollama inference HTTP status %s', status)
        if status == 404:
            raise failure('model_not_found', '指定モデルがOllamaに見つかりません') from exc
        if status in (500, 503, 507):
            raise failure('model_runtime_error', 'モデル実行に失敗しました。Ollamaのログとメモリを確認してください') from exc
        raise failure('ollama_http_error', f'OllamaがHTTP {status}を返しました。ログを確認してください') from exc
    except httpx.RequestError as exc:
        logger.warning('Ollama connection failed: %s', type(exc).__name__)
        raise failure('ollama_unreachable', 'Ollamaとの通信に失敗しました') from exc
    try:
        payload = response.json()
        content = payload['message']['content']
        proposed = ExtractResponse.model_validate(json.loads(content))
    except (ValueError, KeyError, TypeError, ValidationError) as exc:
        # Do not log response body because it may contain the supplied text.
        logger.warning('Malformed model output: %s', type(exc).__name__)
        raise failure('invalid_model_output', 'モデル出力がJSONスキーマに適合しませんでした', 502) from exc

    # The inference boundary preserves the model's reported statuses. It must NOT
    # silently turn them into unknown just because quoted evidence is paraphrased.
    # Evidence checks and abstention belong to the audit/business layer, so the UI
    # can report what the model actually said and why it was accepted or rejected.
    clean = proposed.model_dump()
    clean['evidence'] = {
        k: v for k, v in proposed.evidence.items()
        if k in ('fall_status', 'dizziness_status', 'assistance_status')
        and isinstance(v, str) and len(v) <= 120
    }
    return ExtractResponse.model_validate(clean)
