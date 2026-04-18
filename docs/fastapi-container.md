# FastAPI Container (krkn-retriever)

Containerized FastAPI service entrypoint:

```python
logger.info("Starting krknctl Scenario Identification Service...")
uvicorn.run(app, host="0.0.0.0", port=8080, log_level="info")
```

## Build

```bash
podman build -t krkn-retriever:fastapi -f krkn-retriever/Dockerfile .
```

## Run

```bash
podman run --rm -p 8080:8080 krkn-retriever:fastapi
```

## Quick test

```bash
curl -s http://127.0.0.1:8080/
curl -s http://127.0.0.1:8080/health
curl -s -X POST http://127.0.0.1:8080/retrieve \
  -H 'content-type: application/json' \
  -d '{"query":"delete all pods in namespace to test recovery","k":5,"rerank_k":3}'
```
