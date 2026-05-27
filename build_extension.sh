#!/bin/bash
# Package browser-only files for Chrome/Firefox (no Python/venv/__pycache__)
set -e
cd "$(dirname "$0")"

EXTENSION_FILES=(
  manifest.json
  popup.html
  popup.js
  content.js
  injected.js
  background.js
  styles.css
)

mkdir -p extension
for f in "${EXTENSION_FILES[@]}"; do
  if [ ! -f "$f" ]; then
    echo "Missing required file: $f"
    exit 1
  fi
  cp "$f" "extension/"
done

echo "Extension ready: $(pwd)/extension"
echo "Load this folder in chrome://extensions/ (not the project root)."
