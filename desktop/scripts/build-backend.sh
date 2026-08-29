#!/usr/bin/env bash
# Build Python sidecar into desktop/backend for electron-builder.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$REPO"

PY=""
if [[ -n "${ANALIZ_LINUX_PYTHON:-}" ]]; then
  PY="$ANALIZ_LINUX_PYTHON"
fi
for candidate in "$PY" "$REPO/venv/bin/python" "$REPO/.venv/bin/python" \
                 "$REPO/venv/Scripts/python.exe" "$REPO/.venv/Scripts/python.exe" \
                 python3.11 python3 python; do
  [[ -z "$candidate" ]] && continue
  if [[ -x "$candidate" ]] || command -v "$candidate" >/dev/null 2>&1; then
    PY="$candidate"
    break
  fi
done
if [[ -z "$PY" ]]; then
  echo "Python not found" >&2
  exit 1
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
