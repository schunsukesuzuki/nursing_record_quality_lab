# Ollama build-time model image (AWS/GCP scaffold)

Local Compose の `model-init` は従来どおり利用できますが、クラウドでインスタンスがスケールするたびに `ollama pull` を実行するのは非効率です。このサンプルでは **ビルド時に `qwen3:0.6b` をダウンロードしてレイヤーに格納**し、推論APIコンテナと同一タスク／インスタンス上でサイドカー起動する方式を例示します。

```bash
# リポジトリ直下から（CPUアーキテクチャの違いに注意）
docker build --platform linux/amd64 \
  -f deploy/shared/ollama/Dockerfile \
  --build-arg MODEL_NAME=qwen3:0.6b \
  -t nrl-ollama-preloaded:demo .
docker run --rm nrl-ollama-preloaded:demo list
```

- 初回ビルドはネットワークが必要。Ollamaのベースイメージは本番では **タグでなくdigestを固定**してください。
- `list` で登録確認後、ECR / Artifact Registryにpushし、`ollama_image`にそのイメージURIを設定します。
- **モデルバイナリを固定したという証拠にはタグだけでは不十分**です。ビルド後のイメージdigestと、可能ならモデルのmanifest/digestもCIで保管します。
- このDockerfileは実験用の手順例で、利用環境のアーキテクチャ・Ollamaのバージョンによって調整が必要です。OCIイメージに格納するためサイズが大きくなります。ライセンスや再配布条件は別途確認してください。
- ビルド中は `OLLAMA_HOST=127.0.0.1:11434`、Cloud Run実行時はstartup probeのため `OLLAMA_HOST=0.0.0.0:11434` に上書きします。Ollamaは同一インスタンス内のサイドカー用で、**ingressコンテナとして公開しない**でください。
