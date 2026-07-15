from excel_io import (
    MissingColumnsError,
    clean_column_name,
    find_header_row,
    list_departments,
    pick_default_department,
)
import pandas as pd


def test_clean_column_name():
    assert clean_column_name("  Номер   КВС  ") == "Номер КВС"


def test_find_header_row():
    raw = pd.DataFrame(
        [
            ["мусор", "x"],
            ["Номер КВС", "Возраст на момент госпитализации"],
            ["1", "40"],
        ]
    )
    assert find_header_row(raw, ["Номер КВС", "Возраст на момент госпитализации"]) == 1
    assert find_header_row(raw, ["такого нет"]) is None


def test_missing_columns_error_message():
    err = MissingColumnsError(["А", "Б"], found=["X", "Y"])
    text = str(err)
    assert "А" in text and "Б" in text
    assert "X" in text


def test_departments_helpers():
    df = pd.DataFrame(
        {
            "Отделение": [
                "Хирургическое отделение",
                "Оториноларингологическое отделение",
                "Хирургическое отделение",
                "",
            ]
        }
    )
    deps = list_departments(df)
    assert "Оториноларингологическое отделение" in deps
    assert pick_default_department(deps, "Оториноларингологическое") == (
        "Оториноларингологическое отделение"
    )
    assert pick_default_department([], None) is None
