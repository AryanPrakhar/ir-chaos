#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  exec "$SCRIPT_DIR/setup_krknctl_assist.sh" --help
fi

DEFAULT_QUERY="how do i run a pod deletion scenario"
QUERY="${1:-$DEFAULT_QUERY}"
EXPECTED="${2:-}"
if [[ -z "$EXPECTED" && "$QUERY" == "$DEFAULT_QUERY" ]]; then
  EXPECTED="pod-scenarios"
fi

exec "$SCRIPT_DIR/setup_krknctl_assist.sh" \
  --verify \
  --query "$QUERY" \
  --expect "$EXPECTED"
