#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUML_DIR="$ROOT_DIR/docs/architecture/plantuml"
OUT_DIR="$ROOT_DIR/docs/architecture/plantuml/generated"

if ! command -v plantuml >/dev/null 2>&1; then
  echo "Error: 'plantuml' is not installed. Install it with: sudo apt install plantuml" >&2
  exit 1
fi

if [ ! -d "$PUML_DIR" ]; then
  echo "Error: $PUML_DIR not found." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

echo "Rendering PlantUML diagrams..."

# Find all .puml files and render them
find "$PUML_DIR" -name "*.puml" -type f | while read -r puml_file; do
  echo "  Rendering: $(basename "$puml_file")"
  plantuml -tsvg -o "$OUT_DIR" "$puml_file"
done

echo "Done! Generated files in: $OUT_DIR"
echo ""
echo "To view: firefox $OUT_DIR/*.svg"
