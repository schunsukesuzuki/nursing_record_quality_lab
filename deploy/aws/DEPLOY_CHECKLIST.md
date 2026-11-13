# AWS デプロイ前チェックリスト（レビュー用）

> **状態：Terraformサンプル／未適用・未検証。本番利用不可。** 本プロジェクトは合成看護記録だけを扱うPoCです。AWSアカウント・請求・機密情報のある環境にはレビューなしで適用しないこと。

## A. セキュリティ／データ保護（必須）

- [ ] **実患者・診療データを使用しない**ことを再確認。使用するなら適用法令、医療情報システム関連ガイドライン、委託契約、データ所在地・保管期間、アクセス権・監査要件を先に決定。
- [ ] 公開APIに認証・認可（Cognito/OIDC等）とレート制限を実装する。現在のFastAPIは利用者認証がなく、`/api/audit`を保護していない。
- [ ] CloudFront→ALBが **HTTP** のサンプル設定を、ACM証明書の **HTTPS** に変更。ALBの直接アクセスを遮断（CloudFront origin-facing prefix list・origin認証等）。WAFを検討。
- [ ] ECSタスクを**private subnet**に移動し、NATまたはECR/S3/CloudWatchへのVPCエンドポイントを設計。サンプルは費用節約のためタスクにpublic IPを付与している。
- [ ] Security Groupの出口を必要な宛先に絞る。backend→inferenceはCloud MapのプライベートDNS経由であることを確認する。
- [ ] `INFERENCE_AUTH_MODE=none` はネットワーク制限のみ。適切なmTLS／サービス認証方式、証明書更新・認証失敗時の動作を別途実装・検証。
- [ ] S3は非公開＋CloudFront OAC。CloudFrontのS3アクセス以外が拒否されるかを確認する。
- [ ] CloudWatch、ALB、WAF等のログに患者識別子・生の看護記録・プロンプトが含まれないこと。保持期間、暗号化、アクセス監査、削除方針を検討。
- [ ] ECS task role/ execution roleを最小権限に制限。機密値はSecrets Manager/SSMで扱い、tfvars/stateに平文で入れない。

## B. ビルド・デプロイとサービス境界

- [ ] `backend`, `inference` のDockerイメージを**別々に**ビルド・pushし、digestを記録。ECR scan結果を確認する。
- [ ] `ollama_image`は `deploy/shared/ollama` で作った**モデル事前格納済みイメージ**にする。標準Ollamaイメージだけでは `model_not_found` になる。
- [ ] **ECRリポジトリの作成→イメージpush→ECSを作成**というブートストラップ順序を確認。Terraform自体はコンテナビルドもpushも行わない。
- [ ] Backend `INFERENCE_URL=http://inference.nrl.internal:8100` がCloud Mapで解決し、同じVPC内でアクセスできること。
- [ ] AWS Fargateは**GPU非対応**。GPUへ移行するときはECS on EC2などにモデル実行だけ差し替える。
- [ ] React `VITE_API_BASE_URL=/api` でビルドし、S3に`dist/`を配置。CloudFrontは `/api/*` をALBに転送する設計。CORSのoriginがCloudFront URLに一致するか。
- [ ] CloudFrontキャッシュはAPIで無効（0秒）。`POST /api/audit` のHTTPメソッド、ヘッダー、エラーの透過をテストする。
- [ ] CPU・メモリ（inference task 2 vCPU/4GiB）で初回ロードできるか検証。`health/live` とモデル準備(`/health/ready`)を区別する。

## C. 性能・継続運用・費用

- [ ] 初回起動／再起動時に `qwen3:0.6b` がロードできることを確認。イメージdigestとモデル名を実験ログに記録。
- [ ] 24件の合成評価セットで分類Accuracy・Macro F1、引用一致率、監査Precision/Recallを確認。
- [ ] p50/p95推論レイテンシ・同時実行数・タイムアウトを測る。現状APIは同期推論で最大約195秒待機する。
- [ ] ALBのhealth checkは `/health/live`。LLM不調時もルール監査は動かし、監視ではreadyの失敗を別アラートにする。
- [ ] 障害時のサービス別CloudWatchログ、ECS task停止原因、Cloud Map DNSを確認できること。
- [ ] **月額見積と予算アラート**（Fargate常時1タスク×2、ALB、CloudFront、ログ、転送料、S3）を設定。`terraform apply`は無料ではない。
- [ ] 二重デプロイ時のリソース名衝突、既存イメージのrollback、`terraform destroy`前のS3内容削除条件を確認。

## D. 具体的なsmoke test（架空データのみ）

```bash
terraform fmt -check -recursive
terraform init -backend=false
terraform validate
terraform plan -var-file=terraform.tfvars
# apply はレビュー後のみ。以下は構築できた場合の確認例。
aws ecs list-services --cluster nrl-demo --region ap-northeast-1
curl -i 'https://<CloudFront-domain>/api/inference/status'
curl -i -X POST 'https://<CloudFront-domain>/api/audit' \
  -H 'Content-Type: application/json' \
  --data '{"narrative":"転倒は認めず","record":{"fall_status":"unknown","dizziness_status":"unknown","assistance_status":"unknown"},"use_llm":false}'
```

最後のJSONは説明用です。実際のAPI Pydanticスキーマとの一致は `http://localhost:8000/docs` または `backend/app/schemas.py` で確認してください。

**出典**: [AWS ECS Service Discovery](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-discovery.html) · [CloudFront OAC](https://docs.aws.amazon.com/AmazonCloudFront/latest/DeveloperGuide/private-content-restricting-access-to-s3.html) · [ECS Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)
