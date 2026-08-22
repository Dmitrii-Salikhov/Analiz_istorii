"""Тема интерфейса в стиле Slice: токены светлой/тёмной темы, цвета нарушений."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

# Имена тем ttkbootstrap (кастомные, регистрируются при старте)
LIGHT_THEME = "slice-light"
DARK_THEME = "slice-dark"

# Алиасы старых настроек → Slice
_THEME_ALIASES = {
    "flatly": LIGHT_THEME,
    "litera": LIGHT_THEME,
    "cosmo": LIGHT_THEME,
    "lumen": LIGHT_THEME,
    "yeti": LIGHT_THEME,
    "minty": LIGHT_THEME,
    "pulse": LIGHT_THEME,
    "sandstone": LIGHT_THEME,
    "united": LIGHT_THEME,
    "journal": LIGHT_THEME,
    "morph": LIGHT_THEME,
    "simplex": LIGHT_THEME,
    "cerculean": LIGHT_THEME,
    "darkly": DARK_THEME,
    "cyborg": DARK_THEME,
    "superhero": DARK_THEME,
    "solar": DARK_THEME,
    "vapor": DARK_THEME,
}

# Токены как в Slice / План операций (desktop/src/index.css)
SLICE_TOKENS_DARK: dict[str, str] = {
    "bg": "#0c0e12",
    "bg_elevated": "#141820",
    "bg_panel": "#10141c",
    "bg_input": "#0a0c10",
    "border": "#232a36",
    "text": "#e8ecf1",
    "text_muted": "#8b95a8",
    "accent": "#3d9cf0",
    "accent_dim": "#1a4a73",
    "danger": "#e85d5d",
    "ok": "#3ecf8e",
    "warning": "#e6a23c",
}

SLICE_TOKENS_LIGHT: dict[str, str] = {
    "bg": "#f3f5f8",
    "bg_elevated": "#ffffff",
    "bg_panel": "#eef1f5",
    "bg_input": "#ffffff",
    "border": "#cfd6e0",
    "text": "#1a2230",
    "text_muted": "#5b667a",
    "accent": "#1f6fbf",
    "accent_dim": "#d6e8f8",
    "danger": "#c62828",
    "ok": "#1b7a4a",
    "warning": "#b36b00",
}

FONT_SANS = ("Segoe UI", 10)
FONT_SANS_BOLD = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 16, "bold")
FONT_MONO = ("Consolas", 10)

VIOLATION_COLORS: dict[str, str] = {
    "Первичный осмотр": "#3d9cf0",
    "Эпикриз": "#9B7ED9",
    "МКСБ": "#e85d5d",
    "Лекарственные назначения": "#3ecf8e",
    "Дневниковые записи": "#e6a23c",
    "Лабораторные исследования": "#1abc9c",
    "Инструментальные исследования": "#5c6bc0",
    "Консультативные услуги": "#8e6bbf",
    "Реанимационные дневники": "#d35400",
    "ЭМД выписной эпикриз": "#2c7a7b",
    "ИДС": "#E67E22",
    "Длительная госпитализация": "#8b95a8",
    "Протоколы операций": "#c62828",
}

VIOLATION_TREE_TAGS_LIGHT: dict[str, str] = {
    "Первичный осмотр": "#d6e8f8",
    "Эпикриз": "#ebe4f7",
    "МКСБ": "#fadbd8",
    "Лекарственные назначения": "#d5f5e3",
    "Дневниковые записи": "#fcf3cf",
    "Лабораторные исследования": "#d5f5e8",
    "Инструментальные исследования": "#dbe0f5",
    "Консультативные услуги": "#eadff5",
    "Реанимационные дневники": "#fde5d0",
    "ЭМД выписной эпикриз": "#d4eeef",
    "ИДС": "#fdebd0",
    "Длительная госпитализация": "#e5e7e9",
    "Протоколы операций": "#f5b7b1",
}

VIOLATION_TREE_TAGS_DARK: dict[str, str] = {
    "Первичный осмотр": "#1a4a73",
    "Эпикриз": "#3a2f55",
    "МКСБ": "#5c2a2a",
    "Лекарственные назначения": "#1a4a38",
    "Дневниковые записи": "#4a3a1a",
    "Лабораторные исследования": "#1a4a40",
    "Инструментальные исследования": "#2a3355",
    "Консультативные услуги": "#3a2a50",
    "Реанимационные дневники": "#4a2a14",
    "ЭМД выписной эпикриз": "#1a3a3b",
    "ИДС": "#4a3218",
    "Длительная госпитализация": "#2a3344",
    "Протоколы операций": "#5c2020",
}

# Обратная совместимость для импортов
VIOLATION_TREE_TAGS = VIOLATION_TREE_TAGS_LIGHT

_MONTH_RU = {
    1: "январь",
    2: "февраль",
    3: "март",
    4: "апрель",
    5: "май",
    6: "июнь",
    7: "июль",
    8: "август",
    9: "сентябрь",
    10: "октябрь",
    11: "ноябрь",
    12: "декабрь",
}

_SLICE_REGISTERED = False


def normalize_theme_name(theme: str | None) -> str:
    name = (theme or LIGHT_THEME).strip().lower()
    if name in (LIGHT_THEME, DARK_THEME):
        return name
    return _THEME_ALIASES.get(name, LIGHT_THEME)


def is_dark_theme(theme: str) -> bool:
    return normalize_theme_name(theme) == DARK_THEME


def toggle_theme_name(current: str) -> str:
    return DARK_THEME if not is_dark_theme(current) else LIGHT_THEME


def tokens_for_theme(theme: str | None) -> dict[str, str]:
    return SLICE_TOKENS_DARK if is_dark_theme(theme or "") else SLICE_TOKENS_LIGHT


def violation_tree_tags_for_theme(theme: str | None) -> dict[str, str]:
    return VIOLATION_TREE_TAGS_DARK if is_dark_theme(theme or "") else VIOLATION_TREE_TAGS_LIGHT


def chart_color_for_violation(name: str) -> str:
    return VIOLATION_COLORS.get(name, "#3d9cf0")


def _bootstrap_colors_from_tokens(tokens: dict[str, str]) -> dict[str, str]:
    """Маппинг токенов Slice → палитра ttkbootstrap Colors."""
    return {
        "primary": tokens["accent"],
        "secondary": tokens["text_muted"],
        "success": tokens["ok"],
        "info": tokens["accent"],
        "warning": tokens["warning"],
        "danger": tokens["danger"],
        "light": tokens["bg_panel"],
        "dark": tokens["bg"],
        "bg": tokens["bg"],
        "fg": tokens["text"],
        "selectbg": tokens["accent_dim"],
        "selectfg": tokens["text"],
        "border": tokens["border"],
        "inputfg": tokens["text"],
        "inputbg": tokens["bg_input"],
        "active": tokens["bg_elevated"],
    }


def register_slice_themes(style=None) -> None:
    """Регистрирует slice-light / slice-dark в ttkbootstrap (один раз)."""
    global _SLICE_REGISTERED
    if _SLICE_REGISTERED:
        return
    from ttkbootstrap.style import ThemeDefinition
    import ttkbootstrap as ttkb
    import tkinter as tk

    if style is None:
        root = tk._default_root
        style = ttkb.Style(master=root) if root is not None else ttkb.Style()
    existing = set(style.theme_names())
    definitions = [
        ThemeDefinition(
            name=DARK_THEME,
            colors=_bootstrap_colors_from_tokens(SLICE_TOKENS_DARK),
            themetype="dark",
        ),
        ThemeDefinition(
            name=LIGHT_THEME,
            colors=_bootstrap_colors_from_tokens(SLICE_TOKENS_LIGHT),
            themetype="light",
        ),
    ]
    for definition in definitions:
        if definition.name not in existing:
            style.register_theme(definition)
    _SLICE_REGISTERED = True


def apply_slice_chrome(style, theme: str | None) -> None:
    """Доп. стили поверх темы: шрифты, Treeview, плотность как в Slice."""
    tokens = tokens_for_theme(theme)
    try:
        style.configure(".", font=FONT_SANS)
        style.configure("TLabel", font=FONT_SANS)
        style.configure("TButton", font=FONT_SANS)
        style.configure("Treeview", rowheight=26, font=FONT_SANS)
        style.configure("Treeview.Heading", font=FONT_SANS_BOLD)
        style.configure("TNotebook.Tab", font=FONT_SANS, padding=(12, 6))
        style.configure(
            "Slice.TFrame",
            background=tokens["bg"],
        )
        style.configure(
            "SliceElevated.TFrame",
            background=tokens["bg_elevated"],
        )
        style.configure(
            "SlicePanel.TFrame",
            background=tokens["bg_panel"],
        )
    except Exception:
        pass


def style_tk_text(widget, theme: str | None = None) -> None:
    """Оформление tk.Text / Listbox под токены Slice."""
    tokens = tokens_for_theme(theme)
    try:
        widget.configure(
            background=tokens["bg_input"],
            foreground=tokens["text"],
            insertbackground=tokens["text"],
            selectbackground=tokens["accent_dim"],
            selectforeground=tokens["text"],
            highlightbackground=tokens["border"],
            highlightcolor=tokens["accent"],
            relief="flat",
            borderwidth=1,
        )
    except Exception:
        pass


def style_matplotlib_axes(fig, ax, theme: str | None = None) -> None:
    """Фон и оси графиков под светлую/тёмную тему Slice."""
    tokens = tokens_for_theme(theme)
    try:
        fig.patch.set_facecolor(tokens["bg_elevated"])
        ax.set_facecolor(tokens["bg_elevated"])
        ax.tick_params(colors=tokens["text_muted"])
        ax.xaxis.label.set_color(tokens["text"])
        ax.yaxis.label.set_color(tokens["text"])
        ax.title.set_color(tokens["text"])
        for spine in ax.spines.values():
            spine.set_color(tokens["border"])
        for text in ax.texts:
            text.set_color(tokens["text"])
        legend = ax.get_legend()
        if legend is not None:
            legend.get_frame().set_facecolor(tokens["bg_panel"])
            legend.get_frame().set_edgecolor(tokens["border"])
            for t in legend.get_texts():
                t.set_color(tokens["text"])
    except Exception:
        pass


def short_month_label(name: str, df: pd.DataFrame | None = None) -> str:
    """Ярлык месяца для сравнения: «июнь 2026» (по графе «Выписка»)."""
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
    stem = name.rsplit(".", 1)[0] if name else "файл"
    return stem[:18]
