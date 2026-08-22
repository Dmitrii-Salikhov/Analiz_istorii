"""Тесты paths."""
from __future__ import annotations

from pathlib import Path

import paths


def test_get_base_dir_env(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ANALIZ_BASE_DIR", str(tmp_path))
    assert paths.get_base_dir() == tmp_path.resolve()


def test_get_base_dir_frozen(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("ANALIZ_BASE_DIR", raising=False)
    exe = tmp_path / "app.exe"
    exe.write_text("x", encoding="utf-8")
    monkeypatch.setattr(paths.sys, "frozen", True, raising=False)
    monkeypatch.setattr(paths.sys, "executable", str(exe))
    assert paths.get_base_dir() == tmp_path.resolve()


def test_resource_path_meipass(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ANALIZ_BASE_DIR", str(tmp_path))
    meipass = tmp_path / "_internal"
    meipass.mkdir()
    target = meipass / "icon.png"
    target.write_bytes(b"png")
    monkeypatch.setattr(paths.sys, "_MEIPASS", str(meipass), raising=False)
    assert paths.resource_path("icon.png") == target.resolve()


def test_resource_path_missing_falls_back(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("ANALIZ_BASE_DIR", str(tmp_path))
    monkeypatch.setattr(paths.sys, "_MEIPASS", None, raising=False)
    expected = tmp_path / "missing.txt"
    assert paths.resource_path("missing.txt") == expected.resolve()


def test_ensure_writable_dir(tmp_path: Path):
    nested = tmp_path / "a" / "b"
    assert paths.ensure_writable_dir(nested) == nested
    assert nested.is_dir()
