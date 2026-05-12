#!/usr/bin/env bash
set -euo pipefail

# Backward-compatible wrapper.
# The main entrypoint lives in pipeline_assist.sh.

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec "$SCRIPT_DIR/pipeline_assist.sh" "$@"
