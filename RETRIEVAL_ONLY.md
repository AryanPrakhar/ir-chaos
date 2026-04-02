# Krkn Retriever - Retrieval-Only Branch

This is a dedicated retrieval and reranking pipeline with **no inference** and **no FastAPI**. Just fast, containerized retrieval + cross-encoder reranking.

## What This Does

- Indexes Markdown docs from `./docs/` into a FAISS vector store
- Retrieves top matching scenarios using dense embeddings (Qwen embedding model)
- Reranks with cross-encoder (bge-reranker-base) for final ranking
- Exports results as JSON for downstream use

## What This Does NOT Do

- ✗ No LLM inference
- ✗ No FastAPI server
- ✗ No docker-compose orchestration
- ✗ Just clean Podman container operations

## Quick Start

### 1. Build the container

```bash
podman build -t krkn-retriever:v1 -f krkn-retriever/Dockerfile .
```

### 2. Run retrieval + reranking

Using the pipeline script (recommended):

```bash
./scripts/pipeline_retrieve_only.sh "Simulate cluster power loss"
```

With custom retrieve-k and rerank-k:

```bash
./scripts/pipeline_retrieve_only.sh "Simulate cluster power loss" 15 8
```

Or manually in a container:

```bash
podman run -it --rm \
  -v ./krkn-retriever:/app:Z \
  -v ./docs:/app/docs:Z \
  -v ./shared:/io:Z \
  -v ~/.cache/huggingface:/root/.cache/huggingface:Z \
  -v ~/.cache/torch:/root/.cache/torch:Z \
  -e DOCS_DIR=/app/docs \
  -w /app \
  krkn-retriever:v1 \
  bash
```

Inside the container:

```bash
# Build index (one-time)
python3 retriever.py index

# Query with reranking
python3 retriever.py query "your query here" --retrieve-k 10 --rerank-k 5

# Export to JSON
python3 retriever.py query "your query" --retrieve-k 10 --rerank-k 5 \
  --export /io/retrieval_output.json --include-text
```

### 3. Check output

Results are in `./shared/retrieval_output.json`:

```json
{
  "query": "Simulate cluster power loss",
  "retrieved_scenarios": [
    {
      "doc_id": "power-outages",
      "score": 0.92,
      "text": "..."
    },
    ...
  ]
}
```

## What Models Are Used

- **Embedding**: `Qwen/Qwen3-Embedding-0.6B` (dense retrieval)
- **Reranker**: `BAAI/bge-reranker-base` (cross-encoder reranking)

Both are downloaded automatically on first run and cached locally.

## Project Structure

```
.
├── krkn-retriever/
│   ├── Dockerfile          # Retriever container
│   ├── retriever.py        # Core retrieval + reranking
│   ├── faiss-index/        # Built FAISS index
│   └── outputs/            # Query results
├── docs/                   # Scenario docs (indexed)
├── shared/                 # Pipeline output folder
└── scripts/
    └── pipeline_retrieve_only.sh   # Simplified pipeline
```

## Disk Space & Caching

Models are cached in:
- `~/.cache/huggingface/` (embeddings + reranker)
- `~/.cache/torch/` (PyTorch)

To use custom cache locations:

```bash
export HF_CACHE_DIR=/custom/hf/path
export TORCH_CACHE_DIR=/custom/torch/path
./scripts/pipeline_retrieve_only.sh "your query"
```

Or mount custom dirs:

```bash
podman run -it --rm \
  -v ./krkn-retriever:/app:Z \
  -v ./docs:/app/docs:Z \
  -v /my/hf/cache:/root/.cache/huggingface:Z \
  -v /my/torch/cache:/root/.cache/torch:Z \
  -w /app \
  krkn-retriever:v1 bash
```

## Performance Notes

- **First run**: ~30-60s (downloads models)
- **Index build**: ~5-10s (one-time, cached)
- **Query + rerank**: ~0.5-1s per query
- **GPU support**: Detects CUDA automatically, falls back to CPU

## API (in container)

The `retriever.py` module can be used programmatically:

```python
from retriever import CrossEncoderRanker

ranker = CrossEncoderRanker()
results = ranker.query("Simulate node CPU pressure", retrieve_k=10, rerank_k=5)
for doc in results["reranked_results"]:
    print(f"{doc['doc_id']}: {doc['score']:.3f}")
```

## Testing

From the container:

```bash
python3 retriever.py query "test query" --retrieve-k 5 --rerank-k 3
```

Should return top 3 scenarios sorted by cross-encoder score.

## Branch Purpose

This branch exists to provide a **pure retrieval pipeline** without the complexity of:
- Inference containers
- FastAPI endpoints
- Multi-stage orchestration

Use this when you only need fast scenario retrieval and reranking for downstream tools.
