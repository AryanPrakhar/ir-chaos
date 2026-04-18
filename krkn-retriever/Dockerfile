FROM registry.fedoraproject.org/fedora:42

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app

# GGML_BACKEND: vulkan (macOS Docker Desktop) or cpu (default)
ARG GGML_BACKEND=cpu

# ── Base build tools ──
RUN dnf -y install --setopt=install_weak_deps=False \
      python3 python3-pip python3-devel python3-virtualenv \
      gcc gcc-c++ cmake ninja-build make pkgconf-pkg-config && \
    dnf clean all

# ── Vulkan packages (macOS Docker Desktop via Venus/libkrun) ──
RUN if [ "$GGML_BACKEND" = "vulkan" ]; then \
      dnf -y install dnf-plugins-core dnf-plugin-versionlock && \
      dnf -y copr enable slp/mesa-libkrun-vulkan && \
      dnf -y install --setopt=install_weak_deps=False \
        vulkan-loader vulkan-loader-devel vulkan-headers \
        mesa-vulkan-drivers glslc && \
      dnf versionlock add mesa-vulkan-drivers && \
      dnf clean all; \
    fi

RUN python3 -m venv /opt/venv && \
    pip install --upgrade pip setuptools wheel

# ── llama.cpp (Vulkan-accelerated on macOS, CPU elsewhere) ──
RUN if [ "$GGML_BACKEND" = "vulkan" ]; then \
      CMAKE_ARGS="-DGGML_VULKAN=on" \
      FORCE_CMAKE=1 \
      pip install --no-binary=llama-cpp-python llama-cpp-python; \
    else \
      pip install llama-cpp-python; \
    fi

# ── PyTorch CPU + ML dependencies ──
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install \
      fastapi \
      uvicorn \
      transformers==4.52.4 \
      huggingface_hub[cli] \
      sentence-transformers \
      faiss-cpu \
      FlagEmbedding==1.2.3

# Track which backend the image was built with
ENV GGML_BACKEND_BUILT=${GGML_BACKEND}

RUN printf '%s\n' \
    '#!/usr/bin/env bash' \
    'set -e' \
    'exec "$@"' \
    > /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]
