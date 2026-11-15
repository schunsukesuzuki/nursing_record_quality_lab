# Demonstration only: freeze the resulting image by digest before any real release.
# Build can take time because ~523 MB Qwen3-0.6B is pulled at image-build time.
ARG OLLAMA_BASE=ollama/ollama:latest
FROM ${OLLAMA_BASE}
ARG MODEL_NAME=qwen3:0.6b
ENV OLLAMA_HOST=127.0.0.1:11434
RUN set -eu; \
    ollama serve >/tmp/ollama-build.log 2>&1 & \
    pid="$!"; \
    trap 'kill "$pid" 2>/dev/null || true' EXIT; \
    ready=0; \
    for i in $(seq 1 60); do \
      if ollama list >/dev/null 2>&1; then ready=1; break; fi; \
      sleep 1; \
    done; \
    test "$ready" -eq 1 || { cat /tmp/ollama-build.log; exit 1; }; \
    ollama pull "$MODEL_NAME"; \
    ollama show "$MODEL_NAME" >/dev/null
# Inherits Ollama's upstream ENTRYPOINT/CMD. Confirm with docker inspect after build.
