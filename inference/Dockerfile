FROM registry.fedoraproject.org/fedora:40

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PATH=/opt/venv/bin:$PATH
ENV CMAKE_BUILD_PARALLEL_LEVEL=1

RUN dnf -y update && \
    dnf -y install \
      python3 \
      python3-pip \
      python3-devel \
      python3-virtualenv \
      cmake \
      ninja-build \
      gcc \
      gcc-c++ \
      make \
      pkgconf-pkg-config \
      vulkan-loader \
      vulkan-loader-devel \
      vulkan-headers \
      vulkan-tools \
      glslc \
      git && \
    dnf clean all

WORKDIR /app

RUN python3 -m venv /opt/venv && \
    pip install --upgrade pip setuptools wheel

# Build llama.cpp with Vulkan enabled for macOS Podman Venus or Linux Vulkan.
# If no GPU device is exposed at runtime, we still run with CPU (n_gpu_layers=0).
RUN CMAKE_ARGS="-DGGML_VULKAN=on" \
    FORCE_CMAKE=1 \
    pip install --no-cache-dir llama-cpp-python

RUN mkdir -p /etc/vulkan/icd.d && \
    printf '%s\n' \
'{' \
'  "file_format_version": "1.0.1",' \
'  "ICD": {' \
'    "library_path": "libEGL_nvidia.so.0",' \
'    "api_version": "1.4.312"' \
'  }' \
'}' > /etc/vulkan/icd.d/nvidia_egl_icd.json

COPY inference/run_inference.py /app/run_inference.py

RUN printf '%s\n' \
'#!/usr/bin/env bash' \
'set -e' \
'' \
'GPU_MODE="cpu"' \
'VINFO="$(vulkaninfo --summary 2>/dev/null || true)"' \
'if echo "$VINFO" | grep -q "PHYSICAL_DEVICE_TYPE_DISCRETE_GPU"; then' \
'    GPU_MODE="nvidia"' \
'    export VK_DRIVER_FILES=/etc/vulkan/icd.d/nvidia_egl_icd.json' \
'elif echo "$VINFO" | grep -Eq "PHYSICAL_DEVICE_TYPE_(INTEGRATED_GPU|DISCRETE_GPU)" && ! echo "$VINFO" | grep -qi "llvmpipe"; then' \
'    GPU_MODE="vulkan"' \
'fi' \
'' \
'export GPU_MODE' \
'echo "[entrypoint] GPU_MODE=$GPU_MODE"' \
'echo "$VINFO"' \
'exec "$@"' \
> /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["python3", "/app/run_inference.py", "--help"]
