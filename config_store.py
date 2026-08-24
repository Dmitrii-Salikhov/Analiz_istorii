"""Загрузка и сохранение настроек приложения (не путать с Tk .config)."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from paths import get_base_dir

CONFIG_FILE = "config.json"
RECENT_MAX = 5

DEFAULT_CONFIG: dict[str, Any] = {
    "window_geometry": "1400x850+100+100",
    "date_format": "dayfirst",
    "theme": "slice-light",
    "ksg_threshold_low": 20000,
    "ksg_threshold_high": 100000,
    "kslp_age_min": 0,
    "kslp_age_max": 4,
    "kslp_senior_age": 75,
    "long_stay_days": 7,
    "long_op_hours": 4,
    "kslp_operations_codes": [
        "A16.08.017.001",
        "A16.08.013.001",
        "A16.08.010.003",
    ],
    "kslp_rules": [
        {
            "id": "default-ops",
            "name": "Правило 1",
            "codes": [
                "A16.08.017.001",
                "A16.08.013.001",
                "A16.08.010.003",
            ],
        }
    ],
    "preferred_department": "Оториноларингологическое отделение",
    "known_departments": [
        "Оториноларингологическое отделение",
    ],
    "github_repo": "Dmitrii-Salikhov/Analiz_istorii",
    "check_updates_on_start": True,
    "emk_display": {
        "kpi_patients": True,
        "kpi_avg_beddays": True,
        "kpi_urgent": True,
        "kpi_planned": True,
        "kpi_violations": True,
        "kpi_skp": True,
        "section_share": True,
        "section_age": True,
        "section_violations": True,
        "section_doctors": True,
        "section_skp": True,
    },
    "emk_info_checks": {
        "lab": True,
        "instr": True,
        "cons": True,
        "rean": True,
        "emd": True,
    },
    "ksg_display": {
        "kpi_patients": True,
        "kpi_sum": True,
        "kpi_kz": True,
        "kpi_no_service": True,
        "kpi_kslp": True,
        "section_doctors": True,
        "section_cases": True,
        "section_ops": True,
        "section_compare": True,
    },
    "ui_prefs": {
        "main_tab": "emk",
        "emk_sub": "share",
        "ksg_sub": "doctors",
        "ops_sub": "long",
        "compare_charts": {
            "patients": True,
            "sum": True,
            "kz": True,
            "kslp": True,
        },
        "emk_scope_mode": "single",
        "emk_summary_mode": "all",
        "emk_selected_departments": [],
        "ops_scope_mode": "single",
        "ops_summary_mode": "all",
        "ops_selected_departments": [],
    },
    "report_profiles": None,  # filled below via normalize — placeholder replaced
    "recent_emk": [],
    "recent_ksg": [],
    "recent_ops": [],
    "last_main_tab": 0,
    "last_seen_version": None,
    "pending_update_from": None,
}

# Avoid circular import at module load for DEFAULT — set after import
from report_profiles import DEFAULT_REPORT_PROFILES  # noqa: E402

DEFAULT_CONFIG["report_profiles"] = deepcopy(DEFAULT_REPORT_PROFILES)


def config_path() -> Path:
    return get_base_dir() / CONFIG_FILE


def load_config() -> dict[str, Any]:
    path = config_path()
    cfg = deepcopy(DEFAULT_CONFIG)
    loaded_data: dict[str, Any] | None = None
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                loaded_data = loaded
                cfg.update(loaded)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    cfg.setdefault("recent_emk", [])
    cfg.setdefault("recent_ksg", [])
    cfg.setdefault("recent_ops", [])
    cfg.setdefault("last_main_tab", 0)
    cfg.setdefault("last_seen_version", None)
    cfg.setdefault("pending_update_from", None)
    cfg.setdefault("long_stay_days", 7)
    cfg.setdefault("long_op_hours", 4)
    cfg.setdefault("known_departments", list(DEFAULT_CONFIG["known_departments"]))
    cfg.setdefault("emk_display", deepcopy(DEFAULT_CONFIG["emk_display"]))
    cfg.setdefault("emk_info_checks", deepcopy(DEFAULT_CONFIG["emk_info_checks"]))
    cfg.setdefault("ksg_display", deepcopy(DEFAULT_CONFIG["ksg_display"]))
    cfg.setdefault("ui_prefs", deepcopy(DEFAULT_CONFIG["ui_prefs"]))
    # merge nested display keys so old configs get new toggles
    for key in ("emk_display", "ksg_display", "emk_info_checks"):
        base = deepcopy(DEFAULT_CONFIG[key])
        nested = cfg.get(key) if isinstance(cfg.get(key), dict) else {}
        base.update(nested or {})
        cfg[key] = base
    ui_base = deepcopy(DEFAULT_CONFIG["ui_prefs"])
    ui_merged = cfg.get("ui_prefs") if isinstance(cfg.get("ui_prefs"), dict) else {}
    ui_base.update(ui_merged or {})
    charts_base = deepcopy(DEFAULT_CONFIG["ui_prefs"]["compare_charts"])
    charts_merged = (
        ui_merged.get("compare_charts")
        if isinstance(ui_merged.get("compare_charts"), dict)
        else {}
    )
    charts_base.update(charts_merged or {})
    ui_base["compare_charts"] = charts_base
    file_ui = loaded_data.get("ui_prefs") if isinstance(loaded_data, dict) else None
    if not (isinstance(file_ui, dict) and "main_tab" in file_ui):
        ui_base["main_tab"] = "ksg" if int(cfg.get("last_main_tab") or 0) == 1 else "emk"
    cfg["ui_prefs"] = ui_base
    from report_profiles import normalize_report_profiles

    cfg["report_profiles"] = normalize_report_profiles(cfg.get("report_profiles"))
    cfg["kslp_rules"] = _normalize_kslp_rules(cfg)
    # keep flat codes in sync with first rule for older UI / callers
    rules = cfg.get("kslp_rules") or []
    if rules and isinstance(rules[0], dict) and rules[0].get("codes"):
        cfg["kslp_operations_codes"] = list(rules[0]["codes"])
    try:
        from gui.ui_theme import normalize_theme_name

        cfg["theme"] = normalize_theme_name(cfg.get("theme"))
    except Exception:
        pass
    return cfg


def _normalize_kslp_rules(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Ensure kslp_rules exists; migrate from flat kslp_operations_codes if needed."""
    raw = cfg.get("kslp_rules")
    rules: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            codes = [str(c).strip() for c in (item.get("codes") or []) if str(c).strip()]
            if not codes:
                continue
            rid = str(item.get("id") or f"rule-{i + 1}")
            name = str(item.get("name") or f"Правило {i + 1}").strip() or f"Правило {i + 1}"
            rules.append({"id": rid, "name": name, "codes": codes})
        # Explicit list (even empty) wins over legacy flat codes
        if "kslp_rules" in cfg:
            return rules
    if rules:
        return rules
    legacy = cfg.get("kslp_operations_codes") or []
    codes = [str(c).strip() for c in legacy if str(c).strip()]
    if not codes:
        return deepcopy(DEFAULT_CONFIG["kslp_rules"])
    return [{"id": "migrated-ops", "name": "Правило 1", "codes": codes}]


def save_config(config: dict[str, Any]) -> None:
    path = config_path()
    from report_profiles import normalize_report_profiles

    if "report_profiles" in config:
        config["report_profiles"] = normalize_report_profiles(config.get("report_profiles"))
    config["kslp_rules"] = _normalize_kslp_rules(config)
    rules = config.get("kslp_rules") or []
    if rules and isinstance(rules[0], dict) and rules[0].get("codes"):
        config["kslp_operations_codes"] = list(rules[0]["codes"])
    with path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def push_recent_file(config: dict[str, Any], key: str, file_path: str, limit: int = RECENT_MAX) -> None:
    """Добавляет путь в начало списка недавних файлов."""
    if key not in ("recent_emk", "recent_ksg", "recent_ops"):
        return
    path = str(file_path)
    items = [p for p in list(config.get(key) or []) if p and p != path]
    items.insert(0, path)
    config[key] = items[:limit]
    save_config(config)
