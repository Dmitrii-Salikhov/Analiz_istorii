#!/usr/bin/env bash
# Portable launcher (no root / chrome-sandbox SUID required).
cd "$(dirname "$0")"
exec ./AnalizIstorii --no-sandbox "$@"
