FROM --platform=linux/arm64 fedora:42

USER 0

# ── [1/4] Mesa libkrun Vulkan drivers (locked before anything else) ──────────
#
# Must install before any other mesa package lands via transitive deps, or dnf
# will pull the stock mesa build and the versionlock will conflict.
RUN dnf -y install \
        dnf-plugins-core \
        dnf-plugin-versionlock && \
    dnf -y copr enable slp/mesa-libkrun-vulkan && \
    dnf -y install \
        mesa-vulkan-drivers.aarch64 \
        vulkan-loader-devel.aarch64 \
        vulkan-headers \
        vulkan-tools.aarch64 \
        vulkan-loader.aarch64 \
        glslc && \
    dnf versionlock add mesa-vulkan-drivers && \
    dnf clean all

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
WORKDIR /app

ARG GGML_BACKEND=vulkan
ENV GGML_BACKEND_BUILT=${GGML_BACKEND}
ARG TORCH_BUILD=cpu
ARG TORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu126

# ── [2/4] Python + build tools ───────────────────────────────────────────────
RUN dnf -y install --setopt=install_weak_deps=False \
    git \
    python3 python3-pip python3-devel \
    gcc gcc-c++ cmake ninja-build make pkgconf-pkg-config \
    spirv-headers-devel && \
    dnf clean all

# ── [3/4] llama-cpp-python with Vulkan backend ───────────────────────────────
#
# GGML_VULKAN_COOPMAT* disabled: cooperative matrix extensions require
# Vulkan 1.3 features not guaranteed on Mesa Venus (virtio-gpu).
RUN pip install --upgrade pip setuptools wheel && \
    CMAKE_ARGS="\
      -DGGML_VULKAN=on \
      -DGGML_VULKAN_COOPMAT=OFF \
      -DGGML_VULKAN_COOPMAT2=OFF \
    " FORCE_CMAKE=1 \
      pip install --no-binary=llama-cpp-python "llama-cpp-python==0.3.19"

# ── [4/4] Python runtime dependencies ────────────────────────────────────────
#
# torch: CPU-only wheel by default (Vulkan acceleration goes through llama.cpp
#        for embedding; torch is only needed as transformers backend for the
#        reranker ONNX export step and as an inference fallback).
#
# onnxruntime: used by OnnxCrossEncoder for cross-encoder reranking.
#              No GPU dependency required for 20-document workloads.
#
# optimum[onnxruntime]: preferred ONNX export path from HuggingFace models.
#
# FlagEmbedding intentionally removed: FlagReranker replaced by OnnxCrossEncoder.
RUN if [ "$TORCH_BUILD" = "cuda" ]; then \
      pip install --index-url "$TORCH_CUDA_INDEX_URL" torch; \
    else \
      pip install --index-url https://download.pytorch.org/whl/cpu torch; \
    fi && \
    pip install \
      fastapi \
      uvicorn \
      "transformers>=4.52.4" \
      "huggingface_hub[cli]" \
      sentence-transformers \
      faiss-cpu \
      onnxruntime \
      "optimum[onnxruntime]" \
      requests

COPY krkn-assist/ /app/

EXPOSE 8080 18080
CMD ["python3", "api_server.py"]
