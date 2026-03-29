# Krkn Retriever

Two-stage retrieval (embedding search + cross-encoder reranking) over Krkn scenario docs. This repository indexes Markdown docs under the top-level `docs/` directory and serves fast, high-quality matches for scenario queries.

## What this repo uses

- Source docs: `./docs` (repository root)
- Index output: `./krkn-retriever/faiss-index`
- Retriever code: `./krkn-retriever`

`krkn-hub` is not required for indexing or querying in this repo. The retriever reads directly from `./docs`.

## Quick start

From the repository root:

```bash
podman build -t krkn-retriever:v1 .
```

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
```

## Benchmark

From the container:

```bash
python3 benchmark_retriever.py --dataset data.csv --retrieve-k 10 --rerank-k 5
```

## Notes

- If you change docs, re-run `python3 retriever.py index` to rebuild the FAISS index.
