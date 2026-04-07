FROM registry.fedoraproject.org/fedora:40

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PATH=/opt/venv/bin:$PATH

# ------------------------------------------------------------
# MANDATORY RUNTIME SECTION — required for Vulkan runtime
# Based on canonical Dockerfile-baseline
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
      vulkan-loader \
      vulkan-loader-devel \
      vulkan-headers \
      mesa-vulkan-drivers \
      glslc \
      libXext \
      openblas-devel && \
    dnf clean all

WORKDIR /app

# macOS Apple Silicon: replace stock mesa with Venus-capable krunkit build.
# Required for the Venus/libkrun/MoltenVK GPU acceleration pipeline.
# Pass --build-arg MACOS_MESA_KRUNKIT=1 when building on macOS.
ARG MACOS_MESA_KRUNKIT=0

RUN set -eux; \
    if [ "$MACOS_MESA_KRUNKIT" = "1" ] && [ "$(uname -m)" = "aarch64" ]; then \
        dnf -y install dnf-plugins-core dnf-plugin-versionlock --setopt=install_weak_deps=False; \
        dnf -y copr enable slp/mesa-krunkit fedora-40-aarch64; \
        dnf -y downgrade mesa-vulkan-drivers.aarch64 --repo=copr:copr.fedorainfracloud.org:slp:mesa-krunkit; \
        dnf -y versionlock add mesa-vulkan-drivers; \
        dnf clean all; \
    fi

RUN python3 -m venv /opt/venv && \
    pip install --upgrade pip setuptools wheel

# NVIDIA headless Vulkan ICD (conditional — skip on macOS)
ARG NVIDIA_EGL_ICD=1

RUN set -eux; \
    if [ "$NVIDIA_EGL_ICD" = "1" ]; then \
        mkdir -p /etc/vulkan/icd.d && \
        printf '%s\n' \
            '{' \
            '  "file_format_version": "1.0.1",' \
            '  "ICD": {' \
            '    "library_path": "libEGL_nvidia.so.0",' \
            '    "api_version": "1.4.312"' \
            '  }' \
            '}' > /etc/vulkan/icd.d/nvidia_egl_icd.json; \
    fi

ARG VK_DRIVER_FILES=""
ENV VK_DRIVER_FILES=${VK_DRIVER_FILES}

# Vulkan-enabled llama.cpp for cross-platform GGUF embedding acceleration
RUN CMAKE_ARGS="-DGGML_VULKAN=on" \
    FORCE_CMAKE=1 \
    pip install --no-binary=llama-cpp-python llama-cpp-python

# Torch: auto tries CUDA first, falls back to CPU
ARG TORCH_BUILD=auto
ARG TORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu126

RUN set -eux; \
    if [ "$TORCH_BUILD" = "cuda" ]; then \
        pip install --no-cache-dir --index-url "$TORCH_CUDA_INDEX_URL" torch; \
    elif [ "$TORCH_BUILD" = "cpu" ]; then \
        pip install --no-cache-dir torch; \
    else \
        pip install --no-cache-dir --index-url "$TORCH_CUDA_INDEX_URL" torch || \
        pip install --no-cache-dir torch; \
    fi; \
    pip install --no-cache-dir \
        transformers==4.52.4 \
        huggingface_hub[cli] \
        sentence-transformers \
        faiss-cpu \
        FlagEmbedding==1.2.3

RUN printf '%s\n' \
    '#!/usr/bin/env bash' \
    'set -e' \
    'exec "$@"' \
    > /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
