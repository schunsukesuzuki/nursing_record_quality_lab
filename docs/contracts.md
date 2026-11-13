# API Contracts v1.5

## POST /api/audit (browser -> backend)

```json
{
  "record": {"fall_status":"unknown", "dizziness_status":"present", "assistance_status":"present"},
  "narrative": "歩行時ふらつきあり。移乗時は看護師が介助。転倒は認めず。",
  "use_llm": false,
  "prompt_variant": "semantic"
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
{"narrative":"歩行時ふらつきあり。転倒は認めず。", "prompt_variant":"semantic"}
```

Response:

```json
{"fall_status":"absent", "dizziness_status":"present", "assistance_status":"unknown", "evidence":{"fall_status":"転倒は認めず", "dizziness_status":"ふらつきあり"}}
```

- `present`: あり
- `absent`: 明確な否定（例: 「転倒なし」）
- `unknown`: 未言及、判断困難、根拠がない
- `evidence`: モデルが返す原文引用の候補。推論サービスは生の判定を保持し、根拠が不備でも `unknown` に上書きしない。
- `prompt_variant`: `basic` / `semantic` / `few_shot`; 省略時は `semantic`。
- API名 `dizziness_status` の操作的定義は歩行不安定（「めまいの自覚」とは異なる）。互換性維持のためキー名は継続。

### API versions

`/v1/extract` を安定した inference service 境界として使用する。LLM実装の切り替え後もこの契約を維持し、変更時は `/v2/` を用いる。

### Error handling

- 422: フィールド不正／過大入力／未知フィールド
- 503: 推論サービスの呼び出し失敗または不正応答（本文はログ・エラーに含めない）
- 200: 監査候補の一覧。`flags=[]` は整合性保証を意味しない。

## v1.4 監査結果の追加フィールド

`POST /api/audit` では `baseline_flags` (ルール単独の確認候補)、`raw_extraction` (LLMが返した判定と根拠)、`evidence_checks` (フィールドごとの根拠照合経路) を返します。
`extraction` と `flags` は採用可能な根拠が見つかったLLM結果です。未確認のLLM判断は `unknown` (判定保留) にします。`raw_extraction` と `extraction` は一致しない場合があり、**生の判定と最終採用値を同一視しない**でください。
`/v1/extract` では3つのstatusは必須フィールドとなり、欠落は `invalid_model_output` として返します。

## v1.5 response 追記

`prompt_variant` を返却し、どの抽出条件を使ったかを明示する。`raw_extraction` はモデル生判定、`extraction` は根拠チェック後の監査採用値。
`evidence_checks="quoted"` は文字列の完全一致にすぎず、意味の真偽や臨床的妥当性を証明しない。
`baseline_flags` と `flags` は研究用途の比較のため独立した配列で保持するが、UIは同一項目・同一状態の候補を重複表示しない。
