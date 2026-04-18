Use the container image only — no venv.

**1. Build the image**
```bash
cd /home/ubuntu/ir-chaos
podman build -t krkn-retriever:fastapi -f krkn-retriever/Dockerfile .
```

**2. Run the FastAPI service**
```bash
podman run --rm -p 8080:8080 krkn-retriever:fastapi
```

**3. Check it**
```bash
curl -s http://127.0.0.1:8080/
curl -s http://127.0.0.1:8080/health
```

**4. Query it**
```bash
curl -s -X POST http://127.0.0.1:8080/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model":"krkn-retriever","messages":[{"role":"user","content":"delete all pods in namespace to test restart behavior"}],"stream":false,"retrieve_k":5,"rerank_k":3}'
```

**5. Run the pipeline with the same image**
```bash
RETRIEVER_IMAGE=krkn-retriever:fastapi ./scripts/pipeline_retrieve_only.sh "delete pods in namespace to test restart behavior" 5 3
```

If you want a rebuild on the next pipeline run:
```bash
RETRIEVER_IMAGE=krkn-retriever:fastapi RETRIEVER_FORCE_BUILD=1 ./scripts/pipeline_retrieve_only.sh "your query" 5 3
```