# GCP へのサービス別配置案（設計資料、IaC未実装）

## マッピング

| Local component | GCP option | Purpose |
|---|---|---|
| `frontend` Vite `dist/` | Cloud Storage + Cloud CDN (via load balancer) / Firebase Hosting | 静的Web配信 |
| `backend` container | Cloud Run | Public API（認証プロキシ/入口設計が別途必要） |
| `inference` container | private Cloud Run service | `/v1/extract` 内部API、独立デプロイ |
| Ollama/other runner | Cloud Run GPU / GCE GPU | モデルランタイム。場合により推論APIと同じCloud Run deploy unitにする |
| `model-init` | Local-only | Cloud側は事前取得済み重み/モデルイメージ/モデルストレージを準備 |
| Persistent storage (future) | Cloud Storage / Cloud SQL | 目的を明確にしたうえで設置 |
| Async jobs (future) | Cloud Tasks + worker | 非同期業務が必要になった場合 |

## Backend から private Cloud Run Inference を呼ぶ

- 推論サービスは未認証公開にしない。
- Backend実行用Service Accountに推論サービスの `roles/run.invoker` を付与。
- Backendに `INFERENCE_URL=https://YOUR-INFERENCE-SERVICE.run.app` を設定。
- `INFERENCE_AUTH_MODE=google_id_token`, `INFERENCE_AUDIENCE=https://YOUR-INFERENCE-SERVICE.run.app` を設定。
- BackendはID tokenを取得し、`Authorization: Bearer` で送る実装を内蔵。**IAM権限とGoogle実行環境の設定は利用者側で必要**。
- Local Composeでは `INFERENCE_AUTH_MODE=none` を使う。

## GPU推論へ切り替える場合

Cloud Run GPUはLLM推論に対応。ただしGPU種別・リージョン・CPU/メモリ最小要件・クォータに制約がある。GPUサービス内でモデルを直接実行するには、`inference` service内部のruntimeを交換するか、Ollama sidecarで推論ランタイムを同一デプロイ単位にまとめる。**付属のComposeをそのまま単一Cloud Runサービスに投げても、望む独立デプロイ・重みの永続化は成立しない**。

Cloud Runコンテナは ingress port と一致するポートを `0.0.0.0` でListenする必要がある。各Dockerfileはそれぞれ8000/8100でListenするので、デプロイ側でもそのポートを指定する。

## フロントエンド

CDN配信する場合 `VITE_API_BASE_URL=https://api.example.com/api` をビルド時に注入し、Backendの `CORS_ORIGINS` を一致させる。アクセストークンをJavaScriptに恒久保存せず、認証方式とcookie方針を別途設計する。

## 本番化前のチェック

1. 認証/OIDC、Cloud Armor/WAF、TLS、private ingress、Secret Manager、監査ロギングを決める。
2. `use_llm=true` の同期APIが許容されるレイテンシかを計測する。長時間ならCloud Tasksを検討。
3. `INFERENCE_AUTH_MODE` はGoogle ID tokenのみ実装済み。ネットワーク経路/IAMの正しさは実クラウド環境で統合確認。
4. モデル・プロンプト・データバージョン固定、病院とのデータ処理契約/国内法・ガイドライン確認。

参考:
- https://docs.cloud.google.com/run/docs/authenticating/service-to-service
- https://docs.cloud.google.com/run/docs/configuring/services/gpu
- https://docs.cloud.google.com/run/docs/container-contract
