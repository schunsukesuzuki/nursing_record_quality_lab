# AWS — Terraform設計サンプル（合成データ専用）

このフォルダに**サンプルIaC（Terraform）**を追加しました。`terraform apply` による実環境構築は未確認です。公開設定・HTTP-only経路・ユーザー認証未実装のため**本番・実患者データには使用しないこと**。

**必読:** [DEPLOY_CHECKLIST.md](DEPLOY_CHECKLIST.md)

## サービス構成と責務

```text
Browser
  └─ HTTPS → CloudFront ── /        → private S3 (React/Vite dist)
                       └─ /api/*   → public HTTP ALB ── ECS Fargate backend:8000
                                                         │
                                                         │ Cloud Map DNS (VPC)
                                                         ▼
                                    ECS Fargate inference task:8100
                                      ├─ inference FastAPI adapter:8100
                                      └─ Ollama sidecar:11434 (task-local loopback)
```

| サービス | IaC | 更新単位 | 補足 |
|---|---|---|---|
| Frontend | S3 + CloudFront | S3 `dist/`配信 | Vite `VITE_API_BASE_URL=/api` |
| Backend | ECS Fargate + ALB | backend task definition | 認証は未実装。APIを誰でも呼べるサンプル |
| Inference + Ollama | ECS Fargate + Cloud Map | inference task definition | APIとモデルサイドカーを同一タスクに配置 |
| Model initialization | **IaCでは起動時pullしない** | モデル格納済みOCIイメージ | `../shared/ollama/`で構築 |
| Async/DB | 未実装 | 将来SQS/RDS/S3等 | 今回のPoCには不要 |

`INFERENCE_URL=http://inference.nrl.internal:8100`。BackendとInferenceの認証はクラウド用に未実装（SGによる到達制限のみ）。`INFERENCE_AUTH_MODE=none` を本番の安全策と解釈しないでください。

## 配置ファイル

- `versions.tf`: TerraformとAWSプロバイダ
- `variables.tf` / `terraform.tfvars.example`: 環境変数とイメージ参照の例（実値に置き換え）
- `main.tf`: ECR、VPC、ECS、ALB、Cloud Map、IAM、CloudWatch
- `frontend.tf`: private S3 + CloudFront OAC + `/api/*` ALBルーティング
- `outputs.tf`: URL/バケット名/ECR URI
- `DEPLOY_CHECKLIST.md`: セキュリティ・費用・性能・運用・テスト

## 認証なしのローカル検証（クラウド資源は作らない）

```bash
cd deploy/aws
cp terraform.tfvars.example terraform.tfvars
# 画像URIは実際のECRを参照するよう変更
terraform fmt -recursive
terraform init -backend=false
terraform validate
terraform plan -var-file=terraform.tfvars
```

`terraform init`はproviderをダウンロードします。`plan`はAWS資格情報と環境が必要です。**`apply`は課金対象資源を作成するため安易に実行しないでください**。Terraform state/プロバイダlockを適切に管理してください。

## 実デプロイに進むなら（レビュー後の参考手順）

1. AWSアカウントと請求予算・権限を確認。ECRが必要なため**リポジトリ作成→イメージpush→残りのサービス構築**の順序が必要。例外的な初回bootstrapでは `terraform apply -target=aws_ecr_repository.images -var-file=terraform.tfvars` の使用が考えられます（`-target`を通常運用に用いない）。
2. `docker build -t ... ./backend` / `./inference` で別イメージを作り、`../shared/ollama/Dockerfile` でモデル入りOllamaイメージを作る。ECRにそれぞれpushし、`terraform.tfvars`を実イメージURIで更新。OCI digest固定を推奨。
3. `terraform plan -out=plan.out` をレビューのうえ、意図が確認できた場合だけ `terraform apply plan.out`。
4. Frontendはリポジトリの`frontend`で `VITE_API_BASE_URL=/api npm run build` を実行して静的ファイルをS3に同期。`aws s3 sync frontend/dist "s3://$(terraform output -raw frontend_bucket)"`（プロジェクトrootから実行する場合はパスに注意）。CloudFrontキャッシュ無効化等を実施。
5. [DEPLOY_CHECKLIST.md](DEPLOY_CHECKLIST.md)を使って、**HTTPS化・認証追加・タスクのprivate化**を完了させてから対外公開を検討。上記Terraformのまま本番デプロイしない。

## 制約・デモとしての未整備事項

- CloudFront→ALBはHTTPであり、ALB自体も公開（オリジン直接アクセス可能）。認証・WAF・TLSの本番設計は意図的に未実装。
- Fargate taskにはデモ簡略化のためpublic IPを設定。SGではInferenceへの公開入口を開けていないが、private subnet構成への変更が必要。
- 推論タスクは既定のCPU 2 vCPU / 4GiB、モデルイメージは事前取得済みを要求。実際のメモリ消費、起動・推論時間、可用性は未測定。
- FargateはGPU非対応。GPU化は別ランタイムへ切り離して配置を変更する。
- 今回はTerraform state backend、Secrets Manager、OIDC、CloudWatch alarms、autoscaling、WAF、料金アラート、CI/CD、DNS/ACM証明書など未実装。

## 公式参照

- [ECS Service Discovery](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-discovery.html)
- [CloudFront S3 OAC](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html)
- [AWS Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)
