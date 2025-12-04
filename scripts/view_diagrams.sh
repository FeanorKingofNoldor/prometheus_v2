#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GEN_DIR="$ROOT_DIR/docs/architecture/generated"

if [ ! -d "$GEN_DIR" ]; then
  echo "Error: No generated diagrams found. Run 'bash scripts/render_mermaid_docs.sh' first." >&2
  exit 1
fi

# Find all generated markdown files with embedded SVGs
MD_FILES=($(find "$GEN_DIR" -maxdepth 1 -name "*.md" | sort))

if [ ${#MD_FILES[@]} -eq 0 ]; then
  echo "No generated markdown files found in $GEN_DIR" >&2
  exit 1
fi

echo "Opening generated architecture diagrams in browser..."
for md_file in "${MD_FILES[@]}"; do
  echo "  - $(basename "$md_file")"
done

# Open all generated markdown files in Firefox (which renders SVGs properly)
firefox "${MD_FILES[@]}" 2>/dev/null &

echo "Done! Check your browser."
