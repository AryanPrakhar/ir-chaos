# Krkn Retriever

Two-stage retrieval (embedding search + cross-encoder reranking) over Krkn scenario docs. This repository indexes Markdown docs under the top-level `docs/` directory and serves fast, high-quality matches for scenario queries.

## What this repo uses

- Source docs: `./docs` (repository root)
- Index output: `./krkn-retriever/faiss-index`
- Retriever code: `./krkn-retriever`

`krkn-hub` is not required for indexing or querying in this repo. The retriever reads directly from `./docs`.

## Architecture

- Retrieval container: builds index and returns top-matching scenarios.
- Inference container: runs local LLM generation from retrieval export JSON.
- Handoff format: retrieval writes a JSON file, inference reads it and writes a response JSON.

## Build images

From the repository root:

```bash
podman build -t krkn-retriever:v1 -f krkn-retriever/Dockerfile .
podman build -t krkn-inference:v1 -f inference/Dockerfile .
```

## Retrieval quick start

```
podman run -it --rm \                                                                               
  -v ./krkn-retriever:/app:Z \
  -v ./docs:/app/docs:Z \
  -v ./krkn-retriever/outputs:/outputs:Z \
  -v ~/.cache/huggingface:/root/.cache/huggingface:Z \
  -w /app \
  krkn-retriever:v1 bash
```

Inside the container:

```bash
python3 retriever.py index
python3 retriever.py query -i
python3 retriever.py query "Simulate cluster power loss and send metrics to external collector"

# Export retrieval results for inference handoff
python3 retriever.py query "Simulate node memory pressure" \
  --retrieve-k 10 --rerank-k 5 \
  --export /outputs/retrieval_output.json \
  --include-text
```

## Inference from retrieval export

Run inference container with:

- a mounted retrieval export JSON file
- a mounted GGUF model path

```bash
podman run --rm \
  -v ./shared:/io:Z \
  -v /absolute/path/to/models:/models:Z \
  krkn-inference:v1 \
  python3 /app/run_inference.py \
    --input /io/retrieval_output.json \
    --output /io/inference_output.json \
    --model /models/your-model.gguf
```

## End-to-end (recommended)

Use the provided script to run retrieval -> export -> inference in one command.

Pipeline behavior:

- Reuses existing images (builds only if missing).
- Uses existing FAISS index if present.
- Builds index automatically only when missing.
- Runs retrieval and inference for each query.

Run with explicit model path:

```bash
./scripts/pipeline_retrieve_infer.sh \
  "Generate a chaos validation plan for network packet loss" \
  /absolute/path/to/model.gguf
```

Run with default model path (query only):

```bash
./scripts/pipeline_retrieve_infer.sh "Generate a chaos validation plan for network packet loss"
```

Default model path used by the script:

- `./models/Qwen2.5-3B-Instruct-Q4_K_M.gguf`

You can also set:

```bash
export LLM_MODEL_PATH=/absolute/path/to/your-model.gguf
```

Then run query-only:

```bash
./scripts/pipeline_retrieve_infer.sh "Generate a chaos validation plan for network packet loss"
```

## Inference LLM

Inference uses llama.cpp through `llama-cpp-python` in the inference container.

Model choice:

- Recommended small, strong model: Qwen2.5-3B-Instruct GGUF, quantized as Q4_K_M.
- By default the pipeline looks for: `./models/Qwen2.5-3B-Instruct-Q4_K_M.gguf`.
- You can pass any GGUF model path to the script if you want a different model.

Outputs are written to:

- `./shared/retrieval_output.json`
- `./shared/inference_output.json`

## macOS GPU setup (Podman + Apple Silicon)

For Vulkan-capable GPU inference inside Podman VM on macOS, follow the applehv + krunkit setup:

1. Install/upgrade Podman from brew.
2. Set machine provider to `applehv` in `~/.config/containers/containers.conf`:

```toml
[machine]
  provider = "applehv"
```

3. Initialize machine if needed:

```bash
podman machine init
```

4. Install krunkit:

```bash
brew tap slp/krunkit
brew install krunkit
```

5. Replace vfkit with krunkit (temporary workaround used by the upstream blog flow).
6. Start VM and verify render node exists:

```bash
podman machine start
podman machine ssh
ls /dev/dri
```

If `renderD128` is present, the inference container can use Vulkan path (`GPU_MODE=vulkan`).

## Linux/PC fallback

If no Vulkan GPU is available, inference still runs in CPU mode automatically (`n_gpu_layers=0`). No command changes are required.

## Benchmark

From the container:

```bash
python3 benchmark_retriever.py --dataset data.csv --retrieve-k 10 --rerank-k 5
```

## Notes

- If you change docs, re-run `python3 retriever.py index` to rebuild the FAISS index.
