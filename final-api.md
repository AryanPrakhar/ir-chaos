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

**4. Query it (primary endpoint)**
```bash
curl -s -X POST http://127.0.0.1:8080/retrieve \
  -H 'content-type: application/json' \
  -d '{"query":"delete all pods in namespace to test restart behavior","k":5,"rerank_k":3}'
```

Example response:
```json
{
  "query": "delete all pods in namespace to test restart behavior",
  "results": [
    {
      "id": "pod-scenarios",
      "name": "Pod Scenarios",
      "retrieval_score": 0.7128,
      "rerank_score": -7.5341,
      "final_score": 0.143,
      "score_percent": 14.3
    }
  ],
  "top_match": "pod-scenarios",
  "message": "Found 1 relevant scenarios"
}
```

**5. Run the pipeline with the same image**
```bash
RETRIEVER_IMAGE=krkn-retriever:fastapi ./scripts/pipeline_retrieve_only.sh "delete pods in namespace to test restart behavior" 5 3
```

If you want a rebuild on the next pipeline run:
```bash
RETRIEVER_IMAGE=krkn-retriever:fastapi RETRIEVER_FORCE_BUILD=1 ./scripts/pipeline_retrieve_only.sh "your query" 5 3
```
