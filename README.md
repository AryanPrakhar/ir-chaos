# krknctl Assist

## One-Call Setup

Use this as the default end-user path. It builds the expected local image,
precomputes the FAISS assets, verifies the image provenance, builds `krknctl`
from `gpu_check`, runs an end-to-end assist check, and cleans stale assist
containers.

```bash
cd ~/ir-chaos
./scripts/setup_krknctl_assist.sh --verify
```

## Interactive Assist

Launch through the setup wrapper instead of running `krknctl` directly. The
wrapper clears old containers first and disables terminal suspend while the
interactive session is active, which avoids the `proxy already running` state
after an accidental `Ctrl+Z`.

```bash
cd ~/ir-chaos
./scripts/setup_krknctl_assist.sh --launch
```

## Minimal Commands

```bash
# Clean stale krknctl assist containers.
./scripts/setup_krknctl_assist.sh --cleanup

# Rebuild and verify from scratch.
./scripts/setup_krknctl_assist.sh --verify --force-build

# Verify one query and expected scenario.
./scripts/run_krknctl_integration_mac.sh \
  "Gimme the krknctl command to cause pod failure in namespace production but exclude any pods labeled env=dev" \
  pod-scenarios

# Start the debug and compat APIs for local retrieval work.
./scripts/pipeline.sh --verbose

# Run benchmark after the debug API is healthy at http://127.0.0.1:18080.
./scripts/benchmark.py --n 100 --fr 25 --out bench.json --clear-cache
```

If you run `krknctl` directly, run it from the checkout that contains the
built binary:

```bash
cd ~/krknctl
PATH="$PATH:/opt/homebrew/bin" ./krknctl assist run
```

If you see `bind: address already in use` for port 8080, clean up stale assist
containers first:

```bash
cd ~/ir-chaos
./scripts/setup_krknctl_assist.sh --cleanup
```

## API Endpoints

When `./scripts/pipeline.sh --verbose` is running:

- Debug API: `http://127.0.0.1:18080`
- Compat API: `http://127.0.0.1:8080`

```bash
curl -s http://127.0.0.1:18080/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query":"network latency between services","k":5,"rerank_k":3}' | jq

curl -s http://127.0.0.1:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"krkn-assist","messages":[{"role":"user","content":"network latency between services"}]}' | jq
```
