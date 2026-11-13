#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
printf '%s\n' '== Docker Compose services (including exited jobs) =='
docker compose ps -a
printf '\n%s\n' '== Ollama models =='
docker compose exec -T ollama ollama list || true
printf '\n%s\n' '== Inference process liveness =='
docker compose exec -T inference python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8100/health/live', timeout=5).read().decode())" || true
printf '\n%s\n' '== Inference readiness (from backend) =='
curl -fsS http://localhost:8000/api/inference/status || true
printf '\n\n%s\n' '== Model initialization and inference logs =='
docker compose logs --tail=100 model-init inference ollama
printf '\n%s\n' '== Note: test only synthetic data; no patient information. =='
