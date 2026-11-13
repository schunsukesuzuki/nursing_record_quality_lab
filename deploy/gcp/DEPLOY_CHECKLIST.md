# GCP デプロイ前チェックリスト（レビュー用）

> **状態：Terraformサンプル／未適用・未検証。本番利用不可。** 合成データ専用。実患者情報の投入は想定していません。

## A. セキュリティ／データ保護（必須）

- [ ] GCPプロジェクトの課金・リージョン・組織ポリシー（`allUsers`不可など）を確認。現行サンプルのfrontend/backendは**公開**、inferenceはCloud Run IAMのみで限定。
- [ ] `roles/run.invoker`をbackend service accountにのみ与え、inferenceを第三者が呼べないことを検証。
- [ ] Inferenceのingressは `INGRESS_TRAFFIC_ALL` だが**IAMで保護**している。これはネットワークレベルでの内部限定ではない。要件に応じてVPC/ingress `internal`/ロードバランサ経由を再設計。
- [ ] `INFERENCE_AUTH_MODE=google_id_token` により、backendが推論サービスのURLをaudienceとしてID tokenを発行する。tokenの検証・401/403時の診断と再試行を確認。
- [ ] Backendのエンドユーザー認証・認可（Identity Platform、IAP、OIDC等）を実装する。現状、公開APIにエンドユーザー認証はない。
- [ ] CORS `frontend_origin` が実際のCloud Run frontend URLと**完全一致**することを確認。CORSは認証・保護ではない。
- [ ] サービスアカウントは機能ごとに分離。ビルド・デプロイ担当には最小権限、Secret Manager、監査ログ、ログのPII削除方針を設定。
- [ ] 実患者データを扱う場合は、データ取扱い契約・所在地・保持削除・日本国内の医療情報関連要件を別途レビュー。実利用にはそのためのアーキテクチャ改訂が必要。

## B. ビルド・デプロイと推論モデル

- [ ] `run.googleapis.com` / `artifactregistry.googleapis.com` / `iam.googleapis.com` のAPI有効化と権限を確認。
- [ ] Artifact Registry作成後に、frontend・backend・inference・モデル格納済みOllamaの4イメージを**個別にpush**。Terraformはbuild/pushをしない。
- [ ] `frontend` Dockerfileの`production` stage (Nginx :80) でビルド。**Vite API URLはビルド時に焼き込む**ため、`VITE_API_BASE_URL=https://<backend>.run.app/api` で生成したイメージを使用。
- [ ] Backend URLとfrontend URLの確定には**段階的な適用／再ビルド**が必要。`frontend_origin`は実URLに変更して`terraform apply`を繰り返す。デプロイ前はplaceholderを使用しない。
- [ ] Cloud Runの推論サービスは **Inference API :8100 + Ollama :11434のサイドカー**。`OLLAMA_URL=http://127.0.0.1:11434` を確認。
- [ ] Ollamaサイドカーは`deploy/shared/ollama`による**事前格納モデルイメージ**が必要。初回起動の`ollama pull`はしない。
- [ ] Cloud RunのPORTを確認：frontend=80、backend=8000、inference=8100。アプリ側で`0.0.0.0`にListenしていること。
- [ ] Sidecarのstartup probeは`/api/tags`を確認するが、**モデルが存在する保証ではない**。別途`/health/ready`を確認。
- [ ] CPU/メモリ上限・コールドスタート・クォータ・リクエストタイムアウト(最大300秒)を検証。

## C. 性能・評価・費用

- [ ] 24件合成データで3種類のプロンプトの分類Accuracy/Macro F1、根拠照合、監査Precision/Recallを比較。
- [ ] ルールだけの監査と、LLM待機時の処理が分離されているか確認。
- [ ] p50/p95、初回推論時間、Cloud Run scale-to-zero後のモデルロード、CPUメモリ使用量を測る。
- [ ] 0.6Bモデルでも小さいとは限らない。Cloud Run CPUのみで十分かを測ってからGPU/モデル配置方法を見直す。
- [ ] Cloud Run logに看護記録の原文・モデル生出力・患者識別子を残さない。Traceやエラー詳細も検査。
- [ ] Cloud Monitoringのアラート、アクセスログ、請求予算アラートを設定。コールドスタート待ちを含むSLOを定義。
- [ ] リリース／rollback時はイメージdigestとプロンプト・評価データのバージョンを保持。旧リビジョンへ戻せるか確認。
- [ ] `terraform destroy` の対象とデータ消去方針、Artifact Registryイメージ削除ポリシーを確認。

## D. 具体的なsmoke test（架空データのみ）

```bash
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
terraform plan -var-file=terraform.tfvars
# apply はコードレビューと予算確認後のみ

gcloud run services list --project YOUR_GCP_PROJECT_ID --region asia-northeast1
# 公開バックエンドのステータス確認。任意の機密情報は送らない。
curl -i 'https://<backend>.run.app/api/inference/status'
# 推論サービスを匿名で呼んだ場合は401/403であることを確認
curl -i 'https://<inference>.run.app/health/ready'
```

**出典**: [Cloud Run service-to-service認証](https://docs.cloud.google.com/run/docs/authenticating/service-to-service) · [Cloud Run multi-container](https://docs.cloud.google.com/run/docs/configuring/services/containers) · [Cloud Run IAM](https://docs.cloud.google.com/run/docs/securing/managing-access)
