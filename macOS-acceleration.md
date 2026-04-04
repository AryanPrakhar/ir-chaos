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

From repo root, run:

```bash
RETRIEVER_BACKEND=vulkan \
RETRIEVER_ACCELERATION=gpu \
RETRIEVER_FORCE_BUILD=1 \
RETRIEVER_EXTRA_BUILD_ARGS='--build-arg MACOS_MESA_KRUNKIT=1' \
./scripts/pipeline_retrieve_only.sh "simulate power outage across zones" 10 5
```

Notes:

- `RETRIEVER_BACKEND=vulkan` enables GGUF + `llama.cpp` embedding path.
- `RETRIEVER_ACCELERATION=gpu` asks for GPU runtime and falls back to CPU if unavailable.
- `RETRIEVER_EXTRA_BUILD_ARGS='--build-arg MACOS_MESA_KRUNKIT=1'` enables the optional Mesa-krunkit profile in `krkn-retriever/Dockerfile` (recommended on Apple silicon Podman).
- On first run, a default GGUF embedding model is downloaded to `./models/` if missing.

## 3) Confirm acceleration is active

In pipeline output, look for:

- `Host OS: darwin`
- `Backend: vulkan`
- `GPU runtime flags enabled (podman-dri)`
- `Runtime flags: --device /dev/dri`

If you see `GPU runtime flags disabled`, the workflow will still run but without GPU acceleration.

## Troubleshooting

- If build fails with Vulkan/Mesa errors:
  - Rebuild with `RETRIEVER_FORCE_BUILD=1`.
  - Keep `MACOS_MESA_KRUNKIT=1` enabled.
- If Podman cannot expose `/dev/dri`:
  - Re-check `podman machine ssh "ls /dev/dri"`.
  - Ensure Podman machine is using `applehv`.
- If you need CPU-only fallback:

```bash
RETRIEVER_CPU_ONLY=1 ./scripts/pipeline_retrieve_only.sh "your query" 10 5
```
