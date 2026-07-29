#!/usr/bin/env bash
# Build Python sidecar into desktop/backend for electron-builder.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"

PY=""
for candidate in "$REPO/venv/bin/python" "$REPO/.venv/bin/python" \
                 "$REPO/venv/Scripts/python.exe" "$REPO/.venv/Scripts/python.exe"; do
  if [[ -x "$candidate" ]] || [[ -f "$candidate" ]]; then
    PY="$candidate"
    break
  fi
done
if [[ -z "$PY" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PY=python3
  else
    PY=python
  fi
fi

"$PY" -m pip install -q pyinstaller
"$PY" -m PyInstaller desktop/analiz_backend.spec --noconfirm --clean --distpath dist --workpath build

rm -rf desktop/backend
mkdir -p desktop/backend

if [[ -d dist/AnalizIstoriiBackend ]]; then
  cp -R dist/AnalizIstoriiBackend/. desktop/backend/
else
  echo "PyInstaller output not found at dist/AnalizIstoriiBackend"
  exit 1
fi

if [[ -f desktop/backend/AnalizIstoriiBackend ]]; then
  chmod +x desktop/backend/AnalizIstoriiBackend
fi

echo "Backend ready in desktop/backend/"
ls -la desktop/backend/ | head -20
