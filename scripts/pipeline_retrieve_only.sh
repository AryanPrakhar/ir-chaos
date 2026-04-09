#!/usr/bin/env bash
set -euo pipefail

# Retrieval-only pipeline: retrieves and reranks results without inference
#
# Usage:
#   ./scripts/pipeline_retrieve_only.sh "your query" [retrieve-k] [rerank-k] [--verbose]
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

VERBOSE=0
POSITIONAL_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --verbose) VERBOSE=1 ;;
    *) POSITIONAL_ARGS+=("$arg") ;;
  esac
done
set -- "${POSITIONAL_ARGS[@]}"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"<query>\" [retrieve-k] [rerank-k] [--verbose]"
  echo "Defaults: retrieve-k=10, rerank-k=5"
  echo "Optional: --verbose"
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

# On macOS with podman, the libkrun VM provider is required for Vulkan GPU
# passthrough via virtio-gpu/Venus.  Without this, podman silently falls back to
# the applehv provider which has no GPU device and causes llvmpipe CPU fallback.
# Respect an explicit override; default to libkrun when unset.
if [[ "$HOST_OS" == "darwin" && "$ENGINE" == "podman" ]]; then
  export CONTAINERS_MACHINE_PROVIDER="${CONTAINERS_MACHINE_PROVIDER:-libkrun}"
fi

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

ensure_podman_machine() {
  [[ "$ENGINE" == "podman" ]] || return 0

  # Ensure provider for macOS Vulkan path.
  if [[ "$HOST_OS" == "darwin" ]]; then
    export CONTAINERS_MACHINE_PROVIDER="${CONTAINERS_MACHINE_PROVIDER:-libkrun}"
  fi

  # Create machine if missing.
  if ! "$ENGINE" machine list --format "{{.Name}}" | grep -q .; then
    echo "No podman machine found. Initializing..."
    if [[ "$HOST_OS" == "darwin" ]]; then
      "$ENGINE" machine init --now --cpus 4 --memory 8192
    else
      "$ENGINE" machine init
    fi
  fi

  local machine
  machine=$("$ENGINE" machine list --format "{{.Name}}" | head -n1)
  if [[ -z "$machine" ]]; then
    echo "Error: could not determine podman machine name"
    return 1
  fi

  # On macOS, recreate applehv machine so Vulkan can use libkrun path.
  if [[ "$HOST_OS" == "darwin" ]]; then
    if "$ENGINE" machine inspect "$machine" | grep -q "applehv"; then
      echo "Recreating podman machine with libkrun (required for Vulkan): $machine"
      "$ENGINE" machine rm -f "$machine"
      "$ENGINE" machine init --now --cpus 4 --memory 8192
      machine=$("$ENGINE" machine list --format "{{.Name}}" | head -n1)
    fi
  fi

  # Start machine when stopped.
  if ! "$ENGINE" machine inspect "$machine" | grep -q '"Running": true'; then
    echo "Starting podman machine: $machine"
    "$ENGINE" machine start "$machine"
  fi
}

# Build-time args (auto-detected based on host platform)
BUILD_ARGS=()
GPU_FLAGS=()
DEVICE_ARGS=(--device auto)
LLAMA_MOUNT_ARGS=()
GPU_RUNTIME_KIND="none"
GGML_BACKEND_DESIRED=""

MOUNT_LABEL_SUFFIX=""
if [[ "$ENGINE" == "podman" ]]; then
  MOUNT_LABEL_SUFFIX=":Z"
fi

now_ms() {
  # macOS-compatible millisecond timestamp (date +%s%3N not available on macOS)
  if [[ "$HOST_OS" == "darwin" ]]; then
    python3 -c "import time; print(int(time.time() * 1000))"
  else
    date +%s%3N
  fi
}

vlog() {
  if [[ "$VERBOSE" == "1" ]]; then
    echo "$@"
  fi
}

PIPELINE_LOG="$(mktemp)"
QUERY_LOG=""
cleanup_logs() {
  rm -f "$PIPELINE_LOG"
  if [[ -n "$QUERY_LOG" ]]; then
    rm -f "$QUERY_LOG"
  fi
}
trap cleanup_logs EXIT

run_cmd() {
  if [[ "$VERBOSE" == "1" ]]; then
    "$@"
    return
  fi

  if ! "$@" >>"$PIPELINE_LOG" 2>&1; then
    echo "Error: retrieval pipeline failed."
    tail -n 40 "$PIPELINE_LOG"
    rm -f "$PIPELINE_LOG"
    exit 1
  fi
}

index_doc_count() {
  if [[ ! -f "$META_FILE" ]]; then
    echo "0"
    return
  fi
  python3 - "$META_FILE" <<'PY'
import pickle
import sys
from pathlib import Path

meta = Path(sys.argv[1])
if not meta.exists():
    print("0")
    raise SystemExit(0)
with meta.open("rb") as f:
    ids = pickle.load(f)
print(len(ids))
PY
}

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
    "$ENGINE" run --rm --entrypoint python3 "$IMAGE" -c "import faiss, llama_cpp" >/dev/null 2>&1 || return 1
  else
    "$ENGINE" run --rm --entrypoint python3 "$IMAGE" -c "import faiss" >/dev/null 2>&1 || return 1
  fi
  # Verify image was built with the right GGML backend
  if [[ -n "$GGML_BACKEND_DESIRED" ]]; then
    local image_backend
    image_backend=$("$ENGINE" run --rm --entrypoint sh "$IMAGE" -c 'echo $GGML_BACKEND_BUILT' 2>/dev/null)
    if [[ "$image_backend" != "$GGML_BACKEND_DESIRED" ]]; then
      vlog "      Image backend mismatch: built=$image_backend want=$GGML_BACKEND_DESIRED"
      return 1
    fi
  fi
}

download_gguf_model() {
  local out_path="$1"
  local url="https://huggingface.co/${GGUF_REPO}/resolve/main/${GGUF_FILE}"
  vlog "      Downloading GGUF model: ${GGUF_REPO}/${GGUF_FILE}"
  mkdir -p "$(dirname "$out_path")"
  curl -L --fail --retry 3 --continue-at - -o "$out_path" "$url"
}

configure_acceleration() {
  GPU_FLAGS=()
  DEVICE_ARGS=(--device cpu --cpu-only)
  GPU_RUNTIME_KIND="none"

  # macOS: Vulkan acceleration via libkrun + virtio-gpu + Mesa Venus.
  # The libkrun VM exposes /dev/dri inside the VM; podman does NOT forward it to
  # containers automatically.  --device /dev/dri is the one flag that bridges the
  # VM's DRM nodes into the container so Mesa Venus picks up real GPU hardware
  # instead of falling back to llvmpipe (CPU software renderer).
  if [[ "$HOST_OS" == "darwin" || "$HOST_OS" == "macos" ]]; then
    GGML_BACKEND_DESIRED="vulkan"
    BUILD_ARGS+=(--build-arg GGML_BACKEND=vulkan)
    GPU_RUNTIME_KIND="vulkan-venus"
    GPU_FLAGS=(--device /dev/dri)
    DEVICE_ARGS=(--device auto)   # let llama.cpp use Vulkan; don't force CPU
    return
  fi

  # Everything else: CPU only
  GGML_BACKEND_DESIRED="cpu"
  BUILD_ARGS+=(--build-arg GGML_BACKEND=cpu)
}

build_image() {
  "$ENGINE" build \
    -t "$IMAGE" \
    -f "$DOCKERFILE" \
    "${BUILD_ARGS[@]}" \
    "$ROOT_DIR"
}

run_engine() {
  if [[ -n "${GPU_FLAGS+x}" ]] && [[ ${#GPU_FLAGS[@]} -gt 0 ]]; then
    "$ENGINE" run --rm "${GPU_FLAGS[@]}" "$@"
  else
    "$ENGINE" run --rm "$@"
  fi
}

run_retriever_python() {
  local run_args=(--entrypoint python3)
  if [[ -n "${LLAMA_MOUNT_ARGS+x}" ]] && [[ ${#LLAMA_MOUNT_ARGS[@]} -gt 0 ]]; then
    run_args+=("${LLAMA_MOUNT_ARGS[@]}")
  fi
  run_engine "${run_args[@]}" "$@"
}

# ── Setup ──

mkdir -p "$SHARED_DIR" "$HF_CACHE_DIR" "$TORCH_CACHE_DIR"

# macOS: use llama.cpp (vulkan backend) for Vulkan GPU acceleration
if [[ "$BACKEND" == "auto" && ( "$HOST_OS" == "darwin" || "$HOST_OS" == "macos" ) ]]; then
  BACKEND="vulkan"
  vlog "macOS detected; using llama.cpp backend for Vulkan acceleration"
fi

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

if [[ "$VERBOSE" == "1" ]]; then
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
fi

TOTAL_START_MS="$(now_ms)"

# ── [1/3] Build image ──
ensure_podman_machine

vlog "[1/3] Building retriever container image"
STEP_START_MS="$(now_ms)"
if [[ "$FORCE_BUILD" == "1" ]]; then
  vlog "      RETRIEVER_FORCE_BUILD=1 — rebuilding image"
  run_cmd build_image
elif "$ENGINE" image exists "$IMAGE"; then
  if image_is_compatible; then
    vlog "      Image $IMAGE already present and compatible, skipping build"
  else
    vlog "      Existing image incompatible, rebuilding..."
    run_cmd build_image
  fi
else
  vlog "      Building image..."
  run_cmd build_image
fi
STEP_END_MS="$(now_ms)"
BUILD_MS="$((STEP_END_MS - STEP_START_MS))"
vlog "      Step time: ${BUILD_MS}ms"
if [[ "$VERBOSE" == "1" ]]; then
  echo "      Torch runtime in image:"
  image_torch_runtime | sed 's/^/        /'
fi

vlog "      Device args: ${DEVICE_ARGS[*]}"
if [[ -n "${GPU_FLAGS+x}" ]] && [[ ${#GPU_FLAGS[@]} -gt 0 ]]; then
  vlog "      GPU flags: ${GPU_FLAGS[*]} (${GPU_RUNTIME_KIND})"
else
  vlog "      GPU flags: disabled"
fi

# ── [2/3] Ensure FAISS index ──

vlog ""
vlog "[2/3] Ensuring FAISS index exists"
STEP_START_MS="$(now_ms)"
if [[ -f "$INDEX_FILE" && -f "$META_FILE" ]]; then
  vlog "      FAISS index already present, skipping indexing"
else
  vlog "      FAISS index missing, building now..."
  run_cmd run_retriever_python \
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
INDEX_MS="$((STEP_END_MS - STEP_START_MS))"
vlog "      Step time: ${INDEX_MS}ms"

# ── [3/3] Retrieval + reranking ──

vlog ""
vlog "[3/3] Running retrieval and reranking query"
STEP_START_MS="$(now_ms)"
QUERY_LOG="$(mktemp)"
if [[ "$VERBOSE" == "1" ]]; then
  if ! run_retriever_python \
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
      --include-text >"$QUERY_LOG" 2>&1; then
    echo "Error: retrieval query failed."
    cat "$QUERY_LOG"
    exit 1
  fi
else
  if ! run_retriever_python \
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
      --include-text >"$QUERY_LOG" 2>&1; then
    echo "Error: retrieval query failed."
    tail -n 40 "$QUERY_LOG"
    exit 1
  fi
fi
STEP_END_MS="$(now_ms)"
QUERY_MS="$((STEP_END_MS - STEP_START_MS))"
vlog "      Step time: ${QUERY_MS}ms"

TOTAL_END_MS="$(now_ms)"
TOTAL_MS="$((TOTAL_END_MS - TOTAL_START_MS))"

DOC_COUNT="$(index_doc_count)"
OUTPUT_PATH="$SHARED_DIR/retrieval_output.json"
SECONDS_DISPLAY="$(python3 - "$QUERY_MS" <<'PY'
import sys
ms = int(sys.argv[1])
print(f"{ms/1000.0:.1f}")
PY
)"

echo ""
echo "  Searching ${DOC_COUNT} scenarios...  done in ${SECONDS_DISPLAY}s"
echo ""
python3 - "$OUTPUT_PATH" <<'PY'
import json
import math
import sys
from pathlib import Path

FAISS_GAP = 0.07
CE_GAP = 1.0
CONF_CE_WEIGHT = 0.8
CONF_FAISS_WEIGHT = 0.2

path = Path(sys.argv[1])
if not path.exists():
    print("  No retrieval output found.")
    raise SystemExit(0)

payload = json.loads(path.read_text(encoding="utf-8"))
results = payload.get("results", [])

if not results:
    print("  No matching scenarios.")
    raise SystemExit(0)

def confidence_score(row):
    """Return the raw blended score (0.0 - 1.0) without any UX transforms."""
    ce = float(row.get("score", 0.0))
    faiss = float(row.get("retrieval_score", 0.0))
    ce_sigmoid = 1.0 / (1.0 + math.exp(-ce))
    blended = (CONF_CE_WEIGHT * ce_sigmoid) + (CONF_FAISS_WEIGHT * max(0.0, min(1.0, faiss)))
    return max(0.0, min(1.0, blended))

clear_count = 1
if len(results) >= 2:
    faiss_gap = abs(float(results[0].get("retrieval_score", 0.0)) - float(results[1].get("retrieval_score", 0.0)))
    ce_gap = abs(float(results[0].get("score", 0.0)) - float(results[1].get("score", 0.0)))
    if faiss_gap < FAISS_GAP or ce_gap < CE_GAP:
        clear_count = 2

best = results[:clear_count]
rest = results[clear_count:]
all_scores = [confidence_score(r) for r in results]

def render_bar(score, width=10):
    filled = max(0, min(width, int(round(score * width))))
    return ("█" * filled) + ("░" * (width - filled))

name_w = 22
bar_w = 10
top_border = "  ┌─ Best matches ──────────────────────────────────────────────┐"
bottom_border = "  └─────────────────────────────────────────────────────────────┘"
print(top_border)
for idx, row in enumerate(best, 1):
    name = str(row.get("name", "Unknown"))[:name_w].ljust(name_w)
    score = all_scores[idx - 1]
    bar = render_bar(score, width=bar_w)
    print(f"  │  {idx:<2} {name} {bar}   {score:0.3f}            │")
print(bottom_border)

if rest:
    print("")
    print("  Also retrieved (lower confidence)")
    for offset, row in enumerate(rest, clear_count + 1):
        name = str(row.get("name", "Unknown"))[:name_w].ljust(name_w)
        score = all_scores[offset - 1]
        bar = render_bar(score, width=bar_w)
        print(f"     {offset:<2} {name} {bar}   {score:0.4f}")
PY

echo ""
echo "  Results -> $OUTPUT_PATH"

if [[ "$VERBOSE" == "1" ]]; then
  echo ""
  echo "[verbose] Step timings"
  echo "[1/3] Building retriever container image   (${BUILD_MS}ms)"
  echo "[2/3] Ensuring FAISS index exists          (${INDEX_MS}ms)"
  echo "[3/3] Running retrieval and reranking      (${QUERY_MS}ms)"
  echo "Total elapsed: ${TOTAL_MS}ms"
  python3 - "$OUTPUT_PATH" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(0)

payload = json.loads(path.read_text(encoding="utf-8"))
results = payload.get("results", [])
if not results:
    raise SystemExit(0)

def fmt(values):
    return "  ".join(f"{v:>7.4f}" for v in values)

ce_scores = [float(r.get("score", 0.0)) for r in results]
faiss_scores = [float(r.get("retrieval_score", 0.0)) for r in results]
print("")
print(f"  CE scores:  {fmt(ce_scores)}")
print(f"  FAISS:      {fmt(faiss_scores)}")
PY
  echo ""
  echo "[verbose] Retriever command output"
  cat "$QUERY_LOG"
fi



  # configure_acceleration() for macOS:                                            
  # - GPU_FLAGS=(--device /dev/dri) — forwards the virtio-gpu DRM nodes from the libkrun VM into the 
  # container. Without this, Mesa has no hardware device and falls back to llvmpipe (CPU renderer).  
  # - DEVICE_ARGS=(--device auto) — clears the --device cpu --cpu-only that was being passed to      
  # retriever.py, which was overriding Vulkan and forcing CPU execution.                             
                                                                                                   
  # CONTAINERS_MACHINE_PROVIDER export:
  # - Automatically sets CONTAINERS_MACHINE_PROVIDER=libkrun for all podman commands in the script   
  # when on macOS, so podman targets the correct libkrun machine instead of silently using applehv.  
  # Respects an explicit override if already set in the environment. 
