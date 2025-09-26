# shellcheck shell=bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="$REPO_ROOT/frontend/public/zotero"
TMP_DIR="$(mktemp -d)"

mkdir -p "$OUTPUT_DIR"

download_asset() {
  local url="$1"
  local dest="$2"
  echo "Downloading $url"
  curl -fsSL "$url" -o "$dest"
}

echo "Fetching pre-built Zotero Web Library assets…"

download_asset "https://www.zotero.org/static/web-library/zotero-web-library.css" \
  "$OUTPUT_DIR/zotero-web-library.css"
download_asset "https://www.zotero.org/static/web-library/zotero-web-library.js" \
  "$OUTPUT_DIR/zotero-web-library.js"

# Download fonts and icons referenced by the CSS
FONT_LIST=(
  36AC02_5_0.eot
  36AC02_5_0.svg
  36AC02_5_0.ttf
  36AC02_5_0.woff
  36AC02_5_0.woff2
)

mkdir -p "$OUTPUT_DIR/fonts"
for font in "${FONT_LIST[@]}"; do
  download_asset "https://www.zotero.org/static/web-library/fonts/$font" \
    "$OUTPUT_DIR/fonts/$font"
done

mkdir -p "$OUTPUT_DIR/icons"
download_asset "https://www.zotero.org/static/web-library/icons/zotero-logo.svg" \
  "$OUTPUT_DIR/icons/zotero-logo.svg"

download_asset "https://www.zotero.org/static/web-library/xdelta3.wasm" \
  "$OUTPUT_DIR/xdelta3.wasm"

rm -rf "$TMP_DIR"

echo "Zotero assets downloaded to $OUTPUT_DIR"
