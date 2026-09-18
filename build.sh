#!/usr/bin/env bash
# build.sh — Builds the .icuewidget package
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION=$(python3 -c "import json; print(json.load(open('$SCRIPT_DIR/manifest.json'))['version'])")
SUFFIX="${1:-}"
NAME="galadriel_edge_v${VERSION}${SUFFIX:+_$SUFFIX}"
OUT_DIR="$SCRIPT_DIR/dist"
mkdir -p "$OUT_DIR"
OUT="$OUT_DIR/${NAME}.icuewidget"

# Sync WIDGET_VERSION
CURRENT_JS_VERSION=$(grep -oP "const WIDGET_VERSION = '\K[^']+" "$SCRIPT_DIR/index.html")
if [ "$CURRENT_JS_VERSION" != "$VERSION" ]; then
    sed -i "s/const WIDGET_VERSION = '${CURRENT_JS_VERSION}';/const WIDGET_VERSION = '${VERSION}';/" "$SCRIPT_DIR/index.html"
    echo "Synced WIDGET_VERSION: ${CURRENT_JS_VERSION} -> ${VERSION}"
fi

echo "Building ${NAME}.icuewidget..."
cd "$SCRIPT_DIR"
zip -r "/tmp/${NAME}.icuewidget" \
    index.html \
    manifest.json \
    translation.json \
    resources/

mv "/tmp/${NAME}.icuewidget" "$OUT"
echo "✓ Successfully built: $OUT"
unzip -l "$OUT" | grep -v "^Archive\|^---\|files$"
