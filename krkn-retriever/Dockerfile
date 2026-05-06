FROM --platform=linux/arm64 fedora:42

USER 0

# PRIORITY BLOCK: Install specialized libkrun Vulkan drivers and lock them
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
ENV GGML_BACKEND_BUILT=vulkan
ARG TORCH_BUILD=auto
ARG TORCH_CUDA_INDEX_URL=https://download.pytorch.org/whl/cu126

# SECONDARY BLOCK: Python, Build tools, and remaining dependencies
# Note: Conflicting vulkan packages and glslc have been removed from here
RUN dnf -y install --setopt=install_weak_deps=False \
      python3 python3-pip python3-devel \
      gcc gcc-c++ cmake ninja-build make pkgconf-pkg-config \
      spirv-headers-devel && \
    dnf clean all

RUN pip install --upgrade pip setuptools wheel && \
    CMAKE_ARGS="\
      -DGGML_VULKAN=on \
      -DGGML_VULKAN_COOPMAT=OFF \
      -DGGML_VULKAN_COOPMAT2=OFF \
    " FORCE_CMAKE=1 \
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

COPY krkn-retriever/ /app/
COPY docs/ /app/docs/

EXPOSE 8080
CMD ["python3", "api_server.py"]