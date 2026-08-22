"""Тесты профилей отчётов."""
from __future__ import annotations

from report_profiles import get_active_profile, normalize_report_profiles


def test_normalize_non_dict_returns_defaults():
    result = normalize_report_profiles(None)
    assert result["emk_active"] == "default"
    assert "default" in result["emk"]


def test_normalize_merges_custom_profile_and_active():
    raw = {
        "emk_active": "custom",
        "emk": {
            "default": {
                "name": "Базовый",
                "header_fragments": ["КВС"],
                "required_columns": ["Номер КВС"],
                "aliases": {"Номер КВС": ["КВС"]},
            },
            "custom": {
                "name": "Свой",
                "header_fragments": ["история"],
                "aliases": {"Номер КВС": ["№ КВС"], "bad": "skip"},
            },
            "skip_me": "not-a-dict",
        },
        "ksg_active": "missing",
    }
    result = normalize_report_profiles(raw)
    assert result["emk_active"] == "custom"
    assert result["ksg_active"] == "default"
    assert result["emk"]["custom"]["name"] == "Свой"
    assert "№ КВС" in result["emk"]["custom"]["aliases"]["Номер КВС"]


def test_get_active_profile():
    cfg = {"report_profiles": {"emk_active": "default"}}
    prof = get_active_profile(cfg, "emk")
    assert "required_columns" in prof or "header_fragments" in prof
