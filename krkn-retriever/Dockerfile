FROM registry.fedoraproject.org/fedora:42

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app

ARG TORCH_BUILD=auto
ARG TORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu126
ARG VK_DRIVER_FILES=""
ENV VK_DRIVER_FILES=${VK_DRIVER_FILES}

# Vulkan runtime + build tools (Venus-enabled mesa for macOS Docker Desktop)
RUN dnf -y install dnf-plugins-core dnf-plugin-versionlock && \
    dnf -y copr enable slp/mesa-libkrun-vulkan && \
    dnf -y install --setopt=install_weak_deps=False \
      python3 \
      python3-pip \
      python3-devel \
      python3-virtualenv \
      gcc \
      gcc-c++ \
      cmake \
      ninja-build \
      make \
      pkgconf-pkg-config \
      vulkan-loader \
      vulkan-loader-devel \
      vulkan-headers \
      mesa-vulkan-drivers \
      glslc && \
    dnf versionlock add mesa-vulkan-drivers && \
    dnf clean all

RUN python3 -m venv /opt/venv && \
    pip install --upgrade pip setuptools wheel

# llama.cpp with Vulkan acceleration
RUN CMAKE_ARGS="-DGGML_VULKAN=on" \
    FORCE_CMAKE=1 \
    pip install --no-binary=llama-cpp-python llama-cpp-python

# PyTorch + ML dependencies (CPU wheels; GPU acceleration via Vulkan/llama.cpp)
RUN pip install torch && \
    pip install \
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
