from gui.ui_theme import (
    DARK_THEME,
    LIGHT_THEME,
    chart_color_for_violation,
    normalize_theme_name,
    short_month_label,
    toggle_theme_name,
    tokens_for_theme,
    violation_tree_tags_for_theme,
)


def test_toggle_theme():
    assert toggle_theme_name(LIGHT_THEME) == DARK_THEME
    assert toggle_theme_name(DARK_THEME) == LIGHT_THEME
    assert toggle_theme_name("flatly") == DARK_THEME
    assert toggle_theme_name("darkly") == LIGHT_THEME


def test_normalize_theme_aliases():
    assert normalize_theme_name("flatly") == LIGHT_THEME
    assert normalize_theme_name("darkly") == DARK_THEME
    assert normalize_theme_name("slice-light") == LIGHT_THEME
    assert normalize_theme_name(None) == LIGHT_THEME


def test_tokens_and_tags():
    dark = tokens_for_theme(DARK_THEME)
    light = tokens_for_theme(LIGHT_THEME)
    assert dark["bg"] == "#0c0e12"
    assert light["bg"] == "#f3f5f8"
    assert dark["accent"] == "#3d9cf0"
    assert violation_tree_tags_for_theme(DARK_THEME)["МКСБ"].startswith("#")
    assert violation_tree_tags_for_theme(LIGHT_THEME)["МКСБ"].startswith("#")


def test_short_month_label_from_name():
    assert short_month_label("КСГ за май 2026.xlsx") == "май 2026"
    assert short_month_label("КСГ июнь 2026.xlsx") == "июнь 2026"
    assert "сентябрь" in short_month_label("отчёт сентябрь 2025.xlsx")


def test_chart_color_ids():
    assert chart_color_for_violation("ИДС").startswith("#")
    assert chart_color_for_violation("Лабораторные исследования") == "#1abc9c"
    assert chart_color_for_violation("Реанимационные дневники") == "#d35400"
    assert chart_color_for_violation("ЭМД выписной эпикриз") == "#2c7a7b"
