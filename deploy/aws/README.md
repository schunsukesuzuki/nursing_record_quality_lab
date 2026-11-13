# AWS へのサービス別配置案（設計資料、IaC未実装）

## マッピング

| Local component | AWS option | Purpose |
|---|---|---|
| `frontend` Vite `dist/` | S3 + CloudFront | CDN配信。ビルド時に公開APIのURLを設定 |
| `backend` container | ECS Fargate + ALB or API Gateway | Stateless public API, auth layer, autoscaling |
| `inference` container | private ECS service | Ollamaから分離されたJSON抽出API。独立デプロイ |
| Ollama/other runner | CPUならECS Fargateも可能。GPU必要時はECS on EC2 / ECS Managed Instances | モデル重みと推論プロセス |
| `model-init` | Local-only | 本番ではリリース時に事前取得・検証してモデルを固定 |
| Persistence (future) | S3 / RDS | 必要性・データ取扱いを検討してから |
| Async jobs (future) | SQS + worker | 大量バッチ化する場合のみ |

## 重要な点

- `INFERENCE_URL` はVPC内部のECS Service Connect名（またはprivate load balancer）を設定。Service Connectはサービス発見と接続を支援する。
- 推論サービスとモデルサーバーはprivate subnets内に置き、公開しない。TLS/最小権限/監査は別途必要。
- AWS FargateはGPUをサポートしない。GPUへ移行する場合、ECS EC2/Managed Instancesなどを選ぶ。
- モデル重みの取り扱いはイメージ同梱またはセキュアな事前配置を検討。リクエストごとのpullは禁止。
- `frontend` build: `VITE_API_BASE_URL=https://api.example.com/api` を指定。API側 `CORS_ORIGINS=https://app.example.com` を設定。
- `backend`にはCognito/OIDC等のユーザー認証を加え、ALB/API GatewayでTLS終端とレート制限を設ける。サンプルには本番認証なし。

## 個別ビルド

```bash
docker build -t nursing-backend:0.1 ./backend
docker build -t nursing-inference:0.1 ./inference
docker build --target production --build-arg VITE_API_BASE_URL=https://api.example.com/api \
  -t nursing-frontend:0.1 ./frontend
```

実際のECR push / ECS task definition / ALB / CloudFront / IAM / VPCの作成は含まれていない。

参考:
- https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-connect.html
- https://docs.aws.amazon.com/decision-guides/latest/decision-guides/choosing-aws-container-service.html
