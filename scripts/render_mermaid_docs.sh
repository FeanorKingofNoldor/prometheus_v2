#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Tell Puppeteer/mermaid-cli to use this repo as its browser cache directory,
# so it can find the chrome-headless-shell we installed here.
export PUPPETEER_CACHE_DIR="$ROOT_DIR"
ARCH_DIR="$ROOT_DIR/docs/architecture"
OUT_DIR="$ARCH_DIR/generated"

if ! command -v mmdc >/dev/null 2>&1; then
  echo "Error: 'mmdc' (mermaid-cli) is not in PATH. Install it with: npm install -g @mermaid-js/mermaid-cli" >&2
  exit 1
fi

if [ ! -d "$ARCH_DIR" ]; then
  echo "Error: $ARCH_DIR not found. Nothing to render." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

processed=0
for doc in "$ARCH_DIR"/*.md; do
  if [ ! -e "$doc" ]; then
    echo "No Markdown docs found in $ARCH_DIR" >&2
    exit 0
  fi

  if ! grep -q '```mermaid' "$doc"; then
    continue
  fi

  base="$(basename "$doc")"
  out_md="$OUT_DIR/$base"
  artefacts_dir="$OUT_DIR/${base%.md}_assets"

  echo "Rendering $doc -> $out_md (assets: $artefacts_dir)"
  mmdc -i "$doc" -o "$out_md" -a "$artefacts_dir"
  processed=$((processed + 1))
done

if [ "$processed" -eq 0 ]; then
  echo "No Mermaid code blocks found in $ARCH_DIR/*.md" >&2
else
  echo "Rendered $processed Markdown file(s) with Mermaid diagrams."
fi
