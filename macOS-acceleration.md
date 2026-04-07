# macOS Apple Silicon Acceleration Guide

This project can use Apple GPU acceleration on macOS through Podman machine virtualization:

- `llama.cpp` uses Vulkan in-container.
- Podman/libkrun exposes a virtual GPU at `/dev/dri`.
- Venus + MoltenVK translate Vulkan compute to Metal.

## Prerequisites

- macOS on Apple silicon (M1/M2/M3).
- Podman installed and working.
- Podman machine using `applehv`.

## 1) Prepare Podman machine

If needed, set the machine provider to `applehv`:

```bash
mkdir -p ~/.config/containers
cat > ~/.config/containers/containers.conf <<'EOF'
[machine]
provider = "applehv"
EOF
```

Start (or init + start) the machine:

```bash
podman machine init || true
podman machine start
```

Verify the VM has render nodes:

```bash
podman machine ssh "ls /dev/dri"
```

You should see entries like `card0` and `renderD128`.

## 2) Run retrieval with Vulkan backend

### Option A: GPU-accelerated (if `/dev/dri` available)

From repo root, run:

```bash
RETRIEVER_BACKEND=vulkan \
RETRIEVER_ACCELERATION=gpu \
./scripts/pipeline_retrieve_only.sh "simulate power outage across zones" 10 5
```

### Option B: CPU-only (recommended while GPU Mesa support stabilizes)

```bash
RETRIEVER_CPU_ONLY=1 \
./scripts/pipeline_retrieve_only.sh "simulate power outage across zones" 10 5
```

**Notes:**

- `RETRIEVER_BACKEND=vulkan` enables GGUF + `llama.cpp` embedding path.
- `RETRIEVER_ACCELERATION=gpu` asks for GPU runtime and falls back to CPU if unavailable.
- `RETRIEVER_CPU_ONLY=1` skips GPU probing entirely and avoids Mesa Copr build issues.
- The script auto-detects macOS and passes correct build args (`MACOS_MESA_KRUNKIT` varies by mode).
- On first run, a default GGUF embedding model is downloaded to `./models/` if missing.
- Use `RETRIEVER_FORCE_BUILD=1` to rebuild the image after Dockerfile changes.

## 3) Confirm acceleration is active

In pipeline output, look for:

- `Host OS: darwin`
- `Backend: vulkan`
- `GPU runtime flags enabled (podman-dri)`
- `Runtime flags: --device /dev/dri`

If you see `GPU runtime flags disabled`, the workflow will still run but without GPU acceleration.

## Troubleshooting

### Build fails with Copr Mesa krunkit error
If you see:
```
Error: It wasn't possible to enable this project.
Repository 'fedora-40-aarch64' does not exist in project 'slp/mesa-krunkit'.
Available repositories: 'epel-9-aarch64', 'epel-9-x86_64'
```

The Mesa krunkit Copr only supports EPEL 9. For now, use **CPU-only mode** (GPU acceleration via this path is not yet stable on macOS):

```bash
RETRIEVER_CPU_ONLY=1 ./scripts/pipeline_retrieve_only.sh "your query" 10 5
```

Alternatively, rebuild with `MACOS_MESA_KRUNKIT=0`:
```bash
RETRIEVER_FORCE_BUILD=1 \
RETRIEVER_CPU_ONLY=1 \
./scripts/pipeline_retrieve_only.sh "your query" 10 5
```

### `/dev/dri` not found in Podman VM

If you see:
```
Warning: /dev/dri not found in Podman VM — falling back to CPU
```

1. **Verify Podman machine provider is `applehv`**:
```bash
podman machine inspect | grep provider
# should output: "Provider": "applehv"
```

2. **If not applehv**, recreate the machine:
```bash
podman machine rm
podman machine init --now
```

3. **Verify render nodes are exposed**:
```bash
podman machine ssh "ls -la /dev/dri"
# should show: card0, renderD128, etc.
```

4. **Restart Podman machine**:
```bash
podman machine stop
podman machine start
```

### GPU-only fallback

If you need CPU-only without GPU:

```bash
RETRIEVER_CPU_ONLY=1 ./scripts/pipeline_retrieve_only.sh "your query" 10 5
```

### Check what's being used

From pipeline output, look for:
- ✅ `Acceleration: gpu` + `GPU runtime: podman-dri-venus` = GPU active
- ⚠️ `Acceleration: gpu` + `GPU runtime: none` = GPU unavailable, using CPU
- ✅ `Acceleration: cpu` = CPU-only (intentional)
