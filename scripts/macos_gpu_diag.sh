#!/usr/bin/env bash
# macOS GPU diagnostics and native Metal inference test
# Purpose: Validate GPU/Metal availability without relying on Podman machine startup
# Usage: ./scripts/macos_gpu_diag.sh [path-to-model.gguf]

set -euo pipefail

echo "=== macOS GPU Diagnostics ==="
echo

# Check Metal support
echo "[1] Checking Metal support..."
if system_profiler SPDisplaysDataType | grep -q "Chipset Model: Apple"; then
  echo "✓ Apple Silicon detected"
else
  echo "⚠ Unable to confirm Apple Silicon"
fi

# Check Vulkan/MoltenVK
echo
echo "[2] Checking Vulkan (MoltenVK) support..."
if command -v vulkaninfo &>/dev/null; then
  echo "✓ vulkaninfo found"
  vulkaninfo --summary 2>/dev/null | head -n 10 || echo "  (vulkaninfo output unavailable)"
else
  echo "⚠ vulkaninfo not found (install via: brew install vulkan-tools)"
fi

# Check /dev/dri on host (for reference; only available inside Podman machine)
echo
echo "[3] Checking GPU device nodes..."
if [[ -e /dev/dri ]]; then
  echo "✓ /dev/dri exists (host level)"
  ls -la /dev/dri/
else
  echo "⚠ /dev/dri not present at host level (expected; only available inside Podman machine)"
fi

# Check for Metal GPU frameworks
echo
echo "[4] Checking Metal GPU frameworks..."
if [[ -d /System/Library/Frameworks/Metal.framework ]]; then
  echo "✓ Metal.framework found"
else
  echo "⚠ Metal.framework not found"
fi

# Try importing llama-cpp-python with Metal support
echo
echo "[5] Testing llama-cpp-python with Metal..."
python3 <<'EOF'
try:
    from llama_cpp import Llama
    print("✓ llama-cpp-python imported successfully")
    print(f"  GPU layer offload available: check source for n_gpu_layers support")
except ImportError as e:
    print(f"⚠ llama-cpp-python not installed or import failed: {e}")
    print("  Install with: pip install llama-cpp-python")
except Exception as e:
    print(f"⚠ Unexpected error: {e}")
EOF

# If model provided, attempt native Metal inference (outside container)
MODEL_PATH="${1:-}"
if [[ -n "$MODEL_PATH" && -f "$MODEL_PATH" ]]; then
  echo
  echo "[6] Testing native Metal inference with provided model..."
  python3 <<EOFPY
import time
try:
    from llama_cpp import Llama
    model = Llama(
        model_path="$MODEL_PATH",
        n_gpu_layers=99,  # Offload all layers to Metal GPU
        verbose=False
    )
    print("✓ Model loaded with GPU offload")
    
    # Quick test generation
    start = time.time()
    result = model(
        "What is 2+2?",
        max_tokens=10,
        echo=False
    )
    elapsed = time.time() - start
    print(f"✓ Native Metal inference completed in {elapsed:.2f}s")
    print(f"  Output: {result['choices'][0]['text'].strip()}")
except Exception as e:
    print(f"✗ Metal inference failed: {e}")
    print("  Try with n_gpu_layers=0 (CPU fallback):")
    try:
        from llama_cpp import Llama
        model = Llama(
            model_path="$MODEL_PATH",
            n_gpu_layers=0,  # CPU fallback
            verbose=False
        )
        print("✓ CPU fallback successful")
    except Exception as e2:
        print(f"✗ CPU fallback also failed: {e2}")
EOFPY
elif [[ -n "$MODEL_PATH" ]]; then
  echo
  echo "✗ Model file not found: $MODEL_PATH"
else
  echo
  echo "[6] Skipping native Metal inference test (no model provided)"
  echo "  Usage: $0 /path/to/model.gguf"
fi

echo
echo "=== End of Diagnostics ==="
