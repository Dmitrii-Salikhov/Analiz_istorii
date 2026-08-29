#!/usr/bin/env python3
"""Create desktop/build icons from analytics.png (Windows .ico + Linux .png)."""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "analytics.png"
OUT = Path(__file__).resolve().parents[1] / "build"
OUT.mkdir(parents=True, exist_ok=True)

img = Image.open(SRC).convert("RGBA")
img.save(
    OUT / "icon.ico",
    sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)],
)
# electron-builder linux: 512+ recommended
png = img.copy()
png.thumbnail((512, 512), Image.Resampling.LANCZOS)
png.save(OUT / "icon.png")
print("icons ->", OUT)
