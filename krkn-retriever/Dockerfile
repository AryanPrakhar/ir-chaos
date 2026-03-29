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
      gcc \
      gcc-c++ \
      make \
      pkgconf-pkg-config \
      openblas-devel && \
    dnf clean all

WORKDIR /app

RUN python3 -m venv /opt/venv && \
    pip install --upgrade pip setuptools wheel

RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir \
    transformers==4.52.4 \
    huggingface_hub[cli] \
    sentence-transformers \
    faiss-cpu \
    FlagEmbedding==1.2.3

RUN printf '%s\n' \
'import sys' \
'import torch' \
'import faiss' \
'from sentence_transformers import SentenceTransformer' \
'from FlagEmbedding import FlagReranker' \
'print("Python:", sys.version)' \
'print("Torch:", torch.__version__)' \
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