#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  cat <<EOF
Usage:
  $0
  $0 "query text" expected-scenario

Examples:
  $0
  $0 "network latency between services" network-chaos
  $0 "Gimme the krknctl command to cause pod failure in namespace production but exclude any pods labeled env=dev" pod-scenarios
EOF
  exit 0
fi

if [[ "$#" -gt 2 ]]; then
  echo "Error: query must be quoted as one argument." >&2
  echo "Example: $0 \"Gimme the krknctl command to cause pod failure in namespace production\" pod-scenarios" >&2
  exit 2
fi

DEFAULT_QUERY="how do i run a pod deletion scenario"
QUERY="${1:-$DEFAULT_QUERY}"
EXPECTED="${2:-}"
if [[ -z "$EXPECTED" ]]; then
  if [[ "$QUERY" == "$DEFAULT_QUERY" ]]; then
    EXPECTED="pod-scenarios"
  else
    echo "Error: expected scenario is required for custom verification queries." >&2
    echo "Example: $0 \"$QUERY\" pod-scenarios" >&2
    exit 2
  fi
fi

exec "$SCRIPT_DIR/setup_krknctl_assist.sh" \
  --verify \
  --query "$QUERY" \
  --expect "$EXPECTED"
