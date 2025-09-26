#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="$REPO_ROOT/frontend/public/zotero"
mkdir -p "$OUTPUT_DIR/fonts" "$OUTPUT_DIR/icons"

fetch() {
  local url="$1"; local dest="$2"
  echo "Downloading $url"
  curl -fsSL "$url" -o "$dest"
}

fetch "https://www.zotero.org/static/web-library/zotero-web-library.css" "$OUTPUT_DIR/zotero-web-library.css"
fetch "https://www.zotero.org/static/web-library/zotero-web-library.js" "$OUTPUT_DIR/zotero-web-library.js"

FONT_LIST=(36AC02_5_0.eot 36AC02_5_0.svg 36AC02_5_0.ttf 36AC02_5_0.woff 36AC02_5_0.woff2)
for font in "${FONT_LIST[@]}"; do
  fetch "https://www.zotero.org/static/web-library/fonts/$font" "$OUTPUT_DIR/fonts/$font"
done

fetch "https://www.zotero.org/static/web-library/icons/zotero-logo.svg" "$OUTPUT_DIR/icons/zotero-logo.svg"
fetch "https://www.zotero.org/static/web-library/xdelta3.wasm" "$OUTPUT_DIR/xdelta3.wasm"

echo "Zotero assets downloaded to $OUTPUT_DIR"
