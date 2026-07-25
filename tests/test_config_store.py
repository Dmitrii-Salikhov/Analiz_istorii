"""Тесты config_store: kslp_rules и ui_prefs."""
from __future__ import annotations

from config_store import DEFAULT_CONFIG, _normalize_kslp_rules, load_config


def test_normalize_migrates_flat_codes():
    rules = _normalize_kslp_rules(
        {"kslp_operations_codes": ["A", "B"], "kslp_rules": None}
    )
    assert len(rules) == 1
    assert rules[0]["codes"] == ["A", "B"]


def test_normalize_keeps_explicit_empty_rules():
    assert _normalize_kslp_rules({"kslp_rules": []}) == []


def test_normalize_multiple_rules():
    rules = _normalize_kslp_rules(
        {
            "kslp_rules": [
                {"id": "r1", "name": "A", "codes": ["X"]},
                {"id": "r2", "name": "B", "codes": ["Y", "Z"]},
            ]
        }
    )
    assert len(rules) == 2
    assert rules[1]["codes"] == ["Y", "Z"]


def test_default_has_kslp_rules_and_ui_prefs():
    assert DEFAULT_CONFIG["kslp_rules"]
    assert DEFAULT_CONFIG["ui_prefs"]["main_tab"] == "emk"
    assert DEFAULT_CONFIG["ui_prefs"]["compare_charts"]["patients"] is True


def test_load_config_merges_ui_prefs(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.json"
    cfg_file.write_text(
        '{"last_main_tab": 1, "theme": "slice-dark"}',
        encoding="utf-8",
    )
    monkeypatch.setattr("config_store.config_path", lambda: cfg_file)
    cfg = load_config()
    assert cfg["ui_prefs"]["main_tab"] == "ksg"
    assert "compare_charts" in cfg["ui_prefs"]
    assert cfg["kslp_rules"]
