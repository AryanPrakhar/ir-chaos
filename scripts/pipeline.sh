#!/usr/bin/env bash
set -euo pipefail

# Backward-compatible wrapper.
# The main entrypoint lives in pipeline_retrieve_only.sh.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/pipeline_retrieve_only.sh" "$@"

