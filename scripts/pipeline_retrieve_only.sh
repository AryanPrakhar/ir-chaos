#!/usr/bin/env bash
set -euo pipefail

# Retrieval-only pipeline: retrieves and reranks results without inference
#
# Usage:
#   ./scripts/pipeline_retrieve_only.sh "your query" [retrieve-k] [rerank-k]
#
# Optional environment variables:
#   CONTAINER_ENGINE=podman|docker
#   RETRIEVER_IMAGE=krkn-retriever:v1
#   RETRIEVER_DOCKERFILE=/path/to/Dockerfile
#   RETRIEVER_BACKEND=auto|torch|vulkan
#   RETRIEVER_ACCELERATION=auto|gpu|cpu
#   LLAMA_EMBED_MODEL=/abs/path/to/model.gguf
#   LLAMA_GPU_LAYERS=-1
#   RETRIEVER_GGUF_REPO=Qwen/Qwen3-Embedding-0.6B-GGUF
#   RETRIEVER_GGUF_FILE=Qwen3-Embedding-0.6B-f16.gguf
#   RETRIEVER_AUTO_DOWNLOAD_MODEL=1
#   RETRIEVER_FORCE_BUILD=1
#   HF_CACHE_DIR, TORCH_CACHE_DIR
#
# Output:
#   retrieval container writes ./shared/retrieval_output.json

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"<query>\" [retrieve-k] [rerank-k]"
  echo "Defaults: retrieve-k=10, rerank-k=5"
  echo "Optional env: RETRIEVER_ACCELERATION=auto|gpu|cpu RETRIEVER_FORCE_BUILD=1"
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
ENGINE="${CONTAINER_ENGINE:-podman}"
IMAGE="${RETRIEVER_IMAGE:-krkn-retriever:v1}"
DOCKERFILE="${RETRIEVER_DOCKERFILE:-$ROOT_DIR/krkn-retriever/Dockerfile}"
FORCE_BUILD="${RETRIEVER_FORCE_BUILD:-0}"
BACKEND="${RETRIEVER_BACKEND:-auto}"
LLAMA_EMBED_MODEL_PATH="${LLAMA_EMBED_MODEL:-}"
LLAMA_GPU_LAYERS="${LLAMA_GPU_LAYERS:--1}"
GGUF_REPO="${RETRIEVER_GGUF_REPO:-Qwen/Qwen3-Embedding-0.6B-GGUF}"
GGUF_FILE="${RETRIEVER_GGUF_FILE:-Qwen3-Embedding-0.6B-f16.gguf}"
AUTO_DOWNLOAD_MODEL="${RETRIEVER_AUTO_DOWNLOAD_MODEL:-1}"
ACCELERATION_MODE="${RETRIEVER_ACCELERATION:-auto}"

# Auto-detect host OS
HOST_OS="$(uname -s | tr '[:upper:]' '[:lower:]')"

case "$ACCELERATION_MODE" in
  auto|gpu|cpu) ;;
  *) echo "Error: RETRIEVER_ACCELERATION must be one of auto|gpu|cpu"; exit 1 ;;
esac

case "$BACKEND" in
  auto|torch|vulkan) ;;
  *) echo "Error: RETRIEVER_BACKEND must be one of auto|torch|vulkan"; exit 1 ;;
esac

if ! command -v "$ENGINE" >/dev/null 2>&1; then
  echo "Error: container engine '$ENGINE' not found"
  exit 1
fi

# Build-time args (auto-detected based on host platform)
BUILD_ARGS=()
GPU_FLAGS=()
DEVICE_ARGS=(--device auto)
LLAMA_MOUNT_ARGS=()
GPU_RUNTIME_KIND="none"

MOUNT_LABEL_SUFFIX=""
if [[ "$ENGINE" == "podman" ]]; then
  MOUNT_LABEL_SUFFIX=":Z"
fi

now_ms() { date +%s%3N; }

nvidia_runtime_available() {
  [[ "$ENGINE" == "podman" ]] || return 1
  "$ENGINE" run --rm \
    --device nvidia.com/gpu=all \
    --security-opt=label=disable \
    --entrypoint nvidia-smi \
    "$IMAGE" >/dev/null 2>&1
}

gpu_runtime_supported() {
  [[ "$ENGINE" == "podman" ]] || return 1
  "$ENGINE" run --rm \
    --device nvidia.com/gpu=all \
    --security-opt=label=disable \
    --entrypoint python3 \
    "$IMAGE" \
    -c "import torch; x=torch.tensor([1.0], device='cuda'); print((x+1).cpu().item())" >/dev/null 2>&1
}

podman_dri_runtime_supported() {
  [[ "$ENGINE" == "podman" ]] || return 1
  "$ENGINE" run --rm \
    --device /dev/dri \
    --entrypoint sh \
    "$IMAGE" \
    -c "test -e /dev/dri/renderD128 || test -e /dev/dri/card0" >/dev/null 2>&1
}

image_torch_runtime() {
  "$ENGINE" run --rm --entrypoint python3 "$IMAGE" \
    -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available())" 2>/dev/null || true
}

image_is_compatible() {
  if [[ "$BACKEND" == "vulkan" ]]; then
    "$ENGINE" run --rm --entrypoint python3 "$IMAGE" -c "import faiss, llama_cpp" >/dev/null 2>&1
  else
    "$ENGINE" run --rm --entrypoint python3 "$IMAGE" -c "import faiss" >/dev/null 2>&1
  fi
}

download_gguf_model() {
  local out_path="$1"
  local url="https://huggingface.co/${GGUF_REPO}/resolve/main/${GGUF_FILE}"
  echo "      Downloading GGUF model: ${GGUF_REPO}/${GGUF_FILE}"
  mkdir -p "$(dirname "$out_path")"
  curl -L --fail --retry 3 --continue-at - -o "$out_path" "$url"
}

configure_acceleration() {
  GPU_FLAGS=()
  DEVICE_ARGS=(--device auto)
  GPU_RUNTIME_KIND="none"

  # CPU-only mode: no GPU probing, no GPU build args
  if [[ "$ACCELERATION_MODE" == "cpu" ]]; then
    BUILD_ARGS+=(--build-arg MACOS_MESA_KRUNKIT=0)
    BUILD_ARGS+=(--build-arg NVIDIA_EGL_ICD=0)
    BUILD_ARGS+=(--build-arg TORCH_BUILD=cpu)
    DEVICE_ARGS=(--device cpu --cpu-only)
    return
  fi

  # macOS Apple Silicon: Venus/libkrun/MoltenVK pipeline
  if [[ "$HOST_OS" == "darwin" || "$HOST_OS" == "macos" ]]; then
    BUILD_ARGS+=(--build-arg MACOS_MESA_KRUNKIT=1)
    BUILD_ARGS+=(--build-arg NVIDIA_EGL_ICD=0)
    BUILD_ARGS+=(--build-arg TORCH_BUILD=cpu)

    if podman_dri_runtime_supported; then
      GPU_FLAGS=(--device /dev/dri)
      GPU_RUNTIME_KIND="podman-dri-venus"
    else
      echo "Warning: /dev/dri not found in Podman VM — falling back to CPU"
      echo "         Ensure Podman machine uses applehv provider and has render nodes."
    fi
    return
  fi

  # Linux: NVIDIA CUDA → DRI fallback
  BUILD_ARGS+=(--build-arg MACOS_MESA_KRUNKIT=0)

  if [[ "$BACKEND" == "vulkan" ]]; then
    # Vulkan backend: probe NVIDIA first (runtime only), then DRI
    if nvidia_runtime_available; then
      BUILD_ARGS+=(--build-arg NVIDIA_EGL_ICD=1)
      BUILD_ARGS+=(--build-arg TORCH_BUILD=auto)
      GPU_FLAGS=(--device nvidia.com/gpu=all --security-opt=label=disable)
      GPU_RUNTIME_KIND="nvidia-cuda"
    elif podman_dri_runtime_supported; then
      BUILD_ARGS+=(--build-arg NVIDIA_EGL_ICD=0)
      BUILD_ARGS+=(--build-arg TORCH_BUILD=auto)
      GPU_FLAGS=(--device /dev/dri)
      GPU_RUNTIME_KIND="podman-dri"
    else
      BUILD_ARGS+=(--build-arg NVIDIA_EGL_ICD=1)
      BUILD_ARGS+=(--build-arg TORCH_BUILD=auto)
      if [[ "$ACCELERATION_MODE" == "gpu" ]]; then
        echo "Warning: GPU mode requested but no GPU runtime available; falling back to CPU"
      fi
    fi
    return
  fi

  # Torch backend on Linux
  BUILD_ARGS+=(--build-arg NVIDIA_EGL_ICD=1)
  BUILD_ARGS+=(--build-arg TORCH_BUILD=auto)

  if gpu_runtime_supported; then
    GPU_FLAGS=(--device nvidia.com/gpu=all --security-opt=label=disable)
    GPU_RUNTIME_KIND="nvidia-cuda"
    DEVICE_ARGS=(--device cuda)
  elif [[ "$ACCELERATION_MODE" == "gpu" ]]; then
    echo "Warning: GPU mode requested but GPU runtime unavailable; falling back to CPU"
    DEVICE_ARGS=(--device cpu --cpu-only)
  fi
}

build_image() {
  "$ENGINE" build \
    -t "$IMAGE" \
    -f "$DOCKERFILE" \
    "${BUILD_ARGS[@]}" \
    "$ROOT_DIR"
}

# ── Setup ──

mkdir -p "$SHARED_DIR" "$HF_CACHE_DIR" "$TORCH_CACHE_DIR"

# Resolve GGUF model for vulkan backend
if [[ "$BACKEND" == "vulkan" ]]; then
  if [[ -z "$LLAMA_EMBED_MODEL_PATH" ]]; then
    LLAMA_EMBED_MODEL_PATH="$ROOT_DIR/models/$GGUF_FILE"
  fi

  if [[ ! -f "$LLAMA_EMBED_MODEL_PATH" && "$AUTO_DOWNLOAD_MODEL" == "1" ]]; then
    if ! command -v curl >/dev/null 2>&1; then
      echo "Error: curl is required to auto-download GGUF models"; exit 1
    fi
    download_gguf_model "$LLAMA_EMBED_MODEL_PATH"
  fi

  if [[ ! -f "$LLAMA_EMBED_MODEL_PATH" ]]; then
    echo "Error: Vulkan backend needs a GGUF embedding model file"
    echo "       Expected: $LLAMA_EMBED_MODEL_PATH"
    echo "       Set LLAMA_EMBED_MODEL or keep RETRIEVER_AUTO_DOWNLOAD_MODEL=1"
    exit 1
  fi

  LLAMA_MODEL_ABS="$(cd "$(dirname "$LLAMA_EMBED_MODEL_PATH")" && pwd)/$(basename "$LLAMA_EMBED_MODEL_PATH")"
  LLAMA_MODEL_BASENAME="$(basename "$LLAMA_MODEL_ABS")"
  LLAMA_EMBED_MODEL_PATH="/models/$LLAMA_MODEL_BASENAME"
  LLAMA_MOUNT_ARGS=(-v "$(dirname "$LLAMA_MODEL_ABS"):/models$MOUNT_LABEL_SUFFIX")
fi

# ── Configure acceleration (sets BUILD_ARGS, GPU_FLAGS, DEVICE_ARGS) ──

configure_acceleration

# ── Banner ──

echo "========================================"
echo "Krkn Retrieval-Only Pipeline"
echo "========================================"
echo "Query: $QUERY"
echo "Retrieve-K: $RETRIEVE_K  |  Rerank-K: $RERANK_K"
echo "Engine: $ENGINE  |  Image: $IMAGE"
echo "Host OS: $HOST_OS  |  Backend: $BACKEND"
echo "Acceleration: $ACCELERATION_MODE  |  GPU runtime: $GPU_RUNTIME_KIND"
echo "LLAMA_EMBED_MODEL: ${LLAMA_EMBED_MODEL_PATH:-<not-set>}"
echo "Build args: ${BUILD_ARGS[*]:-<none>}"
echo "Output: $SHARED_DIR/retrieval_output.json"
echo "========================================"
echo ""

TOTAL_START_MS="$(now_ms)"

# ── [1/3] Build image ──

echo "[1/3] Building retriever container image"
STEP_START_MS="$(now_ms)"
if [[ "$FORCE_BUILD" == "1" ]]; then
  echo "      RETRIEVER_FORCE_BUILD=1 — rebuilding image"
  build_image
elif "$ENGINE" image exists "$IMAGE"; then
  if image_is_compatible; then
    echo "      Image $IMAGE already present and compatible, skipping build"
  else
    echo "      Existing image incompatible, rebuilding..."
    build_image
  fi
else
  echo "      Building image..."
  build_image
fi
STEP_END_MS="$(now_ms)"
echo "      Step time: $((STEP_END_MS - STEP_START_MS))ms"
echo "      Torch runtime in image:"
image_torch_runtime | sed 's/^/        /'

echo "      Device args: ${DEVICE_ARGS[*]}"
if [[ ${#GPU_FLAGS[@]} -gt 0 ]]; then
  echo "      GPU flags: ${GPU_FLAGS[*]} (${GPU_RUNTIME_KIND})"
else
  echo "      GPU flags: disabled"
fi

# ── [2/3] Ensure FAISS index ──

echo ""
echo "[2/3] Ensuring FAISS index exists"
STEP_START_MS="$(now_ms)"
if [[ -f "$INDEX_FILE" && -f "$META_FILE" ]]; then
  echo "      FAISS index already present, skipping indexing"
else
  echo "      FAISS index missing, building now..."
  "$ENGINE" run --rm \
    "${GPU_FLAGS[@]}" \
    --entrypoint python3 \
    "${LLAMA_MOUNT_ARGS[@]}" \
    -v "$ROOT_DIR/krkn-retriever:/app$MOUNT_LABEL_SUFFIX" \
    -v "$ROOT_DIR/docs:/app/docs$MOUNT_LABEL_SUFFIX" \
    -v "$HF_CACHE_DIR:/root/.cache/huggingface$MOUNT_LABEL_SUFFIX" \
    -v "$TORCH_CACHE_DIR:/root/.cache/torch$MOUNT_LABEL_SUFFIX" \
    -e DOCS_DIR=/app/docs \
    -e RETRIEVER_BACKEND="$BACKEND" \
    -e LLAMA_EMBED_MODEL="$LLAMA_EMBED_MODEL_PATH" \
    -e LLAMA_GPU_LAYERS="$LLAMA_GPU_LAYERS" \
    -e HF_HOME=/root/.cache/huggingface \
    -e SENTENCE_TRANSFORMERS_HOME=/root/.cache/huggingface \
    -e TORCH_HOME=/root/.cache/torch \
    -w /app \
    "$IMAGE" \
    retriever.py "${DEVICE_ARGS[@]}" index
fi
STEP_END_MS="$(now_ms)"
echo "      Step time: $((STEP_END_MS - STEP_START_MS))ms"

# ── [3/3] Retrieval + reranking ──

echo ""
echo "[3/3] Running retrieval and reranking query"
STEP_START_MS="$(now_ms)"
"$ENGINE" run --rm \
  "${GPU_FLAGS[@]}" \
  --entrypoint python3 \
  "${LLAMA_MOUNT_ARGS[@]}" \
  -v "$ROOT_DIR/krkn-retriever:/app$MOUNT_LABEL_SUFFIX" \
  -v "$ROOT_DIR/docs:/app/docs$MOUNT_LABEL_SUFFIX" \
  -v "$SHARED_DIR:/io$MOUNT_LABEL_SUFFIX" \
  -v "$HF_CACHE_DIR:/root/.cache/huggingface$MOUNT_LABEL_SUFFIX" \
  -v "$TORCH_CACHE_DIR:/root/.cache/torch$MOUNT_LABEL_SUFFIX" \
  -e DOCS_DIR=/app/docs \
  -e RETRIEVER_BACKEND="$BACKEND" \
  -e LLAMA_EMBED_MODEL="$LLAMA_EMBED_MODEL_PATH" \
  -e LLAMA_GPU_LAYERS="$LLAMA_GPU_LAYERS" \
  -e HF_HOME=/root/.cache/huggingface \
  -e SENTENCE_TRANSFORMERS_HOME=/root/.cache/huggingface \
  -e TORCH_HOME=/root/.cache/torch \
  -w /app \
  "$IMAGE" \
  retriever.py "${DEVICE_ARGS[@]}" query "$QUERY" \
    --retrieve-k "$RETRIEVE_K" \
    --rerank-k "$RERANK_K" \
    --export /io/retrieval_output.json \
    --include-text
STEP_END_MS="$(now_ms)"
echo "      Step time: $((STEP_END_MS - STEP_START_MS))ms"

TOTAL_END_MS="$(now_ms)"

echo ""
echo "Done! Results saved to: $SHARED_DIR/retrieval_output.json"
echo "Total elapsed: $((TOTAL_END_MS - TOTAL_START_MS))ms"
