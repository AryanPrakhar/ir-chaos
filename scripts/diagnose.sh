#!/usr/bin/env bash
set -euo pipefail

# Diagnostic script for cross-platform podman + GPU setup
# Run this to check your system before running the retrieval pipeline

set +e  # Don't exit on errors—we want to report all findings

CHECKMARK="✓"
CROSS="✗"
QUESTION="?"

# Color output
info() { echo "[${CHECKMARK}] $@"; }
warn() { echo "[${QUESTION}] $@"; }
error() { echo "[${CROSS}] $@"; }
header() { echo ""; echo "=== $@ ==="; echo ""; }

header "Krkn Retrieval Pipeline Diagnostics"

# ──────────────────────────────────────────────────────────────────
# 1. OS Detection
# ──────────────────────────────────────────────────────────────────

header "1. Platform Detection"

HOST_OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"

echo "OS: $HOST_OS"
echo "Architecture: $ARCH"

if [[ "$HOST_OS" == "linux" ]]; then
  info "Running on Linux"
  if [[ -f /etc/os-release ]]; then
    . /etc/os-release
    echo "  Distribution: ${ID:-unknown} ${VERSION_ID:-unknown}"
  fi
elif [[ "$HOST_OS" == "darwin" ]]; then
  info "Running on macOS"
  echo "  Version: $(sw_vers -productVersion)"
else
  error "Unsupported OS: $HOST_OS"
  exit 1
fi

# ──────────────────────────────────────────────────────────────────
# 2. Container Engine
# ──────────────────────────────────────────────────────────────────

header "2. Container Engine"

if command -v podman >/dev/null 2>&1; then
  PODMAN_VERSION=$(podman --version)
  info "podman found: $PODMAN_VERSION"
else
  error "podman not found. Install with: brew install podman (macOS) or sudo apt-get install podman (Linux)"
fi

if command -v docker >/dev/null 2>&1; then
  DOCKER_VERSION=$(docker --version)
  warn "docker found: $DOCKER_VERSION (using podman preferred)"
fi

# ──────────────────────────────────────────────────────────────────
# 3. Podman Machine (macOS only)
# ──────────────────────────────────────────────────────────────────

header "3. Podman Machine Setup"

if [[ "$HOST_OS" == "darwin" ]]; then
  if command -v podman >/dev/null 2>&1; then
    MACHINES=$(podman machine list --format "{{.Name}}" 2>/dev/null || echo "")
    if [[ -z "$MACHINES" ]]; then
      warn "No podman machines found. Run the pipeline to initialize one."
    else
      echo "Machines:"
      podman machine list 2>/dev/null || true
      
      # Check provider
      MACHINE=$(echo "$MACHINES" | head -n1 | tr -d '*')
      PROVIDER=$(podman machine inspect "$MACHINE" 2>/dev/null | grep -i "provider\|type" || echo "unknown")
      if echo "$PROVIDER" | grep -qi libkrun; then
        info "Machine using libkrun (good for Vulkan GPU)"
      elif echo "$PROVIDER" | grep -qi applehv; then
        warn "Machine using applehv (no GPU support, only CPU)"
      else
        warn "Machine provider: $PROVIDER"
      fi
    fi
  fi
else
  info "Podman machine not needed on Linux (native runtime)"
fi

# ──────────────────────────────────────────────────────────────────
# 4. GPU Detection
# ──────────────────────────────────────────────────────────────────

header "4. GPU & Acceleration"

if [[ "$HOST_OS" == "linux" ]]; then
  # Check NVIDIA
  if command -v nvidia-smi >/dev/null 2>&1; then
    info "NVIDIA GPU detected"
    nvidia-smi --query-gpu=name,driver_version,compute_cap --format=csv,noheader 2>/dev/null || true
    
    # Check nvidia-container-toolkit
    if command -v nvidia-container-runtime >/dev/null 2>&1; then
      info "nvidia-container-runtime installed"
    else
      error "nvidia-container-runtime not installed (required for podman GPU passthrough)"
      echo "  Install: https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html"
    fi
  else
    warn "No NVIDIA GPU detected"
  fi

  # Check AMD ROCm
  if [[ -e /dev/kfd ]]; then
    info "AMD GPU detected (/dev/kfd present)"
    if [[ -e /dev/dri ]]; then
      info "DRI devices present (iGPU/dGPU)"
    fi
  else
    warn "No AMD GPU detected"
  fi

  # Check Intel iGPU
  if [[ -e /dev/dri/renderD128 ]] || [[ -e /dev/dri/card0 ]]; then
    info "Intel iGPU/Arc detected (/dev/dri present)"
  else
    warn "No Intel GPU detected"
  fi

elif [[ "$HOST_OS" == "darwin" ]]; then
  # macOS: Report available Metal GPU
  METAL_DEVICES=$(system_profiler SPDisplaysDataType 2>/dev/null | grep "Chipset Model" || echo "unknown")
  echo "Metal GPU: $METAL_DEVICES"
  info "Vulkan via libkrun will handle GPU (no additional setup needed)"
fi

# ──────────────────────────────────────────────────────────────────
# 5. Python & Dependencies
# ──────────────────────────────────────────────────────────────────

header "5. Python Environment"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_VERSION=$(python3 --version)
  info "Python: $PYTHON_VERSION"
else
  error "Python3 not found"
fi

# Check key packages
for pkg in json pickle faiss numpy torch sentence_transformers; do
  if python3 -c "import $pkg" 2>/dev/null; then
    info "Python package: $pkg"
  else
    warn "Missing Python package: $pkg (will be installed in container)"
  fi
done

# ──────────────────────────────────────────────────────────────────
# 6. Directory Structure
# ──────────────────────────────────────────────────────────────────

header "6. Project Structure"

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd 2>/dev/null || echo ".")"

for dir in "krkn-retriever" "docs" "scripts" "shared" ".cache"; do
  if [[ -d "$ROOT_DIR/$dir" ]]; then
    info "Found: $ROOT_DIR/$dir"
  else
    warn "Missing: $ROOT_DIR/$dir"
  fi
done

# Check for index
INDEX_FILE="$ROOT_DIR/krkn-retriever/faiss-index/krkn-scenarios.index"
META_FILE="$ROOT_DIR/krkn-retriever/faiss-index/krkn-scenarios.meta"

if [[ -f "$INDEX_FILE" ]] && [[ -f "$META_FILE" ]]; then
  info "FAISS index found (will skip rebuilding)"
else
  warn "FAISS index not found (will be built on first run)"
fi

# ──────────────────────────────────────────────────────────────────
# 7. Network / Internet
# ──────────────────────────────────────────────────────────────────

header "7. Network Connectivity"

# Test DNS
if ping -c 1 8.8.8.8 >/dev/null 2>&1 || ping -c 1 huggingface.co >/dev/null 2>&1; then
  info "Internet connectivity OK"
else
  warn "Network connectivity limited (may affect model downloads)"
fi

# Test HuggingFace access
if curl -s --head https://huggingface.co >/dev/null 2>&1; then
  info "HuggingFace.co reachable (for model downloads)"
else
  warn "HuggingFace.co unreachable (will fail when downloading models)"
fi

# ──────────────────────────────────────────────────────────────────
# 8. Container Runtime Test
# ──────────────────────────────────────────────────────────────────

header "8. Container Runtime Test"

if command -v podman >/dev/null 2>&1; then
  echo "Testing podman runtime..."
  
  if podman run --rm alpine echo "hello" >/dev/null 2>&1; then
    info "Basic podman run works"
  else
    error "podman run failed (fix podman installation)"
  fi
  
  # Test GPU passthrough
  if [[ "$HOST_OS" == "linux" ]]; then
    if command -v nvidia-smi >/dev/null 2>&1; then
      echo "Testing NVIDIA GPU passthrough..."
      if podman run --rm --device nvidia.com/gpu=all alpine nvidia-smi >/dev/null 2>&1; then
        info "NVIDIA GPU passthrough works"
      else
        error "NVIDIA GPU passthrough failed"
        echo "  Ensure nvidia-container-toolkit is installed and configured"
      fi
    fi
  fi
fi

# ──────────────────────────────────────────────────────────────────
# 9. Summary & Next Steps
# ──────────────────────────────────────────────────────────────────

header "9. Next Steps"

SCRIPT="./scripts/pipeline_retrieve_only.sh"
if [[ -f "$SCRIPT" ]]; then
  info "Pipeline script found at $SCRIPT"
  echo ""
  echo "To run a query:"
  echo "  $SCRIPT \"your query here\""
  echo ""
  echo "With verbose output:"
  echo "  $SCRIPT \"your query here\" 10 5 --verbose"
else
  warn "Pipeline script not found at $SCRIPT"
  echo "  Copy the fixed pipeline_retrieve_only.sh to ./scripts/"
fi

if [[ "$HOST_OS" == "darwin" ]]; then
  if ! podman machine list >/dev/null 2>&1; then
    echo ""
    echo "First time on macOS? The script will initialize podman machine."
    echo "This takes 1-2 minutes on first run."
  fi
fi

echo ""
echo "For detailed logs, add --verbose:"
echo "  $SCRIPT \"your query\" 10 5 --verbose"
echo ""

header "Diagnostics Complete"
echo "If you see errors above, check the setup guide:"
echo "  ./CROSS_PLATFORM_SETUP.md"