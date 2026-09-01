#!/usr/bin/env bash
# Zip linux-unpacked folder for release (portable folder, no installer).
set -euo pipefail
DESKTOP="$(cd "$(dirname "$0")/.." && pwd)"
REPO="$(cd "$DESKTOP/.." && pwd)"
OUT="$DESKTOP/release"
DIR="$OUT/linux-unpacked"
ZIP="$OUT/AnalizIstorii-linux.zip"
SHA="$OUT/AnalizIstorii-linux.zip.sha256"

if [[ ! -x "$DIR/AnalizIstorii" ]] && [[ ! -f "$DIR/AnalizIstorii" ]]; then
  echo "Missing $DIR/AnalizIstorii" >&2
  ls -la "$DIR" 2>/dev/null | head -20 || true
  exit 1
fi

chmod +x "$DIR/AnalizIstorii" 2>/dev/null || true
cp -f "$REPO/version.txt" "$DIR/version.txt"
cp -f "$REPO/KSGoperacii.csv" "$DIR/KSGoperacii.csv"

ICON_SRC="$DESKTOP/build/icon.png"
if [[ ! -f "$ICON_SRC" ]]; then
  python3 "$DESKTOP/scripts/make-icons.py"
fi
cp -f "$ICON_SRC" "$DIR/icon.png"

PORTABLE="$DESKTOP/linux-portable"
for f in start.sh AnalizIstorii.desktop install-shortcut.sh; do
  cp -f "$PORTABLE/$f" "$DIR/$f"
  chmod +x "$DIR/$f" 2>/dev/null || true
done

rm -f "$ZIP" "$SHA"
(
  cd "$DIR"
  if command -v zip >/dev/null 2>&1; then
    zip -r -q "$ZIP" .
  else
    export ZIP
    python3 - <<'PY'
import os
import zipfile
from pathlib import Path

root = Path(".")
out = Path(os.environ["ZIP"])
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
    for p in sorted(root.rglob("*")):
        if p.is_file():
            zf.write(p, p.as_posix())
PY
  fi
)

HASH="$(sha256sum "$ZIP" | awk '{print $1}')"
printf '%s  AnalizIstorii-linux.zip\n' "$HASH" > "$SHA"
echo "Created $ZIP ($HASH)"
