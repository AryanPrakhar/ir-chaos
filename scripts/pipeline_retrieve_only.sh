#!/usr/bin/env bash
set -euo pipefail

# Retrieval-only pipeline: retrieves and reranks results without inference
# CROSS-PLATFORM: Linux (native podman) + macOS (podman machine + libkrun)
#
# Usage:
#   ./scripts/pipeline_retrieve_only.sh [query] [retrieve-k] [rerank-k] [--verbose] [--cpu|--vulkan]
#   (No query starts interactive mode)
#
# Optional environment variables:
#   CONTAINER_ENGINE=podman|docker
#   RETRIEVER_IMAGE=krkn-retriever:fastapi
#   RETRIEVER_DOCKERFILE=/path/to/Dockerfile
#   RETRIEVER_BACKEND=auto|torch|vulkan
#   RETRIEVER_ACCELERATION=auto|gpu|cpu
#   LLAMA_EMBED_MODEL=/abs/path/to/model.gguf
#   LLAMA_RERANKER_MODEL=/abs/path/to/reranker.gguf
#   LLAMA_GPU_LAYERS=-1
#   RETRIEVER_GGUF_REPO=Qwen/Qwen3-Embedding-0.6B-GGUF
#   RETRIEVER_GGUF_FILE=Qwen3-Embedding-0.6B-f16.gguf
#   RETRIEVER_RERANKER_GGUF_REPO=gpustack/bge-reranker-v2-m3-GGUF
#   RETRIEVER_RERANKER_GGUF_FILE=bge-reranker-v2-m3-Q2_K.gguf
#   RETRIEVER_AUTO_DOWNLOAD_MODEL=1
#   RETRIEVER_FORCE_BUILD=1
#   HF_TOKEN / HUGGING_FACE_HUB_TOKEN (optional, for gated HF downloads)
#   HF_CACHE_DIR, TORCH_CACHE_DIR
#
# Output:
#   retrieval container writes ./shared/retrieval_output.json

VERBOSE=0
INTERACTIVE=0
CLI_BACKEND=""
CLI_ACCELERATION=""
POSITIONAL_ARGS=()
for arg in "$@"; do
  case "$arg" in
    --verbose) VERBOSE=1 ;;
    --cpu)
      CLI_BACKEND="torch"
      CLI_ACCELERATION="cpu"
      ;;
    --vulkan)
      CLI_BACKEND="vulkan"
      CLI_ACCELERATION="gpu"
      ;;
    *) POSITIONAL_ARGS+=("$arg") ;;
  esac
done
set -- "${POSITIONAL_ARGS[@]+"${POSITIONAL_ARGS[@]}"}"

QUERY="${1:-}"
RETRIEVE_K="${2:-10}"
RERANK_K="${3:-5}"

if [[ -z "$QUERY" ]]; then
  INTERACTIVE=1
fi

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SHARED_DIR="$ROOT_DIR/shared"
INDEX_FILE="$ROOT_DIR/krkn-retriever/faiss-index/krkn-scenarios.index"
META_FILE="$ROOT_DIR/krkn-retriever/faiss-index/krkn-scenarios.meta"
HF_CACHE_DIR="${HF_CACHE_DIR:-$ROOT_DIR/.cache/huggingface}"
TORCH_CACHE_DIR="${TORCH_CACHE_DIR:-$ROOT_DIR/.cache/torch}"
ENGINE="${CONTAINER_ENGINE:-podman}"
IMAGE="${RETRIEVER_IMAGE:-krkn-retriever:fastapi}"
DOCKERFILE="${RETRIEVER_DOCKERFILE:-$ROOT_DIR/krkn-retriever/Dockerfile}"
FORCE_BUILD="${RETRIEVER_FORCE_BUILD:-0}"
BACKEND="${RETRIEVER_BACKEND:-auto}"
LLAMA_EMBED_MODEL_PATH="${LLAMA_EMBED_MODEL:-}"
LLAMA_RERANKER_MODEL_PATH="${LLAMA_RERANKER_MODEL:-}"
LLAMA_GPU_LAYERS="${LLAMA_GPU_LAYERS:--1}"
GGUF_REPO="${RETRIEVER_GGUF_REPO:-Qwen/Qwen3-Embedding-0.6B-GGUF}"
GGUF_FILE="${RETRIEVER_GGUF_FILE:-Qwen3-Embedding-0.6B-f16.gguf}"
RERANKER_GGUF_REPO="${RETRIEVER_RERANKER_GGUF_REPO:-gpustack/bge-reranker-v2-m3-GGUF}"
RERANKER_GGUF_FILE="${RETRIEVER_RERANKER_GGUF_FILE:-bge-reranker-v2-m3-Q2_K.gguf}"
AUTO_DOWNLOAD_MODEL="${RETRIEVER_AUTO_DOWNLOAD_MODEL:-1}"
ACCELERATION_MODE="${RETRIEVER_ACCELERATION:-auto}"
HF_TOKEN="${HF_TOKEN:-${HUGGING_FACE_HUB_TOKEN:-${HUGGINGFACE_TOKEN:-}}}"

if [[ -n "$CLI_BACKEND" ]]; then
  BACKEND="$CLI_BACKEND"
fi
if [[ -n "$CLI_ACCELERATION" ]]; then
  ACCELERATION_MODE="$CLI_ACCELERATION"
fi

# Support llama.cpp shorthand "repo:QUANT" (e.g. gpustack/bge-reranker-v2-m3-GGUF:Q2_K)
if [[ "$RERANKER_GGUF_REPO" == *:* ]]; then
  RERANKER_QUANT="${RERANKER_GGUF_REPO#*:}"
  RERANKER_GGUF_REPO="${RERANKER_GGUF_REPO%%:*}"
  if [[ -z "${RETRIEVER_RERANKER_GGUF_FILE:-}" ]]; then
    RERANKER_GGUF_FILE="$RERANKER_QUANT"
  fi
fi

# Allow passing just quant name for the gpustack v2-m3 repo.
if [[ "$RERANKER_GGUF_REPO" == "gpustack/bge-reranker-v2-m3-GGUF" && "$RERANKER_GGUF_FILE" != *.gguf ]]; then
  RERANKER_GGUF_FILE="bge-reranker-v2-m3-${RERANKER_GGUF_FILE}.gguf"
fi

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
  # Linux podman is native: no podman machine management needed.
  [[ "$ENGINE" == "podman" ]] || return 0
  [[ "$HOST_OS" == "darwin" ]] || return 0

  # macOS only: ensure provider for Vulkan path.
  export CONTAINERS_MACHINE_PROVIDER="${CONTAINERS_MACHINE_PROVIDER:-libkrun}"

  # Create machine if missing.
  if ! "$ENGINE" machine list --format "{{.Name}}" 2>/dev/null | grep -q .; then
    echo "No podman machine found. Initializing with libkrun provider..."
    "$ENGINE" machine init --cpus 4 --memory 8192 --disk-size 100
  fi

  local machine
  machine=$("$ENGINE" machine list --format "{{.Name}}" 2>/dev/null | head -n1 | tr -d '*') || true
  if [[ -z "$machine" ]]; then
    echo "Error: could not determine podman machine name"
    return 1
  fi

  # Recreate applehv machine so Vulkan can use libkrun path.
  if "$ENGINE" machine inspect "$machine" 2>/dev/null | grep -qi "applehv"; then
    echo "Recreating podman machine with libkrun (required for Vulkan on macOS): $machine"
    "$ENGINE" machine rm -f "$machine"
    "$ENGINE" machine init --cpus 4 --memory 8192 --disk-size 100
    machine=$("$ENGINE" machine list --format "{{.Name}}" 2>/dev/null | head -n1 | tr -d '*') || true
  fi

  # Attempt to start machine; ignore "already running" errors.
  if ! "$ENGINE" machine start "$machine" 2>&1 | grep -qi "already running\|started"; then
    # Attempt failed and didn't say "already running"; may have started anyway, try a final check.
    sleep 1
    if ! "$ENGINE" machine list --format "{{.Name}}" 2>/dev/null | grep -q "$(echo "$machine" | sed 's/\*//')"; then
      echo "Error: podman machine $machine failed to start"
      return 1
    fi
  fi
  
  return 0
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
API_CONTAINER_ID=""
API_PORT="${RETRIEVER_API_PORT:-18080}"
API_BASE_URL="http://127.0.0.1:${API_PORT}"
cleanup_logs() {
  rm -f "$PIPELINE_LOG"
  if [[ -n "$QUERY_LOG" ]]; then
    rm -f "$QUERY_LOG"
  fi
  if [[ -n "$API_CONTAINER_ID" ]]; then
    "$ENGINE" rm -f "$API_CONTAINER_ID" >/dev/null 2>&1 || true
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
    # A Vulkan-built image can still run in CPU-only mode.
    if [[ "$GGML_BACKEND_DESIRED" == "cpu" && "$image_backend" == "vulkan" ]]; then
      return 0
    fi

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
  local curl_args=(-L --fail --retry 3 --continue-at - -o "$out_path")
  if [[ -n "$HF_TOKEN" ]]; then
    curl_args+=(-H "Authorization: Bearer $HF_TOKEN")
  fi
  curl "${curl_args[@]}" "$url"
}

download_reranker_gguf_model() {
  local out_path="$1"
  local url="https://huggingface.co/${RERANKER_GGUF_REPO}/resolve/main/${RERANKER_GGUF_FILE}"
  vlog "      Downloading GGUF reranker: ${RERANKER_GGUF_REPO}/${RERANKER_GGUF_FILE}"
  mkdir -p "$(dirname "$out_path")"
  local curl_args=(-L --fail --retry 3 --continue-at - -o "$out_path")
  if [[ -n "$HF_TOKEN" ]]; then
    curl_args+=(-H "Authorization: Bearer $HF_TOKEN")
  fi
  curl "${curl_args[@]}" "$url"
}

configure_acceleration() {
  GPU_FLAGS=()
  DEVICE_ARGS=(--device cpu --cpu-only)
  GPU_RUNTIME_KIND="none"

  if [[ "$ACCELERATION_MODE" == "cpu" ]]; then
    GGML_BACKEND_DESIRED="cpu"
    BUILD_ARGS+=(--build-arg GGML_BACKEND=cpu)
    return
  fi

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

  if [[ "$HOST_OS" == "linux" ]]; then
    # Try NVIDIA runtime
    if nvidia_runtime_available 2>/dev/null; then
      if gpu_runtime_supported 2>/dev/null; then
        GGML_BACKEND_DESIRED="cuda"
        BUILD_ARGS+=(--build-arg GGML_BACKEND=cuda)
        GPU_RUNTIME_KIND="nvidia-cuda"
        GPU_FLAGS=(--device nvidia.com/gpu=all --security-opt=label=disable)
        DEVICE_ARGS=(--device cuda)
        return
      fi
    fi

    # Try AMD ROCm
    if [[ -e /dev/kfd ]]; then
      GGML_BACKEND_DESIRED="rocm"
      BUILD_ARGS+=(--build-arg GGML_BACKEND=rocm)
      GPU_RUNTIME_KIND="amd-rocm"
      GPU_FLAGS=(--device /dev/kfd --device /dev/dri --group-add keep-groups)
      DEVICE_ARGS=(--device auto)
      return
    fi

    # Try Intel/DRI Vulkan path
    if [[ -e /dev/dri/renderD128 || -e /dev/dri/card0 ]]; then
      if podman_dri_runtime_supported 2>/dev/null; then
        GGML_BACKEND_DESIRED="vulkan"
        BUILD_ARGS+=(--build-arg GGML_BACKEND=vulkan)
        GPU_RUNTIME_KIND="intel-vulkan"
        GPU_FLAGS=(--device /dev/dri)
        DEVICE_ARGS=(--device auto)
        return
      fi
    fi
  fi

  # Fallback: CPU only
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

run_engine_with_stdin() {
  if [[ -n "${GPU_FLAGS+x}" ]] && [[ ${#GPU_FLAGS[@]} -gt 0 ]]; then
    "$ENGINE" run --rm -i "${GPU_FLAGS[@]}" "$@"
  else
    "$ENGINE" run --rm -i "$@"
  fi
}

run_retriever_python() {
  local run_args=(--entrypoint python3)
  if [[ -n "${LLAMA_MOUNT_ARGS+x}" ]] && [[ ${#LLAMA_MOUNT_ARGS[@]} -gt 0 ]]; then
    run_args+=("${LLAMA_MOUNT_ARGS[@]}")
  fi
  run_engine "${run_args[@]}" "$@"
}

start_api_standby() {
  local run_args=()
  if [[ -n "${LLAMA_MOUNT_ARGS+x}" ]] && [[ ${#LLAMA_MOUNT_ARGS[@]} -gt 0 ]]; then
    run_args+=("${LLAMA_MOUNT_ARGS[@]}")
  fi

  local container_id
  if [[ -n "${GPU_FLAGS+x}" ]] && [[ ${#GPU_FLAGS[@]} -gt 0 ]]; then
    container_id=$(
      "$ENGINE" run -d --rm \
        "${GPU_FLAGS[@]}" \
        "${run_args[@]}" \
        -p "127.0.0.1:${API_PORT}:8080" \
        -v "$ROOT_DIR/krkn-retriever:/app$MOUNT_LABEL_SUFFIX" \
        -v "$ROOT_DIR/docs:/app/docs$MOUNT_LABEL_SUFFIX" \
        -v "$HF_CACHE_DIR:/root/.cache/huggingface$MOUNT_LABEL_SUFFIX" \
        -v "$TORCH_CACHE_DIR:/root/.cache/torch$MOUNT_LABEL_SUFFIX" \
        -e DOCS_DIR=/app/docs \
        -e RETRIEVER_BACKEND="$BACKEND" \
        -e LLAMA_EMBED_MODEL="$LLAMA_EMBED_MODEL_PATH" \
        -e LLAMA_RERANKER_MODEL="$LLAMA_RERANKER_MODEL_PATH" \
        -e LLAMA_GPU_LAYERS="$LLAMA_GPU_LAYERS" \
        -e HF_HOME=/root/.cache/huggingface \
        -e SENTENCE_TRANSFORMERS_HOME=/root/.cache/huggingface \
        -e TORCH_HOME=/root/.cache/torch \
        -e RETRIEVE_K="$RETRIEVE_K" \
        -e RERANK_K="$RERANK_K" \
        -w /app \
        "$IMAGE"
    )
  else
    container_id=$(
      "$ENGINE" run -d --rm \
        "${run_args[@]}" \
        -p "127.0.0.1:${API_PORT}:8080" \
        -v "$ROOT_DIR/krkn-retriever:/app$MOUNT_LABEL_SUFFIX" \
        -v "$ROOT_DIR/docs:/app/docs$MOUNT_LABEL_SUFFIX" \
        -v "$HF_CACHE_DIR:/root/.cache/huggingface$MOUNT_LABEL_SUFFIX" \
        -v "$TORCH_CACHE_DIR:/root/.cache/torch$MOUNT_LABEL_SUFFIX" \
        -e DOCS_DIR=/app/docs \
        -e RETRIEVER_BACKEND="$BACKEND" \
        -e LLAMA_EMBED_MODEL="$LLAMA_EMBED_MODEL_PATH" \
        -e LLAMA_RERANKER_MODEL="$LLAMA_RERANKER_MODEL_PATH" \
        -e LLAMA_GPU_LAYERS="$LLAMA_GPU_LAYERS" \
        -e HF_HOME=/root/.cache/huggingface \
        -e SENTENCE_TRANSFORMERS_HOME=/root/.cache/huggingface \
        -e TORCH_HOME=/root/.cache/torch \
        -e RETRIEVE_K="$RETRIEVE_K" \
        -e RERANK_K="$RERANK_K" \
        -w /app \
        "$IMAGE"
    )
  fi

  API_CONTAINER_ID="${container_id//$'\n'/}"
}

wait_for_api_ready() {
  local attempts=120
  local i
  for ((i=1; i<=attempts; i++)); do
    if curl -fsS "$API_BASE_URL/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 1
  done
  return 1
}

run_query_via_api() {
  local query="$1"
  local request_json
  request_json="$(python3 - "$query" "$RETRIEVE_K" "$RERANK_K" <<'PY'
import json
import sys

payload = {
    "query": sys.argv[1],
    "k": int(sys.argv[2]),
    "rerank_k": int(sys.argv[3]),
}
print(json.dumps(payload))
PY
)"

  if ! curl -fsS \
    -X POST "$API_BASE_URL/retrieve" \
    -H "Content-Type: application/json" \
    -d "$request_json" \
    >"$SHARED_DIR/retrieval_output.json" 2>>"$QUERY_LOG"; then
    return 1
  fi
}

run_query_once() {
  if ! run_query_via_api "$QUERY"; then
    echo "Error: retrieval query failed."
    if [[ "$VERBOSE" == "1" ]]; then
      cat "$QUERY_LOG"
    else
      tail -n 40 "$QUERY_LOG"
    fi
    exit 1
  fi
}

render_query_output() {
  local query_ms="$1"
  local doc_count output_path seconds_display
  doc_count="$(index_doc_count)"
  output_path="$SHARED_DIR/retrieval_output.json"
  seconds_display="$(python3 - "$query_ms" <<'PY'
import sys
ms = int(sys.argv[1])
print(f"{ms/1000.0:.1f}")
PY
)"

  echo ""
  echo "  Searching ${doc_count} scenarios...  done in ${seconds_display}s"
  echo ""

  python3 - "$output_path" <<'PY'
import json, math, sys
from pathlib import Path

FAISS_GAP = 0.07
CE_GAP = 1.0

path = Path(sys.argv[1])
if not path.exists():
    print("  No matching scenario")
    raise SystemExit(0)

payload = json.loads(path.read_text(encoding="utf-8"))
results = payload.get("results", [])

if not results:
    print("  No matching scenario")
    raise SystemExit(0)

def final_score(row):
    if "final_score" in row:
        return max(0.0, min(1.0, float(row.get("final_score", 0.0))))
    # Back-compat with older payloads
    ce = float(row.get("score", 0.0))
    faiss = float(row.get("retrieval_score", 0.0))
    ce_sigmoid = 1.0 / (1.0 + math.exp(-ce))
    return max(0.0, min(1.0, (0.8 * ce_sigmoid) + (0.2 * max(0.0, min(1.0, faiss)))))

def ce_score(row):
    return float(row.get("rerank_score", row.get("score", 0.0)))

clear_count = 1
if len(results) >= 2:
    faiss_gap = abs(float(results[0].get("retrieval_score", 0.0)) - float(results[1].get("retrieval_score", 0.0)))
    ce_gap = abs(ce_score(results[0]) - ce_score(results[1]))
    if faiss_gap < FAISS_GAP or ce_gap < CE_GAP:
        clear_count = 2

best = results[:clear_count]
all_scores = [final_score(r) for r in results]

def render_bar(score, width=10):
    filled = max(0, min(width, int(round(score * width))))
    return ("█" * filled) + ("░" * (width - filled))

use_color = sys.stdout.isatty()
RESET = "\033[0m" if use_color else ""
CYAN  = "\033[36m" if use_color else ""
GREEN = "\033[32m" if use_color else ""
YELLOW= "\033[33m" if use_color else ""
BOLD  = "\033[1m"  if use_color else ""

# STRICT COLUMN WIDTHS
COL_OPT = 6
COL_ACT = 32
COL_FIT = 14
COL_MAT = 8
INNER_WIDTH = COL_OPT + COL_ACT + COL_FIT + COL_MAT

top_border = f"  {CYAN}┌─ Suggested Chaos Experiments {'─' * (INNER_WIDTH - 28)}┐{RESET}"
bottom_border = f"  {CYAN}└{'─' * INNER_WIDTH}┘{RESET}"

print(top_border)

# Header
h_opt = f"{BOLD}{'OPT':<{COL_OPT}}{RESET}"
h_act = f"{BOLD}{'ACTION':<{COL_ACT}}{RESET}"
h_fit = f"{BOLD}{'FITMENT':<{COL_FIT}}{RESET}"
h_mat = f"{BOLD}{'MATCH':<{COL_MAT}}{RESET}"
print(f"  {CYAN}│{RESET}{h_opt}{h_act}{h_fit}{h_mat}{CYAN}│{RESET}")

# Rows
for idx, row in enumerate(best, 1):
    raw_name = str(row.get("id", "unknown"))[:COL_ACT-2]
    
    # 1. Pad raw text strings first
    c_opt = f"[{idx}]".ljust(COL_OPT)
    c_act = raw_name.ljust(COL_ACT)
    
    # 2. Build the bar and pad it explicitly
    score = all_scores[idx - 1]
    bar_str = render_bar(score, width=10)
    c_fit = f"{GREEN}{bar_str}{RESET}" + (" " * (COL_FIT - 10))
    
    # 3. Format the score, pad it, then wrap in color
    c_mat_plain = f"{score:0.3f}".ljust(COL_MAT)
    c_mat = f"{YELLOW}{c_mat_plain}{RESET}"
    
    # 4. Print the line
    print(f"  {CYAN}│{RESET}{c_opt}{c_act}{c_fit}{c_mat}{CYAN}│{RESET}")

print(bottom_border)
PY

}

# ── Setup ──

mkdir -p "$SHARED_DIR" "$HF_CACHE_DIR" "$TORCH_CACHE_DIR"

# Platform-specific backend defaults
if [[ "$BACKEND" == "auto" ]]; then
  if [[ "$HOST_OS" == "darwin" || "$HOST_OS" == "macos" ]]; then
    BACKEND="vulkan"
    vlog "macOS detected; using llama.cpp backend for Vulkan acceleration"
  else
    BACKEND="torch"
    vlog "$HOST_OS detected; using torch backend"
  fi
fi

# Resolve GGUF models for vulkan backend
if [[ "$BACKEND" == "vulkan" ]]; then
  if [[ -z "$LLAMA_EMBED_MODEL_PATH" ]]; then
    LLAMA_EMBED_MODEL_PATH="$ROOT_DIR/models/$GGUF_FILE"
  fi
  if [[ -z "$LLAMA_RERANKER_MODEL_PATH" ]]; then
    LLAMA_RERANKER_MODEL_PATH="$ROOT_DIR/models/$RERANKER_GGUF_FILE"
  fi

  if [[ (! -f "$LLAMA_EMBED_MODEL_PATH" || ! -f "$LLAMA_RERANKER_MODEL_PATH") && "$AUTO_DOWNLOAD_MODEL" == "1" ]]; then
    if ! command -v curl >/dev/null 2>&1; then
      echo "Error: curl is required to auto-download GGUF models"; exit 1
    fi
  fi

  if [[ ! -f "$LLAMA_EMBED_MODEL_PATH" && "$AUTO_DOWNLOAD_MODEL" == "1" ]]; then
    download_gguf_model "$LLAMA_EMBED_MODEL_PATH"
  fi
  if [[ ! -f "$LLAMA_RERANKER_MODEL_PATH" && "$AUTO_DOWNLOAD_MODEL" == "1" ]]; then
    if ! download_reranker_gguf_model "$LLAMA_RERANKER_MODEL_PATH"; then
      echo "Warning: failed to download GGUF reranker (${RERANKER_GGUF_REPO}/${RERANKER_GGUF_FILE})."
      echo "         Falling back to FlagReranker (CPU) unless LLAMA_RERANKER_MODEL is provided."
    fi
  fi

  if [[ ! -f "$LLAMA_EMBED_MODEL_PATH" ]]; then
    echo "Error: Vulkan backend needs a GGUF embedding model file"
    echo "       Expected: $LLAMA_EMBED_MODEL_PATH"
    echo "       Set LLAMA_EMBED_MODEL or keep RETRIEVER_AUTO_DOWNLOAD_MODEL=1"
    exit 1
  fi
  if [[ ! -f "$LLAMA_RERANKER_MODEL_PATH" ]]; then
    LLAMA_RERANKER_MODEL_PATH=""
  fi

  LLAMA_MODEL_ABS="$(cd "$(dirname "$LLAMA_EMBED_MODEL_PATH")" && pwd)/$(basename "$LLAMA_EMBED_MODEL_PATH")"
  LLAMA_MODEL_BASENAME="$(basename "$LLAMA_MODEL_ABS")"
  if [[ -n "$LLAMA_RERANKER_MODEL_PATH" ]]; then
    RERANKER_MODEL_ABS="$(cd "$(dirname "$LLAMA_RERANKER_MODEL_PATH")" && pwd)/$(basename "$LLAMA_RERANKER_MODEL_PATH")"
    RERANKER_MODEL_BASENAME="$(basename "$RERANKER_MODEL_ABS")"
    if [[ "$(dirname "$LLAMA_MODEL_ABS")" == "$(dirname "$RERANKER_MODEL_ABS")" ]]; then
      LLAMA_EMBED_MODEL_PATH="/models/$LLAMA_MODEL_BASENAME"
      LLAMA_RERANKER_MODEL_PATH="/models/$RERANKER_MODEL_BASENAME"
      LLAMA_MOUNT_ARGS=(-v "$(dirname "$LLAMA_MODEL_ABS"):/models$MOUNT_LABEL_SUFFIX")
    else
      LLAMA_EMBED_MODEL_PATH="/models-embed/$LLAMA_MODEL_BASENAME"
      LLAMA_RERANKER_MODEL_PATH="/models-reranker/$RERANKER_MODEL_BASENAME"
      LLAMA_MOUNT_ARGS=(
        -v "$(dirname "$LLAMA_MODEL_ABS"):/models-embed$MOUNT_LABEL_SUFFIX"
        -v "$(dirname "$RERANKER_MODEL_ABS"):/models-reranker$MOUNT_LABEL_SUFFIX"
      )
    fi
  else
    LLAMA_EMBED_MODEL_PATH="/models/$LLAMA_MODEL_BASENAME"
    LLAMA_MOUNT_ARGS=(-v "$(dirname "$LLAMA_MODEL_ABS"):/models$MOUNT_LABEL_SUFFIX")
  fi
fi

# ── Configure acceleration (sets BUILD_ARGS, GPU_FLAGS, DEVICE_ARGS) ──

configure_acceleration

if [[ "$VERBOSE" == "1" ]]; then
  echo "========================================"
  echo "Krkn Retrieval-Only Pipeline"
  echo "========================================"
  echo "Query: ${QUERY:-<interactive>}"
  echo "Retrieve-K: $RETRIEVE_K  |  Rerank-K: $RERANK_K"
  echo "Engine: $ENGINE  |  Image: $IMAGE"
  echo "Host OS: $HOST_OS  |  Backend: $BACKEND"
  echo "Acceleration: $ACCELERATION_MODE  |  GPU runtime: $GPU_RUNTIME_KIND"
  echo "LLAMA_EMBED_MODEL: ${LLAMA_EMBED_MODEL_PATH:-<not-set>}"
  echo "LLAMA_RERANKER_MODEL: ${LLAMA_RERANKER_MODEL_PATH:-<not-set>}"
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
    -e LLAMA_RERANKER_MODEL="$LLAMA_RERANKER_MODEL_PATH" \
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
vlog "      Starting warm API service on $API_BASE_URL"
if ! start_api_standby >>"$PIPELINE_LOG" 2>&1; then
  echo "Error: failed to start standby API container."
  tail -n 40 "$PIPELINE_LOG"
  exit 1
fi
if ! wait_for_api_ready; then
  echo "Error: standby API did not become ready."
  if [[ -n "$API_CONTAINER_ID" ]]; then
    "$ENGINE" logs "$API_CONTAINER_ID" | tail -n 60 || true
  fi
  exit 1
fi

if [[ "$BACKEND" == "vulkan" && "$ACCELERATION_MODE" != "cpu" ]]; then
  accel_check=""
  accel_resp="$(curl -sS -H "Accept: application/json" --max-time 3 -w "\n%{http_code}" "$API_BASE_URL/health/acceleration" 2>/dev/null || true)"
  accel_http="$(printf "%s" "$accel_resp" | tail -n 1)"
  accel_json="$(printf "%s" "$accel_resp" | sed '$d')"

  accel_trimmed="$(printf "%s" "$accel_json" | tr -d '\r' | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  if [[ -z "$accel_trimmed" || "$accel_http" != "200" ]]; then
    echo "Warning: acceleration health check failed (status=${accel_http:-none})."
    if [[ -n "$accel_trimmed" ]]; then
      echo "Response: $accel_trimmed"
    fi
    if [[ -n "$API_CONTAINER_ID" ]]; then
      "$ENGINE" logs "$API_CONTAINER_ID" | tail -n 80 || true
    fi
    accel_check="SKIP"
  fi

  if [[ "$accel_check" != "SKIP" ]]; then
    if [[ "$accel_trimmed" != "{"* && "$accel_trimmed" != "["* ]]; then
      echo "Warning: acceleration health check returned non-JSON (status=${accel_http:-none})."
      echo "Response (first 200 chars): ${accel_trimmed:0:200}"
      if [[ -n "$API_CONTAINER_ID" ]]; then
        "$ENGINE" logs "$API_CONTAINER_ID" | tail -n 80 || true
      fi
      accel_check="SKIP"
    fi
  fi

  if [[ "$accel_check" != "SKIP" ]]; then
    accel_check="$(python3 - <<'PY'
import json
import sys

raw = sys.stdin.read()
try:
    payload = json.loads(raw)
except Exception as exc:
    print(f"ERROR: invalid_json: {exc}")
    raise SystemExit(1)

errors = []
if payload.get("backend") != "vulkan":
    errors.append(f"backend={payload.get('backend')}")
if not payload.get("embedding_gpu"):
    errors.append("embedding_gpu=false")
if payload.get("reranker_type") != "llama_cpp":
    errors.append(f"reranker_type={payload.get('reranker_type')}")
if not payload.get("reranker_gpu"):
    errors.append("reranker_gpu=false")

if errors:
    print("ERROR: " + "; ".join(errors))
    raise SystemExit(1)

print("OK")
PY
<<<"$accel_trimmed" || true)"
  fi

  if [[ "$accel_check" != "OK" && "$accel_check" != "SKIP" ]]; then
    echo "Warning: Vulkan acceleration not active." 
    echo "Detail: ${accel_check}"
  fi

  if [[ "$accel_check" == "OK" ]]; then
    vlog "      Vulkan acceleration confirmed (embedding_gpu=true, reranker_type=llama_cpp, reranker_gpu=true)"
  fi
fi

if [[ "$INTERACTIVE" == "1" ]]; then
  echo ""
  printf '\033[36m[KRKN-AI]\033[0m Ready to profile your cluster. What should we test?\n'
  echo ""
  echo "(type 'exit' to quit)"
  while true; do
    printf ">> "
    if ! IFS= read -r QUERY; then
      echo ""
      break
    fi
    if [[ "$QUERY" == "exit" || "$QUERY" == "quit" ]]; then
      echo ""
      break
    fi
    if [[ -z "${QUERY// }" ]]; then
      echo "Empty query. Please try again."
      continue
    fi
    STEP_START_MS="$(now_ms)"
    if ! run_query_via_api "$QUERY"; then
      echo "Error: retrieval query failed."
      tail -n 40 "$QUERY_LOG"
      continue
    fi
    STEP_END_MS="$(now_ms)"
    QUERY_MS="$((STEP_END_MS - STEP_START_MS))"
    vlog "      Step time: ${QUERY_MS}ms"
    render_query_output "$QUERY_MS"
  done
else
  run_query_once
  STEP_END_MS="$(now_ms)"
  QUERY_MS="$((STEP_END_MS - STEP_START_MS))"
  vlog "      Step time: ${QUERY_MS}ms"
  render_query_output "$QUERY_MS"
fi

TOTAL_END_MS="$(now_ms)"
TOTAL_MS="$((TOTAL_END_MS - TOTAL_START_MS))"

if [[ "$VERBOSE" == "1" ]]; then
  echo ""
  echo "[verbose] Step timings"
  echo "[1/3] Building retriever container image   (${BUILD_MS}ms)"
  echo "[2/3] Ensuring FAISS index exists          (${INDEX_MS}ms)"
  echo "[3/3] Running retrieval and reranking      (${QUERY_MS}ms)"
  echo "Total elapsed: ${TOTAL_MS}ms"
  if [[ -f "$SHARED_DIR/retrieval_output.json" ]]; then
    python3 - "$SHARED_DIR/retrieval_output.json" <<'PY'
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

ce_scores = [float(r.get("rerank_score", r.get("score", 0.0))) for r in results]
faiss_scores = [float(r.get("retrieval_score", 0.0)) for r in results]
hybrid_scores = [float(r.get("final_score", 0.0)) for r in results]
print("")
print(f"  CE scores:  {fmt(ce_scores)}")
print(f"  FAISS:      {fmt(faiss_scores)}")
print(f"  Hybrid:     {fmt(hybrid_scores)}")
PY
  fi
  echo ""
  echo "[verbose] Retriever command output"
  cat "$QUERY_LOG"
  if [[ "$INTERACTIVE" == "1" ]]; then
    echo ""
    echo "[verbose] Interactive mode ran with pipeline scoring/UI per query."
  fi
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
