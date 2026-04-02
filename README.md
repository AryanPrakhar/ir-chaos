# Krkn Retriever

Two-stage retrieval (embedding search + cross-encoder reranking) over Krkn scenario docs. This repository indexes Markdown docs under the top-level `docs` directory and serves fast, high-quality matches for scenario queries.

## What this repo uses

- Source docs: `./docs` (repository root)
- Index output: `./krkn-retriever/faiss-index`
- Retriever code: `./krkn-retriever`

`krkn-hub` is not required for indexing or querying in this repo. The retriever reads directly from `./docs`.

## Architecture

- Retrieval container: builds index and returns top-matching scenarios.
- Inference container: runs local LLM generation from retrieval export JSON.
- Handoff format: retrieval writes JSON, inference reads it and writes response JSON.

## Build images

From the repository root:

```bash
podman build -t krkn-retriever:v1 -f krkn-retriever/Dockerfile .
podman build -t krkn-inference:v1 -f inference/Dockerfile .
```

## Retrieval quick start

```bash
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

## End-to-end pipeline

Use the helper script to run retrieval -> export -> inference in one command.

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

### Optional inference runtime controls

- `INFERENCE_IMAGE`: inference image tag (default: `krkn-inference:v1`)
- `INFERENCE_GPU_MODE`: force `cpu`, `vulkan`, or `nvidia`
- `INFERENCE_PODMAN_DEVICE`: add `--device` for inference container
- `INFERENCE_PODMAN_SECURITY_OPT`: add `--security-opt` for inference container

Example Vulkan run:

```bash
export INFERENCE_GPU_MODE=vulkan
export INFERENCE_PODMAN_DEVICE=/dev/dri/renderD128
./scripts/pipeline_retrieve_infer.sh "Generate a node network chaos plan"
```

Outputs are written to:

- `./shared/retrieval_output.json`
- `./shared/inference_output.json`

## macOS GPU setup (Podman + Apple Silicon)

For Vulkan-capable GPU inference inside Podman VM on macOS, follow the applehv + krunkit setup:

1. Install or upgrade Podman from brew.
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

5. **KNOWN ISSUE: Podman 5.8 + krunkit 1.1.1 incompatibility**
   - Podman 5.8's applehv provider injects `--device rosetta` into vfkit args
   - krunkit 1.1.1 CLI does not accept rosetta device flag → vfkit exits with error
   - **Workaround**: Use default applehv/vfkit (no krunkit swap), or downgrade Podman to 5.7
   - If machine won't start with "vfkit error code 2", try:
     ```bash
     podman machine stop podman-machine-default
     podman machine rm -f podman-machine-default
     podman machine init
     ```

6. START VM (without krunkit swap for now, given Podman 5.8 compatibility issues):

```bash
podman machine start
podman machine ssh
ls /dev/dri
```

If `renderD128` is present, Vulkan path should be available. If machine fails to start, see **Known Issue** above.

## Local dev on Linux + remote test on macOS

Develop on local machine, push the `vulkan` branch, and test remotely by fetching latest changes.

Local workflow:

```bash
git checkout vulkan
git add -A
git commit -m "Update Vulkan flow"
git push origin vulkan
```

Remote macOS workflow:

```bash
cd ~/dev/ir-chaos
git fetch origin
git checkout vulkan || git checkout -b vulkan origin/vulkan
git pull --ff-only origin vulkan
./scripts/pipeline_retrieve_infer.sh "Test query" /absolute/path/to/model.gguf
```

This keeps remote testing synced with latest local branch changes while code changes happen on local Linux.

## Linux/PC fallback

If no Vulkan GPU is available, inference still runs in CPU mode automatically (`n_gpu_layers=0`).

## Benchmark

From the container:

```bash
python3 benchmark_retriever.py --dataset data.csv --retrieve-k 10 --rerank-k 5
```

## Notes

- If you change docs, re-run `python3 retriever.py index` to rebuild the FAISS index.
