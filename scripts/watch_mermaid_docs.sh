#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCH_DIR="$ROOT_DIR/docs/architecture"

if [ ! -d "$ARCH_DIR" ]; then
  echo "Error: $ARCH_DIR not found. Nothing to watch." >&2
  exit 1
fi

if ! command -v entr >/dev/null 2>&1; then
  cat >&2 <<'EOF'
Error: 'entr' is not installed.

On Debian/Ubuntu/Kali you can install it with:
  sudo apt install entr

Then re-run:
  bash scripts/watch_mermaid_docs.sh
EOF
  exit 1
fi

find "$ARCH_DIR" -maxdepth 1 -name '*.md' | entr -r bash "$ROOT_DIR/scripts/render_mermaid_docs.sh"
