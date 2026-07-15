"""Загрузка и сохранение настроек приложения (не путать с Tk .config)."""
from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from paths import get_base_dir

CONFIG_FILE = "config.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "window_geometry": "1400x850+100+100",
    "date_format": "dayfirst",
    "theme": "cosmo",
    "ksg_threshold_low": 20000,
    "ksg_threshold_high": 100000,
    "kslp_age_min": 0,
    "kslp_age_max": 4,
    "kslp_senior_age": 75,
    "kslp_operations_codes": [
        "A16.08.017.001",
        "A16.08.013.001",
        "A16.08.010.003",
    ],
    "preferred_department": "Оториноларингологическое отделение",
    "github_repo": "Dmitrii-Salikhov/Analiz_istorii",
    "check_updates_on_start": True,
}


def config_path() -> Path:
    return get_base_dir() / CONFIG_FILE


def load_config() -> dict[str, Any]:
    path = config_path()
    cfg = deepcopy(DEFAULT_CONFIG)
    if path.exists():
        try:
            with path.open("r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict):
                cfg.update(loaded)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            pass
    return cfg


def save_config(config: dict[str, Any]) -> None:
    path = config_path()
    with path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
