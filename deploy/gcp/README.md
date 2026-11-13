# GCP — Terraform設計サンプル（合成データ専用）

**Cloud Run（frontend/backend/inference）を別サービスで定義し、推論サービスだけIAMで限定公開**するTerraformのサンプルです。未デプロイ・未検証です。エンドユーザー認証のないサンプルなので**実患者データは投入禁止**。

**必読:** [DEPLOY_CHECKLIST.md](DEPLOY_CHECKLIST.md)

## サービス構成と責務

```text
Browser
  ├─ HTTPS → Cloud Run frontend :80 (Nginx/React built dist)
  └─ HTTPS → Cloud Run backend :8000 (public demo API, CORS configured)
                     │ ID token (backend service account)
                     ▼
           Cloud Run inference :8100 (IAM invoker = backend only)
             ├─ inference FastAPI :8100  (ingress container)
             └─ Ollama :11434          (preloaded-model sidecar; localhost)
```

- Frontend React/TSXとBackend FastAPIは**別デプロイ**。静的ファイルを含むNginxイメージを使用。
- Backendの `INFERENCE_URL`/`INFERENCE_AUDIENCE` には推論Cloud Run URLを設定。コード側に`google_id_token`モードが実装済み。
- Inferenceは他のCloud Runと独立デプロイ、OllamaはInferenceと**同じデプロイ単位**のサイドカー。Local Composeの`model-init`はクラウドでは使わない。
- Inferenceへの匿名リクエストを拒否するのはCloud Run IAM。`ingress=ALL`なので**ネットワーク的に内部限定ではない**。用途に応じてingress/VPC設計を追加。

## 配置ファイル

- `versions.tf`、`variables.tf`、`terraform.tfvars.example`: 変数と事前にpushされたイメージの参照
- `main.tf`: API有効化、Artifact Registry、サービスアカウント、Cloud Run、IAM
- `outputs.tf`: 各サービスURL
- `DEPLOY_CHECKLIST.md`: 実デプロイ前の確認項目
- `../shared/ollama/Dockerfile`: モデル入りOllamaイメージのビルド例

## Planの確認（リソース作成なし）

```bash
cd deploy/gcp
cp terraform.tfvars.example terraform.tfvars
# project_id、image、frontend_originを実値に更新
gcloud auth application-default login
terraform fmt -recursive
terraform init -backend=false
terraform validate
terraform plan -var-file=terraform.tfvars
```

**注意:** `terraform plan`は資格情報・プロジェクト状態にアクセスします。providerが未インストールなら`init`はダウンロードします。`terraform apply`は料金が発生するため、レビューと予算上限の設定が先です。

## 実デプロイに進むなら（レビュー後の参考手順）

1. 対象プロジェクトに請求・必要API・権限を用意。Artifact Registry作成後に4イメージをpush。初回のbootstrapに限り `terraform apply -target=google_project_service.required -target=google_artifact_registry_repository.images -var-file=terraform.tfvars` として段階的に作成する方法があります（通常運用で`-target`は推奨しない）。
2. Backend/Inferenceは `docker build ./backend`, `docker build ./inference`。モデル入りイメージは `deploy/shared/ollama` を参照（`ollama/ollama` 素のイメージではモデルがない）。タグよりimage digest固定を推奨。
3. Frontendは`docker build --target production --build-arg VITE_API_BASE_URL=https://<backend>.run.app/api ... ./frontend`で**ビルド時にAPI URLが固定**される。最初はBackend URLが未確定のため、Backend作成→URL確定→Frontend再ビルド・再デプロイ、という2段階の手順が必要。`frontend_origin`には最終的なFrontendの完全なHTTPS originを設定し直す。
4. `terraform plan -out=plan.out` の差分をレビューしてから適用。デプロイ後はIAM、CORS、モデル準備、APIの動作を [DEPLOY_CHECKLIST.md](DEPLOY_CHECKLIST.md) に従って確認。

## サンプルの未整備事項と注意

- FrontendとBackendは`allUsers`で呼び出せる**公開デモ**。エンドユーザー向け認証（IAP/OIDC等）はまだ無い。
- Cloud Runの3サービスそれぞれにservice accountを使用。推論APIのInvokerはBackendだけ。GCPの組織ポリシーによっては`allUsers`設定を適用できません。
- Sidecarが起動してもモデルが格納されているとは限らないので、`/health/ready` を別途確認。
- サンプルはCPUのみ。Cloud Run GPU・VPC/ネットワーク隔離・秘密情報管理・永続ストレージ・請求予算・CI/CD・WAF・監視アラートは未実装。
- 画像レジストリが別プロジェクトの場合はCloud RunサービスエージェントのArtifact Registry読み取り権限が別途必要。
- Chrome等のブラウザからは`CORS_ORIGINS`が実際のfrontend URLと一致しないとAPIを使えません。CORSは認証ではありません。

## 公式参照

- [Cloud Run サービス間認証](https://docs.cloud.google.com/run/docs/authenticating/service-to-service)
- [Cloud Run マルチコンテナ](https://docs.cloud.google.com/run/docs/configuring/services/containers)
- [Cloud Run IAM](https://docs.cloud.google.com/run/docs/securing/managing-access)
