````md id="0ljnhh"
Start the server:

```bash
./scripts/pipeline.sh --verbose
````

This also opens interactive mode and starts the API on:

```
http://127.0.0.1:8080
```

Query from another terminal:

```bash
curl -s http://127.0.0.1:8080/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query":"network latency between services"}' \
| jq
```

Health check:

```
curl http://127.0.0.1:8080/health | jq
```
