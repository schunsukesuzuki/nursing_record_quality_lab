# API Contracts v0.1

## POST /api/audit (browser -> backend)

```json
{
  "record": {"fall_status":"unknown", "dizziness_status":"present", "assistance_status":"present"},
  "narrative": "歩行時ふらつきあり。移乗時は看護師が介助。転倒は認めず。",
  "use_llm": false
}
```

Response:

```json
{
  "baseline": {"fall_status":"absent", "dizziness_status":"present", "assistance_status":"present", "evidence": {"fall_status":"転倒は認めず", "dizziness_status":"ふらつきあり", "assistance_status":"看護師が介助"}},
  "extraction": {"fall_status":"absent", "dizziness_status":"present", "assistance_status":"present", "evidence": {"fall_status":"転倒は認めず", "dizziness_status":"ふらつきあり", "assistance_status":"看護師が介助"}},
  "flags": [{"field":"fall_status", "kind":"missing_structured", "recorded":"unknown", "observed":"absent", "evidence":"転倒は認めず", "message":"転倒: 構造化項目が未記録ですが、自由記述に手掛かりがあります。", "source":"rule"}],
  "source":"rule",
  "elapsed_ms":0.3,
  "disclaimer":"架空記録を用いた技術検証です。臨床判断や記録修正には使用できません。"
}
```

数値 `elapsed_ms` は表示用例であり保証値ではない。

## POST /v1/extract (backend -> inference)

Request:

```json
{"narrative":"歩行時ふらつきあり。転倒は認めず。"}
```

Response:

```json
{"fall_status":"absent", "dizziness_status":"present", "assistance_status":"unknown", "evidence":{"fall_status":"転倒は認めず", "dizziness_status":"ふらつきあり"}}
```

- `present`: あり
- `absent`: 明確な否定（例: 「転倒なし」）
- `unknown`: 未言及、判断困難、根拠がない
- `evidence`: 原文に含まれる完全一致の短い部分文字列。なければ当該項目はunknownに落とす。

### API versions

`/v1/extract` を安定した inference service 境界として使用する。LLM実装の切り替え後もこの契約を維持し、変更時は `/v2/` を用いる。

### Error handling

- 422: フィールド不正／過大入力／未知フィールド
- 503: 推論サービスの呼び出し失敗または不正応答（本文はログ・エラーに含めない）
- 200: 監査候補の一覧。`flags=[]` は整合性保証を意味しない。
