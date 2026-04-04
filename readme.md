# Retrieval Quick Start

Recommended one-command workflow:

```bash
./scripts/pipeline_retrieve_only.sh "I want to measure the downtime if a rogue script deletes all the routing objects and deployments in our tenant space." 5 3
```

This script builds the image (if needed), ensures FAISS index exists, and runs retrieval+rereanking.

## Vulkan acceleration path

```bash
RETRIEVER_BACKEND=vulkan RETRIEVER_FORCE_BUILD=1 ./scripts/pipeline_retrieve_only.sh "your query" 5 3
```

## macOS Apple silicon (Metal via Vulkan)

```bash
RETRIEVER_BACKEND=vulkan \
RETRIEVER_ACCELERATION=gpu \
RETRIEVER_FORCE_BUILD=1 \
RETRIEVER_EXTRA_BUILD_ARGS='--build-arg MACOS_MESA_KRUNKIT=1' \
./scripts/pipeline_retrieve_only.sh "your query" 10 5
```

See `run.md` for full run options and `macOS-acceleration.md` for Apple-silicon setup details.

