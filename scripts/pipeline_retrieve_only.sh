#!/usr/bin/env bash
set -euo pipefail

# Retrieval-only pipeline: retrieves and reranks results without inference
#
# Usage:
#   ./scripts/pipeline_retrieve_only.sh "your query" [retrieve-k] [rerank-k]
#
# Output:
#   retrieval container writes ./shared/retrieval_output.json

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"<query>\" [retrieve-k] [rerank-k]"
  echo "Defaults: retrieve-k=10, rerank-k=5"
  exit 1
fi

QUERY="$1"
RETRIEVE_K="${2:-10}"
RERANK_K="${3:-5}"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SHARED_DIR="$ROOT_DIR/shared"
INDEX_FILE="$ROOT_DIR/krkn-retriever/faiss-index/krkn-scenarios.index"
META_FILE="$ROOT_DIR/krkn-retriever/faiss-index/krkn-scenarios.meta"
HF_CACHE_DIR="${HF_CACHE_DIR:-$ROOT_DIR/.cache/huggingface}"
TORCH_CACHE_DIR="${TORCH_CACHE_DIR:-$ROOT_DIR/.cache/torch}"

mkdir -p "$SHARED_DIR"
mkdir -p "$HF_CACHE_DIR"
mkdir -p "$TORCH_CACHE_DIR"

echo "========================================"
echo "Krkn Retrieval-Only Pipeline"
echo "========================================"
echo "Query: $QUERY"
echo "Retrieve-K: $RETRIEVE_K"
echo "Rerank-K: $RERANK_K"
echo "Output: $SHARED_DIR/retrieval_output.json"
echo "========================================"
echo ""

echo "[1/3] Building retriever container image"
if podman image exists krkn-retriever:v1; then
  echo "      Image krkn-retriever:v1 already present, skipping build"
else
  echo "      Building image..."
  podman build -t krkn-retriever:v1 -f "$ROOT_DIR/krkn-retriever/Dockerfile" "$ROOT_DIR"
fi

echo ""
echo "[2/3] Ensuring FAISS index exists"
if [[ -f "$INDEX_FILE" && -f "$META_FILE" ]]; then
  echo "      FAISS index already present, skipping indexing"
else
  echo "      FAISS index missing, building now..."
  podman run --rm \
    -v "$ROOT_DIR/krkn-retriever:/app:Z" \
    -v "$ROOT_DIR/docs:/app/docs:Z" \
    -v "$HF_CACHE_DIR:/root/.cache/huggingface:Z" \
    -v "$TORCH_CACHE_DIR:/root/.cache/torch:Z" \
    -e DOCS_DIR=/app/docs \
    -e HF_HOME=/root/.cache/huggingface \
    -e SENTENCE_TRANSFORMERS_HOME=/root/.cache/huggingface \
    -e TORCH_HOME=/root/.cache/torch \
    -w /app \
    krkn-retriever:v1 \
    python3 retriever.py index
fi

echo ""
echo "[3/3] Running retrieval and reranking query"
podman run --rm \
  -v "$ROOT_DIR/krkn-retriever:/app:Z" \
  -v "$ROOT_DIR/docs:/app/docs:Z" \
  -v "$SHARED_DIR:/io:Z" \
  -v "$HF_CACHE_DIR:/root/.cache/huggingface:Z" \
  -v "$TORCH_CACHE_DIR:/root/.cache/torch:Z" \
  -e DOCS_DIR=/app/docs \
  -e HF_HOME=/root/.cache/huggingface \
  -e SENTENCE_TRANSFORMERS_HOME=/root/.cache/huggingface \
  -e TORCH_HOME=/root/.cache/torch \
  -w /app \
  krkn-retriever:v1 \
  python3 retriever.py query "$QUERY" \
    --retrieve-k "$RETRIEVE_K" \
    --rerank-k "$RERANK_K" \
    --export /io/retrieval_output.json \
    --include-text

echo ""
echo "✓ Retrieval completed successfully!"
echo "✓ Results saved to: $SHARED_DIR/retrieval_output.json"
echo ""
