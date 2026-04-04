FROM registry.fedoraproject.org/fedora:40

ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV PATH=/opt/venv/bin:$PATH

# 1. System Dependencies 
RUN dnf -y update && \
    dnf -y install \
      python3 python3-pip python3-devel python3-virtualenv \
      git cmake ninja-build gcc gcc-c++ make pkgconf-pkg-config \
      openblas-devel \
      zlib-devel \
      curl which findutils && \
    dnf clean all

WORKDIR /app

# 2. Create Virtual Environment
RUN python3 -m venv /opt/venv && \
    pip install --upgrade pip setuptools wheel

# 3. Install ML Libraries
RUN pip install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir \
    transformers==4.52.4 \
    huggingface_hub[cli] \
    sentence-transformers \
    faiss-cpu \
    FlagEmbedding==1.2.3 \
    llama-cpp-python  # Added missing requirement for your smoke test

# ============================================================
# DEBUG / DEV SECTION
# ============================================================

# Smoke test (Fixed to verify local CPU operation)
RUN printf 'import sys\n\
import torch\n\
print(f"Python: {sys.version}")\n\
print(f"Torch CPU OK: {torch.__version__}")\n\
try:\n\
    import llama_cpp\n\
    print("llama_cpp OK")\n\
except ImportError: print("llama_cpp missing")\n\
from FlagEmbedding import FlagReranker\n\
print("FlagReranker import OK")\n\
import faiss\n\
print("FAISS CPU OK")' > /opt/test_init.py

# Entrypoint 
RUN printf '#!/usr/bin/env bash\n\
set -e\n\
echo "=== System Info ==="\n\
lscpu | grep "Model name" || sysctl -n machdep.cpu.brand_string || true\n\
echo "=== Python smoke test ==="\n\
python /opt/test_init.py\n\
exec "$@"' > /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["bash"]