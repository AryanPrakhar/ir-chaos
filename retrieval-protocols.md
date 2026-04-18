# Retrieval Protocols (API, Pipeline, Benchmark)

This note defines the required usage protocol so scores, ranking, and latency comparisons are consistent.

## 1) Pick one service endpoint and stick to it

Two common ports may be active at once:

- `127.0.0.1:8080` → standalone API server
- `127.0.0.1:18080` → warm API started by `scripts/pipeline_retrieve_only.sh` (default `RETRIEVER_API_PORT`)

If you compare outputs across tools, always hit the **same port**.

## 2) Standard query protocol

Use `/retrieve` with explicit `k` and `rerank_k`.

```bash
curl -sS -X POST http://127.0.0.1:18080/retrieve \
  -H 'content-type: application/json' \
  -d '{"query":"plz skew time on pods with label app=frontend,krknctl run time-scenarios --label-selector app=frontend --action skew_time","k":10,"rerank_k":5}' \
  | python3 -m json.tool
```

## 3) Pipeline protocol

Pipeline queries always go through its warm API base URL:

- `API_PORT="${RETRIEVER_API_PORT:-18080}"`
- `API_BASE_URL="http://127.0.0.1:${API_PORT}"`

So parity checks must query the same `API_BASE_URL` (not a different API on 8080).

## 4) Score interpretation protocol

For each result:

- `retrieval_score`: FAISS similarity (0..1)
- `rerank_score`: raw cross-encoder logit
- `final_score`: hybrid match score used for ranking and display
  - computed as: `0.8 * sigmoid(rerank_score) + 0.2 * clamp(retrieval_score, 0, 1)`

UI `MATCH` in pipeline is based on `final_score` (or back-compat fallback if absent).

## 5) Debug protocol when scores differ

1. Check both endpoints:

```bash
curl -sS http://127.0.0.1:8080/health
curl -sS http://127.0.0.1:18080/health
```

2. Re-run the same query against both ports with same `k/rerank_k`.
3. Compare top result fields: `id`, `rerank_score`, `retrieval_score`, `final_score`.
4. If different, treat as different runtime/model instances (not a math bug).

## 6) Benchmark protocol (API latency path)

`krkn-retriever/benchmark_retriever.py` supports:

- `--mode local` (in-process ranker)
- `--mode api` (HTTP `/retrieve` latency)

Run 200 samples with progress every 10:

```bash
cd /home/ubuntu/ir-chaos/krkn-retriever
../venv/bin/python benchmark_retriever.py \
  --mode api \
  --api-url http://127.0.0.1:18080 \
  --dataset data.csv \
  --retrieve-k 10 \
  --rerank-k 5 \
  --limit 200
```

Progress lines appear as:

```text
[10] Top-1 Acc: ... | Avg Latency: ...ms
[20] Top-1 Acc: ... | Avg Latency: ...ms
...
```

## 7) Reproducibility checklist

- Fix endpoint (`8080` **or** `18080`)
- Fix params (`k`, `rerank_k`)
- Use same query string verbatim
- Verify service health before benchmarking
- Record mode (`local` or `api`) in reports/logs
