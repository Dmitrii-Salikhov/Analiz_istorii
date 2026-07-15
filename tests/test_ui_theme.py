from gui.ui_theme import short_month_label, toggle_theme_name, chart_color_for_violation


def test_toggle_theme():
    assert toggle_theme_name("flatly") == "darkly"
    assert toggle_theme_name("darkly") == "flatly"


def test_short_month_label_from_name():
    assert "май" in short_month_label("КСГ за май 2026.xlsx")
    assert "2026" in short_month_label("КСГ за май 2026.xlsx")


def test_chart_color_ids():
    assert chart_color_for_violation("ИДС").startswith("#")
