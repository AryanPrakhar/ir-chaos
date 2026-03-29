FROM registry.fedoraproject.org/fedora:40

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PATH=/opt/venv/bin:$PATH
ENV CMAKE_BUILD_PARALLEL_LEVEL=1
# ------------------------------------------------------------
# BASE DEPS — always installed regardless of hardware
# ------------------------------------------------------------
RUN dnf -y update && \
    dnf -y install \
      python3 \
      python3-pip \
      python3-devel \
      python3-virtualenv \
      git \
      cmake \
      ninja-build \
      gcc \
      gcc-c++ \
      make \
      pkgconf-pkg-config \
      libXext \
      vulkan-loader \
      vulkan-loader-devel \
      vulkan-headers \
      glslc \
      vulkan-tools && \
    dnf clean all

WORKDIR /app

RUN python3 -m venv /opt/venv && \
    pip install --upgrade pip setuptools wheel

# ------------------------------------------------------------
# llama-cpp-python — compiled with Vulkan support.
# On CPU-only machines (Mac in container, no-GPU Linux),
# Vulkan won't find a device and llama.cpp falls back to
# CPU automatically. No harm done.
# ------------------------------------------------------------
RUN CMAKE_ARGS="-DGGML_VULKAN=off" \
    FORCE_CMAKE=1 \
    pip install llama-cpp-python
# ------------------------------------------------------------
# NVIDIA Vulkan ICD — file is always written, but
# VK_DRIVER_FILES is only exported at runtime when NVIDIA
# is actually detected. On Mac/CPU this file is never loaded.
# ------------------------------------------------------------
RUN mkdir -p /etc/vulkan/icd.d && \
    printf '%s\n' \
'{' \
'  "file_format_version": "1.0.1",' \
'  "ICD": {' \
'    "library_path": "libEGL_nvidia.so.0",' \
'    "api_version": "1.4.312"' \
'  }' \
'}' > /etc/vulkan/icd.d/nvidia_egl_icd.json

# ------------------------------------------------------------
# SMOKE TESTS
# ------------------------------------------------------------
RUN printf '%s\n' \
'import sys, ctypes.util' \
'print("Python:", sys.version)' \
'print("Vulkan loader:", ctypes.util.find_library("vulkan"))' \
'import llama_cpp' \
'print("llama_cpp OK")' \
> /app/test_vulkan.py

RUN printf '%s\n' \
'from llama_cpp import Llama' \
'import os' \
'model = os.environ.get("LLAMA_MODEL", "/models/model.gguf")' \
'print("model:", model)' \
'llm = Llama(model_path=model, n_gpu_layers=999, verbose=True)' \
'out = llm("Q: say hello in one word\nA:", max_tokens=8)' \
'print(out["choices"][0]["text"])' \
> /app/test_infer.py

# ------------------------------------------------------------
# ENTRYPOINT — runtime hardware detection
#
#   GPU_MODE=nvidia  → discrete NVIDIA GPU found, Vulkan on
#   GPU_MODE=vulkan  → other Vulkan device (e.g. Podman/Mac passthrough)
#   GPU_MODE=cpu     → no GPU, CPU fallback
#
# Your app can read $GPU_MODE to decide n_gpu_layers etc.
# ------------------------------------------------------------
RUN printf '%s\n' \
'#!/usr/bin/env bash' \
'set -e' \
'' \
'export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/tmp/xdg-runtime}' \
'mkdir -p "$XDG_RUNTIME_DIR"' \
'' \
'GPU_MODE="cpu"' \
'' \
'if vulkaninfo --summary 2>/dev/null | grep -q "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU"; then' \
'    GPU_MODE="nvidia"' \
'    export VK_DRIVER_FILES=/etc/vulkan/icd.d/nvidia_egl_icd.json' \
'    echo "[entrypoint] NVIDIA discrete GPU → Vulkan enabled"' \
'elif vulkaninfo --summary 2>/dev/null | grep -q "deviceType"; then' \
'    GPU_MODE="vulkan"' \
'    echo "[entrypoint] Vulkan device (non-NVIDIA) → Vulkan enabled"' \
'else' \
'    GPU_MODE="cpu"' \
'    echo "[entrypoint] No GPU → CPU mode"' \
'fi' \
'' \
'export GPU_MODE' \
'echo "[entrypoint] Mode: $GPU_MODE"' \
'' \
'echo "=== Vulkan summary ==="' \
'vulkaninfo --summary 2>/dev/null || echo "(no display or no Vulkan)"' \
'' \
'echo "=== Python / llama_cpp ==="' \
'python /app/test_vulkan.py || true' \
'' \
'if [ -f "${LLAMA_MODEL:-/models/model.gguf}" ]; then' \
'    echo "=== Inference test ==="' \
'    python /app/test_infer.py || true' \
'else' \
'    echo "[entrypoint] No model mounted, skipping inference test"' \
'fi' \
'' \
'exec "$@"' \
> /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]