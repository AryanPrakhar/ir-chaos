## Fast Path

Run build + index + query in one command:

```bash
./scripts/pipeline_retrieve_only.sh "I want to measure the downtime if a rogue script deletes all the routing objects and deployments in our tenant space." 5 3
```

Default mode is acceleration-first with CPU fallback.

## Vulkan Backend (cross-platform)

Use Vulkan + GGUF embeddings:

```bash
RETRIEVER_BACKEND=vulkan RETRIEVER_FORCE_BUILD=1 ./scripts/pipeline_retrieve_only.sh "your query" 5 3
```

If needed, specify your own GGUF file:

```bash
RETRIEVER_BACKEND=vulkan \
LLAMA_EMBED_MODEL=/absolute/path/to/embedding.gguf \
RETRIEVER_FORCE_BUILD=1 \
./scripts/pipeline_retrieve_only.sh "your query" 5 3
```

Download the default GGUF model manually:

```bash
./scripts/download_vulkan_model.sh
```

## macOS Apple Silicon (Metal via Vulkan)

The pipeline now auto-detects macOS hosts and uses Podman `--device /dev/dri` for Vulkan GPU path.

```bash
RETRIEVER_BACKEND=vulkan \
RETRIEVER_ACCELERATION=gpu \
RETRIEVER_FORCE_BUILD=1 \
RETRIEVER_EXTRA_BUILD_ARGS='--build-arg MACOS_MESA_KRUNKIT=1' \
./scripts/pipeline_retrieve_only.sh "your query" 10 5
```

For full setup details, see `macOS-acceleration.md`.

## Useful Toggles

```bash
# force rebuild
RETRIEVER_FORCE_BUILD=1 ./scripts/pipeline_retrieve_only.sh "your query" 5 3

# force acceleration policy
RETRIEVER_ACCELERATION=gpu ./scripts/pipeline_retrieve_only.sh "your query" 5 3
RETRIEVER_ACCELERATION=cpu ./scripts/pipeline_retrieve_only.sh "your query" 5 3

# force CPU-only execution (legacy shortcut)
RETRIEVER_CPU_ONLY=1 ./scripts/pipeline_retrieve_only.sh "your query" 5 3

# torch build strategy in image build
RETRIEVER_TORCH_BUILD=auto RETRIEVER_FORCE_BUILD=1 ./scripts/pipeline_retrieve_only.sh "your query" 5 3
RETRIEVER_TORCH_BUILD=cuda RETRIEVER_FORCE_BUILD=1 ./scripts/pipeline_retrieve_only.sh "your query" 5 3
RETRIEVER_TORCH_BUILD=cpu  RETRIEVER_FORCE_BUILD=1 ./scripts/pipeline_retrieve_only.sh "your query" 5 3

# pass extra image build args
RETRIEVER_EXTRA_BUILD_ARGS='--build-arg KEY=VALUE' ./scripts/pipeline_retrieve_only.sh "your query" 5 3

# use root Dockerfile instead of krkn-retriever/Dockerfile
RETRIEVER_DOCKERFILE=./Dockerfile RETRIEVER_FORCE_BUILD=1 ./scripts/pipeline_retrieve_only.sh "your query" 5 3
```

## Manual Workflow (without pipeline script)

```bash
podman build -t krkn-retriever:v1 -f ./krkn-retriever/Dockerfile .
```

```bash
podman run -it --rm \
  -v ./krkn-retriever:/app:Z \
  -v ./docs:/app/docs:Z \
  -v ~/.cache/huggingface:/root/.cache/huggingface:Z \
  -e DOCS_DIR=/app/docs \
  krkn-retriever:v1 bash
```

Inside container:

```bash
python3 retriever.py index
python3 retriever.py query -i
python3 retriever.py query "Simulate cluster power loss and send metrics to external collector"
```

Benchmark:

```bash
python3 benchmark_retriever.py --dataset data.csv --retrieve-k 10 --rerank-k 5
```
