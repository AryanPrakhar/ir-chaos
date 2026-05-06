FROM registry.fedoraproject.org/fedora:42

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

ARG GGML_BACKEND=vulkan
ARG TORCH_BUILD=auto
ARG TORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu126

RUN dnf -y install --setopt=install_weak_deps=False \
      python3 python3-pip python3-devel \
      gcc gcc-c++ cmake ninja-build make pkgconf-pkg-config \
      vulkan-loader vulkan-loader-devel vulkan-headers \
      mesa-vulkan-drivers glslc \
      spirv-headers-devel && \
    dnf clean all

# Wrap glslc to block problematic shader capability probes
RUN mv /usr/bin/glslc /usr/bin/glslc.real && \
    printf '%s\n' \
'#!/bin/bash' \
'' \
'for arg in "$@"; do' \
'  case "$arg" in' \
'    /tmp/*)' \
'      if [ -f "$arg" ] && grep -qiE "cooperative_matrix|CooperativeMatrix|NV_cooperative|integer_dot_product|bfloat16|BFloat16" "$arg" 2>/dev/null; then' \
'        exit 1' \
'      fi' \
'      ;;' \
'  esac' \
'done' \
'' \
'exec /usr/bin/glslc.real "$@"' \
> /usr/bin/glslc && \
    chmod +x /usr/bin/glslc

RUN pip install --upgrade pip setuptools wheel && \
    CMAKE_ARGS="-DGGML_VULKAN=on" FORCE_CMAKE=1 \
      pip install --no-binary=llama-cpp-python "llama-cpp-python==0.3.19" && \
    if [ "$TORCH_BUILD" = "cuda" ]; then \
      pip install --index-url "$TORCH_CUDA_INDEX_URL" torch; \
    else \
      pip install --index-url https://download.pytorch.org/whl/cpu torch; \
    fi && \
    pip install \
      fastapi \
      uvicorn \
      transformers==4.52.4 \
      huggingface_hub[cli] \
      sentence-transformers \
      faiss-cpu \
      FlagEmbedding==1.2.3 \
      requests

# Restore original glslc
RUN mv /usr/bin/glslc.real /usr/bin/glslc

COPY krkn-retriever/ /app/
COPY docs/ /app/docs/

ENV GGML_BACKEND_BUILT=vulkan

EXPOSE 8080

CMD ["python3", "api_server.py"]