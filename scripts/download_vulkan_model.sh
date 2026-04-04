#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MODELS_DIR="${MODELS_DIR:-$ROOT_DIR/models}"
REPO="${RETRIEVER_GGUF_REPO:-Qwen/Qwen3-Embedding-0.6B-GGUF}"
FILE="${RETRIEVER_GGUF_FILE:-Qwen3-Embedding-0.6B-f16.gguf}"
OUT_PATH="$MODELS_DIR/$FILE"
URL="https://huggingface.co/$REPO/resolve/main/$FILE"

mkdir -p "$MODELS_DIR"

echo "Downloading: $REPO/$FILE"
echo "Target: $OUT_PATH"
curl -L --fail --retry 3 --continue-at - -o "$OUT_PATH" "$URL"

echo "Download complete: $OUT_PATH"