"""Пути к ресурсам приложения (скрипт / frozen)."""
from __future__ import annotations

import sys
from pathlib import Path


def get_base_dir() -> Path:
    """Папка приложения: рядом с .exe (frozen) или корень проекта."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def resource_path(*parts: str) -> Path:
    """
    Ищет ресурс рядом с приложением, затем во внутреннем бандле PyInstaller (_MEIPASS).
    """
    base_candidate = get_base_dir().joinpath(*parts)
    if base_candidate.exists():
        return base_candidate
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        bundled = Path(meipass).joinpath(*parts)
        if bundled.exists():
            return bundled
    return base_candidate


def ensure_writable_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path
