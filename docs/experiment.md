# R&D評価 — v1.5

## 目的・仮説

**仮説:** 小型LLM (Qwen3-0.6B) が日本語の言い換えによる看護イベントを認識できるかはプロンプトに依存する。
特に `unknown`（未言及）と `absent`（明確な否定）を区別し、歩行不安定・転倒・介助を混同しないか検証する。

## 固定条件と比較軸

- Baseline: 決定論的ルール
- LLM A: `basic`（従来の短いプロンプト）
- LLM B: `semantic`（操作的定義）
- LLM C: `few_shot`（同じ定義＋例示）
- 共通: `qwen3:0.6b`, Ollama structured output, temperature=0, think=false, 同一合成入力・同一モデル
- 注意: 推論環境、Ollamaバージョン、モデルdigest、実行ハードウェアを報告すること。固定設定でも完全な決定性は保証されない。
- これら24例は**開発用の診断セット**。事前公開しているため、プロンプトを調整した場合に独立した最終評価セットとして使わない。

## 検証上の3段階

1. **状態抽出** `raw_extraction`: LLM自身が返したpresent/absent/unknownを直接、正解ラベルと照合する。
2. **根拠文字列の照合** `evidence_checks`: 引用文字列が原文に連続部分文字列として含まれるか確認。
   これは語義・否定の正確さや臨床的妥当性を証明しない。`rule_supported` はルールによる補完なので独立したLLM根拠には数えない。
3. **監査への採用** `extraction`, `flags`: 根拠不足の判定は保留、引用が原文に一致している候補のみ下流の比較に進める。
   ただし引用の意味的な正しさは未保証であり、全件人手確認が必要な研究PoCである。

## 指標と限界

- 3状態の正解率・macro F1と各項目の正解率（`unknown`を独立クラスとする）。
- 監査候補のPrecision / Recall（構造化記録と人工ラベルの相違に基づく、合成データ上の候補）。
- 引用文字列の存在割合は語義の正しさを含めない。
- 判定保留理由の内訳（`missing_quote`, `rule_disagreement`, `model_unknown`, etc.）
- latency p50 / p95。3条件比較ではプロンプト長も差として考慮する。
- サンプルが小さいので、性能差を一般化しない。実医療データでの使用・診療判断はできない。

## 実行

```bash
python scripts/evaluate_rule_synthetic.py
# backend と ollama を起動してから
python scripts/evaluate_models.py --variants basic semantic few_shot --output results/synthetic_metrics.json
```

モデルの状態確認 (`/api/inference/status`) は登録済みを意味するだけで、推論実施と同義ではない。

## 学術的な発展

観察や記録の欠測が症例や病院ごとに偏る場合、観測過程自体をモデル化する必要がある。
`P(M=1 | X,H,T)` （記録M、患者状態X、施設H、時刻T）を仮説として検討する。
現PoCの抽出F1が高いことと、この欠測バイアスが解消したことは別の問題である。
