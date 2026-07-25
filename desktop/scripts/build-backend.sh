#!/usr/bin/env bash
# Build Python sidecar into desktop/backend for electron-builder.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PY="${ROOT}/venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="${ROOT}/.venv/bin/python"
fi
if [[ ! -x "$PY" ]]; then
  echo "Need venv with PyInstaller: python -m pip install pyinstaller"
  exit 1
fi

"$PY" -m pip install -q pyinstaller
"$PY" -m PyInstaller desktop/analiz_backend.spec --noconfirm --clean

rm -rf desktop/backend/AnalizIstoriiBackend*
mkdir -p desktop/backend
if [[ -d dist/AnalizIstoriiBackend ]]; then
  cp -R dist/AnalizIstoriiBackend/* desktop/backend/
elif [[ -f dist/AnalizIstoriiBackend/AnalizIstoriiBackend ]]; then
  cp -R dist/AnalizIstoriiBackend/. desktop/backend/
else
  echo "PyInstaller output not found"
  exit 1
fi

# Ensure executable name for electron bridge resolver
if [[ -f desktop/backend/AnalizIstoriiBackend ]]; then
  chmod +x desktop/backend/AnalizIstoriiBackend
elif [[ -f desktop/backend/AnalizIstoriiBackend.exe ]]; then
  :
else
  # onedir layout: executable inside folder
  find desktop/backend -maxdepth 2 -type f -name 'AnalizIstoriiBackend*' -print
fi

echo "Backend ready in desktop/backend/"
