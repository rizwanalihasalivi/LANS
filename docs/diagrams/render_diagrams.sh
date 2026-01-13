#!/usr/bin/env bash
# Render Mermaid diagrams to PNG and SVG using mmdc (mermaid-cli)
# Install: npm i -g @mermaid-js/mermaid-cli

set -e
mkdir -p docs/diagrams/out
for f in docs/diagrams/*.mmd; do
  name=$(basename "$f" .mmd)
  mmdc -i "$f" -o "docs/diagrams/out/${name}.png" || echo "PNG render failed for $f"
  mmdc -i "$f" -o "docs/diagrams/out/${name}.svg" || echo "SVG render failed for $f"
done
