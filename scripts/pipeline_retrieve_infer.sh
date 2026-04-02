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

# Optional runtime knobs for inference container.
# Examples:
#   export INFERENCE_GPU_MODE=vulkan
#   export INFERENCE_PODMAN_DEVICE=/dev/dri/renderD128
#   export INFERENCE_PODMAN_SECURITY_OPT=label=disable
INFERENCE_IMAGE="${INFERENCE_IMAGE:-krkn-inference:v1}"
INFERENCE_GPU_MODE="${INFERENCE_GPU_MODE:-}"
INFERENCE_PODMAN_DEVICE="${INFERENCE_PODMAN_DEVICE:-}"
INFERENCE_PODMAN_SECURITY_OPT="${INFERENCE_PODMAN_SECURITY_OPT:-}"
PIPELINE_TIMING_LOG="${PIPELINE_TIMING_LOG:-}"

now_epoch() {
  date +%s
}

log_timing() {
  local message="$1"
  echo "$message"
  if [[ -n "$PIPELINE_TIMING_LOG" ]]; then
    printf '%s\n' "$message" >> "$PIPELINE_TIMING_LOG"
  fi
}

# Recommended small-but-strong local model for llama.cpp inference.
DEFAULT_MODEL_PATH="$ROOT_DIR/models/Qwen2.5-3B-Instruct-Q4_K_M.gguf"
MODEL_PATH="${2:-${LLM_MODEL_PATH:-$DEFAULT_MODEL_PATH}}"
SKIP_INFERENCE="${SKIP_INFERENCE:-}"

MODEL_AVAILABLE="true"
if [[ ! -f "$MODEL_PATH" ]]; then
  if [[ -z "$SKIP_INFERENCE" ]]; then
    echo "Model file not found: $MODEL_PATH"
    echo "Pass a model path as arg2 or set LLM_MODEL_PATH, or set SKIP_INFERENCE=1 for retrieval-only test mode."
    exit 1
  fi
  MODEL_AVAILABLE="false"
  echo "WARNING: Model not found, running in retrieval-only test mode."
fi

if [[ "$MODEL_AVAILABLE" == "true" ]]; then
  MODEL_DIR="$(dirname "$MODEL_PATH")"
  MODEL_FILE="$(basename "$MODEL_PATH")"
else
  MODEL_DIR=""
  MODEL_FILE=""
fi

mkdir -p "$SHARED_DIR"

RUN_START_EPOCH="$(now_epoch)"

echo "[1/5] Ensuring retrieval image exists"
STEP_START_EPOCH="$(now_epoch)"
if podman image exists krkn-retriever:v1; then
  echo "Image krkn-retriever:v1 already present, skipping build"
else
  podman build -t krkn-retriever:v1 -f "$ROOT_DIR/krkn-retriever/Dockerfile" "$ROOT_DIR"
fi
log_timing "[timing] retrieval_image_step_seconds=$(( $(now_epoch) - STEP_START_EPOCH ))"

echo "[2/5] Ensuring inference image exists"
if [[ "$MODEL_AVAILABLE" == "false" ]]; then
  echo "Skipping inference image (test mode - no model)"
  STEP_START_EPOCH="$(now_epoch)"
  log_timing "[timing] inference_image_step_seconds=0 (skipped_test_mode=true)"
else
  STEP_START_EPOCH="$(now_epoch)"
  if podman image exists "$INFERENCE_IMAGE"; then
    echo "Image $INFERENCE_IMAGE already present, skipping build"
  else
    podman build -t "$INFERENCE_IMAGE" -f "$ROOT_DIR/inference/Dockerfile" "$ROOT_DIR"
  fi
  log_timing "[timing] inference_image_step_seconds=$(( $(now_epoch) - STEP_START_EPOCH ))"
fi

echo "[3/5] Ensuring index exists (build once unless missing)"
STEP_START_EPOCH="$(now_epoch)"
if [[ -f "$INDEX_FILE" && -f "$META_FILE" ]]; then
  echo "FAISS index already present, skipping indexing"
  log_timing "[timing] index_step_seconds=0 (skipped_existing_index=true)"
else
  echo "FAISS index missing, building now"
  podman run --rm \
    -v "$ROOT_DIR/krkn-retriever:/app:Z" \
    -v "$ROOT_DIR/docs:/app/docs:Z" \
    -e DOCS_DIR=/app/docs \
    -w /app \
    krkn-retriever:v1 \
    python3 retriever.py index
  log_timing "[timing] index_step_seconds=$(( $(now_epoch) - STEP_START_EPOCH ))"
fi

echo "[4/5] Running retrieval and exporting JSON"
STEP_START_EPOCH="$(now_epoch)"
podman run --rm \
  -v "$ROOT_DIR/krkn-retriever:/app:Z" \
  -v "$ROOT_DIR/docs:/app/docs:Z" \
  -v "$SHARED_DIR:/io:Z" \
  -e DOCS_DIR=/app/docs \
  -w /app \
  krkn-retriever:v1 \
  python3 retriever.py query "$QUERY" --retrieve-k 10 --rerank-k 5 --export /io/retrieval_output.json --include-text
log_timing "[timing] retrieval_step_seconds=$(( $(now_epoch) - STEP_START_EPOCH ))"

echo "[5/5] Running inference with retrieval output"
if [[ "$MODEL_AVAILABLE" == "false" ]]; then
  echo "Skipping inference (test mode - no model)"
  log_timing "[timing] inference_step_seconds=0 (skipped_test_mode=true)"
else
  STEP_START_EPOCH="$(now_epoch)"
  INFERENCE_RUN_ARGS=()
  if [[ -n "$INFERENCE_PODMAN_DEVICE" ]]; then
    INFERENCE_RUN_ARGS+=(--device "$INFERENCE_PODMAN_DEVICE")
  fi
  if [[ -n "$INFERENCE_PODMAN_SECURITY_OPT" ]]; then
    INFERENCE_RUN_ARGS+=(--security-opt "$INFERENCE_PODMAN_SECURITY_OPT")
  fi
  if [[ -n "$INFERENCE_GPU_MODE" ]]; then
    INFERENCE_RUN_ARGS+=(-e "GPU_MODE=$INFERENCE_GPU_MODE")
  fi

  podman run --rm \
    "${INFERENCE_RUN_ARGS[@]}" \
    -v "$SHARED_DIR:/io:Z" \
    -v "$MODEL_DIR:/models:Z" \
    "$INFERENCE_IMAGE" \
    python3 /app/run_inference.py \
      --input /io/retrieval_output.json \
      --output /io/inference_output.json \
      --model "/models/$MODEL_FILE"
  log_timing "[timing] inference_step_seconds=$(( $(now_epoch) - STEP_START_EPOCH ))"

  if [[ -f "$SHARED_DIR/inference_output.json" ]]; then
    GPU_MODE_VALUE="$(grep -m1 '"gpu_mode"' "$SHARED_DIR/inference_output.json" | sed -E 's/.*: "([^"]+)".*/\1/' || true)"
    GPU_LAYERS_VALUE="$(grep -m1 '"n_gpu_layers"' "$SHARED_DIR/inference_output.json" | sed -E 's/.*: ([0-9-]+).*/\1/' || true)"
    if [[ -n "$GPU_MODE_VALUE" ]]; then
      log_timing "[acceleration] gpu_mode=$GPU_MODE_VALUE n_gpu_layers=${GPU_LAYERS_VALUE:-unknown}"
    fi
  fi
fi

log_timing "[timing] total_pipeline_seconds=$(( $(now_epoch) - RUN_START_EPOCH ))"

echo "Done. Files written:"
echo "  $SHARED_DIR/retrieval_output.json"
if [[ "$MODEL_AVAILABLE" == "true" ]]; then
  echo "  $SHARED_DIR/inference_output.json"
  echo "Model used: $MODEL_PATH"
else
  echo "(Inference skipped - test mode)"
fi
