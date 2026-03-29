#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./scripts/pipeline_retrieve_infer.sh "your query" [path-to-model.gguf]
#
# Data flow:
#   retrieval container writes ./shared/retrieval_output.json
#   inference container reads that file and writes ./shared/inference_output.json

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"<query>\" [path-to-model.gguf]"
  exit 1
fi

QUERY="$1"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SHARED_DIR="$ROOT_DIR/shared"
INDEX_FILE="$ROOT_DIR/krkn-retriever/faiss-index/krkn-scenarios.index"
META_FILE="$ROOT_DIR/krkn-retriever/faiss-index/krkn-scenarios.meta"

# Recommended small-but-strong local model for llama.cpp inference.
DEFAULT_MODEL_PATH="$ROOT_DIR/models/Qwen2.5-3B-Instruct-Q4_K_M.gguf"
MODEL_PATH="${2:-${LLM_MODEL_PATH:-$DEFAULT_MODEL_PATH}}"

if [[ ! -f "$MODEL_PATH" ]]; then
  echo "Model file not found: $MODEL_PATH"
  echo "Pass a model path as arg2 or set LLM_MODEL_PATH."
  exit 1
fi

MODEL_DIR="$(dirname "$MODEL_PATH")"
MODEL_FILE="$(basename "$MODEL_PATH")"

mkdir -p "$SHARED_DIR"

echo "[1/5] Ensuring retrieval image exists"
if podman image exists krkn-retriever:v1; then
  echo "Image krkn-retriever:v1 already present, skipping build"
else
  podman build -t krkn-retriever:v1 -f "$ROOT_DIR/krkn-retriever/Dockerfile" "$ROOT_DIR"
fi

echo "[2/5] Ensuring inference image exists"
if podman image exists krkn-inference:v1; then
  echo "Image krkn-inference:v1 already present, skipping build"
else
  podman build -t krkn-inference:v1 -f "$ROOT_DIR/inference/Dockerfile" "$ROOT_DIR"
fi

echo "[3/5] Ensuring index exists (build once unless missing)"
if [[ -f "$INDEX_FILE" && -f "$META_FILE" ]]; then
  echo "FAISS index already present, skipping indexing"
else
  echo "FAISS index missing, building now"
  podman run --rm \
    -v "$ROOT_DIR/krkn-retriever:/app:Z" \
    -v "$ROOT_DIR/docs:/app/docs:Z" \
    -e DOCS_DIR=/app/docs \
    -w /app \
    krkn-retriever:v1 \
    python3 retriever.py index
fi

echo "[4/5] Running retrieval and exporting JSON"
podman run --rm \
  -v "$ROOT_DIR/krkn-retriever:/app:Z" \
  -v "$ROOT_DIR/docs:/app/docs:Z" \
  -v "$SHARED_DIR:/io:Z" \
  -e DOCS_DIR=/app/docs \
  -w /app \
  krkn-retriever:v1 \
  python3 retriever.py query "$QUERY" --retrieve-k 10 --rerank-k 5 --export /io/retrieval_output.json --include-text

echo "[5/5] Running inference with retrieval output"
podman run --rm \
  -v "$SHARED_DIR:/io:Z" \
  -v "$MODEL_DIR:/models:Z" \
  krkn-inference:v1 \
  python3 /app/run_inference.py \
    --input /io/retrieval_output.json \
    --output /io/inference_output.json \
    --model "/models/$MODEL_FILE"

echo "Done. Files written:"
echo "  $SHARED_DIR/retrieval_output.json"
echo "  $SHARED_DIR/inference_output.json"
echo "Model used: $MODEL_PATH"
