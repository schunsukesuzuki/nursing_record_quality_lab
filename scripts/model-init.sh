#!/bin/sh
# Local Compose-only initialization. No user input is ever passed to this script.
set -eu

: "${MODEL_NAME:?MODEL_NAME must be set}"
: "${OLLAMA_HOST:?OLLAMA_HOST must point to the ollama service}"

echo "[model-init] Checking model: ${MODEL_NAME}"
echo "[model-init] Ollama endpoint: ${OLLAMA_HOST}"
if ollama show "${MODEL_NAME}" >/dev/null 2>&1; then
  echo "[model-init] Model already present, skipping download."
  exit 0
fi

echo "[model-init] Model is missing; starting download (this may take time)."
if ! ollama pull "${MODEL_NAME}"; then
  echo "[model-init] ERROR: model download failed. Check network, DNS, HTTPS_PROXY, disk space and Ollama logs." >&2
  exit 1
fi

if ! ollama show "${MODEL_NAME}" >/dev/null 2>&1; then
  echo "[model-init] ERROR: pull reported success but model is still unavailable." >&2
  exit 1
fi

echo "[model-init] Model verified successfully: ${MODEL_NAME}"
