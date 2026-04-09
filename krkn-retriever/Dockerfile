FROM registry.fedoraproject.org/fedora:40

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH=/opt/venv/bin:$PATH

WORKDIR /app

ARG NVIDIA_EGL_ICD=1
ARG TORCH_BUILD=auto
ARG TORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu126
ARG VK_DRIVER_FILES=""
ENV VK_DRIVER_FILES=${VK_DRIVER_FILES}

RUN dnf -y install --setopt=install_weak_deps=False \
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
    dnf clean all

RUN python3 -m venv /opt/venv && \
    pip install --upgrade pip setuptools wheel

# Optional NVIDIA EGL ICD (for headless NVIDIA Vulkan environments).
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

# Vulkan-enabled llama.cpp for embedding acceleration.
RUN CMAKE_ARGS="-DGGML_VULKAN=on" \
    FORCE_CMAKE=1 \
    pip install --no-binary=llama-cpp-python llama-cpp-python

# Torch: GPU-first when auto/cuda, CPU when requested.
RUN set -eux; \
    if [ "$TORCH_BUILD" = "cuda" ]; then \
      pip install --index-url "$TORCH_CUDA_INDEX_URL" torch; \
    elif [ "$TORCH_BUILD" = "cpu" ]; then \
      pip install torch; \
    else \
      pip install --index-url "$TORCH_CUDA_INDEX_URL" torch || pip install torch; \
    fi && \
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
