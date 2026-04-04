FROM registry.fedoraproject.org/fedora:40

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PATH=/opt/venv/bin:$PATH

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

# Optional profile for Podman/libkrun on macOS Apple silicon.
# Set --build-arg MACOS_MESA_KRUNKIT=1 when building inside an aarch64 Podman machine.
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

# Torch installation strategy:
# - auto: try CUDA wheels first, fallback to CPU wheels
# - cuda: require CUDA wheels (fail build if unavailable)
# - cpu: force CPU wheels
ARG TORCH_BUILD=auto
ARG TORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu126
ARG TORCH_CPU_INDEX_URL=https://download.pytorch.org/whl/cpu

RUN set -eux; \
        if [ "$TORCH_BUILD" = "cuda" ]; then \
            pip install --no-cache-dir --index-url "$TORCH_CUDA_INDEX_URL" torch; \
        elif [ "$TORCH_BUILD" = "cpu" ]; then \
            pip install --no-cache-dir --index-url "$TORCH_CPU_INDEX_URL" torch; \
        else \
            pip install --no-cache-dir --index-url "$TORCH_CUDA_INDEX_URL" torch || \
            pip install --no-cache-dir --index-url "$TORCH_CPU_INDEX_URL" torch; \
        fi; \
        pip install --no-cache-dir \
    transformers==4.52.4 \
    huggingface_hub[cli] \
    sentence-transformers \
    faiss-cpu \
    FlagEmbedding==1.2.3

# Vulkan-enabled llama.cpp backend for cross-platform acceleration with GGUF models
RUN CMAKE_ARGS="-DGGML_VULKAN=on" \
    FORCE_CMAKE=1 \
    pip install --no-binary=llama-cpp-python llama-cpp-python

RUN printf '%s\n' \
'import sys' \
'import torch' \
'import faiss' \
'import llama_cpp' \
'from sentence_transformers import SentenceTransformer' \
'from FlagEmbedding import FlagReranker' \
'print("Python:", sys.version)' \
'print("Torch:", torch.__version__)' \
'print("Torch CUDA version:", torch.version.cuda)' \
'print("Torch CUDA available:", torch.cuda.is_available())' \
'print("llama_cpp:", llama_cpp.__version__)' \
'print("FAISS:", faiss.__version__)' \
'print("SentenceTransformer + FlagReranker import OK")' \
> /app/test_retriever.py

RUN printf '%s\n' \
'#!/usr/bin/env bash' \
'set -e' \
'echo "=== Retrieval container smoke test ==="' \
'if [ -f /app/test_retriever.py ]; then python /app/test_retriever.py || true; else echo "(skipped: /app/test_retriever.py not present in bind mount)"; fi' \
'exec "$@"' \
> /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]