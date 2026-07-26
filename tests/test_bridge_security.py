"""Security-related bridge handler checks."""
from __future__ import annotations

import pytest

from bridge import handlers


def test_config_set_ignores_unknown_keys(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text("{}", encoding="utf-8")
    monkeypatch.setattr("config_store.config_path", lambda: cfg_file)
    monkeypatch.setattr(handlers, "load_config", lambda: {"theme": "slice-light"})
    saved = {}

    def fake_save(cfg):
        saved.update(cfg)

    monkeypatch.setattr(handlers, "save_config", fake_save)
    out = handlers.config_set(
        {"config": {"theme": "slice-dark", "evil_key": "x", "pending_update_from": "hack"}}
    )
    assert out["config"]["theme"] == "slice-dark"
    assert "evil_key" not in out["config"]
    assert "pending_update_from" not in out["config"] or out["config"].get("pending_update_from") != "hack"


def test_config_set_rejects_bad_github_repo(monkeypatch):
    monkeypatch.setattr(handlers, "load_config", lambda: {})
    monkeypatch.setattr(handlers, "save_config", lambda _cfg: None)
    with pytest.raises(ValueError, match="owner/repo"):
        handlers.config_set({"config": {"github_repo": "http://evil.example/x"}})


def test_assert_excel_path_rejects_non_excel(tmp_path):
    p = tmp_path / "notes.txt"
    p.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="Excel"):
        handlers._assert_excel_path(str(p))
