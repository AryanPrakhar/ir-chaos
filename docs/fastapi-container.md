# FastAPI Container (krkn-retriever)

Containerized FastAPI service entrypoint:

```python
# api_server.py runs two servers:
# - compat API on :8080
# - debug API on :18080
```

## Build

```bash
podman build -t krkn-retriever:fastapi -f krkn-retriever/Dockerfile .
```

## Run

```bash
podman run --rm -p 8080:8080 -p 18080:18080 krkn-retriever:fastapi
```

## Quick test

```bash
curl -s http://127.0.0.1:8080/
curl -s http://127.0.0.1:8080/health
curl -s http://127.0.0.1:18080/health
curl -s -X POST http://127.0.0.1:18080/retrieve \
  -H 'content-type: application/json' \
  -d '{"query":"delete all pods in namespace to test recovery","k":5,"rerank_k":3}' \
| jq
curl -s -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"krkn-retriever","messages":[{"role":"user","content":"delete all pods in namespace to test recovery"}]}' \
| jq
```
