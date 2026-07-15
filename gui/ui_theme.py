"""Тема интерфейса, цвета нарушений, ярлыки месяцев."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

LIGHT_THEME = "flatly"
DARK_THEME = "darkly"

VIOLATION_COLORS: dict[str, str] = {
    "Первичный осмотр": "#3498DB",
    "Эпикриз": "#9B59B6",
    "МКСБ": "#E74C3C",
    "Лекарственные назначения": "#1ABC9C",
    "Дневниковые записи": "#F39C12",
    "ИДС": "#E67E22",
    "Длительная госпитализация": "#7F8C8D",
    "Протоколы операций": "#C0392B",
}

VIOLATION_TREE_TAGS: dict[str, str] = {
    # ttkbootstrap tag → цвет фона (через tree.tag_configure)
    "Первичный осмотр": "#D6EAF8",
    "Эпикриз": "#E8DAEF",
    "МКСБ": "#FADBD8",
    "Лекарственные назначения": "#D5F5E3",
    "Дневниковые записи": "#FCF3CF",
    "ИДС": "#FDEBD0",
    "Длительная госпитализация": "#E5E7E9",
    "Протоколы операций": "#F5B7B1",
}

_MONTH_RU = {
    1: "янв",
    2: "фев",
    3: "мар",
    4: "апр",
    5: "май",
    6: "июн",
    7: "июл",
    8: "авг",
    9: "сен",
    10: "окт",
    11: "ноя",
    12: "дек",
}


def is_dark_theme(theme: str) -> bool:
    return (theme or "").lower() in {
        "darkly",
        "cyborg",
        "superhero",
        "solar",
        "vapor",
    }


def toggle_theme_name(current: str) -> str:
    return DARK_THEME if not is_dark_theme(current) else LIGHT_THEME


def chart_color_for_violation(name: str) -> str:
    return VIOLATION_COLORS.get(name, "#5B9BD5")


def short_month_label(name: str, df: pd.DataFrame | None = None) -> str:
    """Короткий ярлык месяца для сравнения: «май 2026» (по графе «Выписка»)."""
    if df is not None and not df.empty:
        date_col = "Выписка" if "Выписка" in df.columns else (
            "Поступление" if "Поступление" in df.columns else None
        )
        if date_col:
            dates = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce").dropna()
            if not dates.empty:
                periods = dates.dt.to_period("M")
                mode = periods.mode()
                mid = mode.iloc[0] if not mode.empty else periods.min()
                return f"{_MONTH_RU.get(int(mid.month), mid.month)} {int(mid.year)}"

    lower = (name or "").lower()
    year_m = re.search(r"(20\d{2})", lower)
    year = year_m.group(1) if year_m else ""
    month_map = [
        (1, ("январ",)),
        (2, ("феврал",)),
        (3, ("март", "марте")),
        (4, ("апрел",)),
        (5, ("май", "мая", "мае")),
        (6, ("июн",)),
        (7, ("июл",)),
        (8, ("август",)),
        (9, ("сентябр",)),
        (10, ("октябр",)),
        (11, ("ноябр",)),
        (12, ("декабр",)),
    ]
    for num, aliases in month_map:
        if any(a in lower for a in aliases):
            label = _MONTH_RU[num]
            return f"{label} {year}".strip() if year else label
    # fallback: truncate filename
    stem = name.rsplit(".", 1)[0] if name else "файл"
    return stem[:18]
