Step 1

```
podman build -t krkn-retriever:v1 .
```
Step 2

```
podman run -it --rm \
  -v ./krkn-retriever:/app:Z \
  -v ./docs:/app/docs:Z \
  -v ~/.cache/huggingface:/root/.cache/huggingface:Z \
  -e DOCS_DIR=/app/docs \
  krkn-retriever:v1 bash
```
Step 3

```
python3 retriever.py index # create the index
```

Step 4

```
python3 retriever.py query -i # test interactively
```

Step 5

```
python3 retriever.py query "Simulate cluster power loss and send metrics to external collector"
```

### Benchmark

```
python3 benchmark_retriever.py --dataset data.csv --retrieve-k 10 --rerank-k 5
```


#### Just do -

```
./scripts/pipeline_retrieve_only.sh "I want to measure the downtime if a rogue script deletes all the routing objects and deployments in our tenant space." 5 3
```

