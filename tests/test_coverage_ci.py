"""Добор покрытия для CI (без локальных xlsx из integration-тестов)."""
from __future__ import annotations

import pandas as pd
import pytest

from excel_io import MissingColumnsError, load_ksg_excel
from ksg_analysis import _age_group, analyze_ksg, build_default_reference, load_reference
from lor_analysis import (
    SNILS_COL,
    SNILS_NOTE,
    cases_coverage_by_snils,
    cases_coverage_lists,
    extract_discharge_period,
)
from ops_analysis import analyze_ops, filter_ops_by_departments, normalize_ops_df, ops_violations_summary
from paths import get_base_dir, resource_path


def test_load_reference_csv_ok_and_missing(tmp_path):
    csv = tmp_path / "KSG.csv"
    csv.write_text(
        "Код;Название;КСГ\nA16.01;Операция;st20.001,st20.002\n;пусто;\n",
        encoding="utf-8",
    )
    ref, status = load_reference(csv)
    assert ref["A16.01"][0] == "Операция"
    assert ref["A16.01"][1] == "st20.001"
    assert "загружен" in status

    missing, status2 = load_reference(tmp_path / "нет.csv")
    assert missing == build_default_reference() or len(missing) > 0
    assert "встроенный" in status2


def test_load_reference_read_error(tmp_path, monkeypatch):
    bad = tmp_path / "bad.csv"
    bad.write_text("x;y;z\n1;2;3\n", encoding="utf-8")

    def boom(*_a, **_k):
        raise OSError("cannot read")

    monkeypatch.setattr(pd, "read_csv", boom)
    ref, status = load_reference(bad)
    assert "ошибка" in status.lower()
    assert ref


def test_age_group_branches():
    assert _age_group(float("nan")) == "неизвестно"
    assert _age_group(10) == "0-14 лет"
    assert _age_group(16) == "15-17 лет"
    assert _age_group(40) == "18-64 года"
    assert _age_group(80) == "65+ лет"


def test_analyze_ksg_covers_unknown_code():
    settings = {
        "date_format": "dayfirst",
        "ksg_threshold_low": 20000,
        "ksg_threshold_high": 100000,
        "kslp_age_min": 0,
        "kslp_age_max": 4,
        "kslp_senior_age": 75,
        "kslp_operations_codes": [],
    }
    df = pd.DataFrame(
        [
            {
                "№ талона": "T1",
                "Врач": "A",
                "Код услуги": "UNKNOWN.CODE",
                "Сумма к оплате": "30000",
                "Дата рождения": "01.01.2010",
                "КСЛП итоговый": "0",
                "КЗ": "1",
                "Поступление": "01.06.2026",
            },
        ]
    )
    result = analyze_ksg(df, build_default_reference(), settings)
    assert result["total_patients"] == 1
    assert "UNKNOWN.CODE" in (result.get("unknown_codes") or [])


def test_cases_coverage_lists_and_snils_empty_violations():
    prepared = pd.DataFrame(
        [
            {"Номер КВС": "1", "Лечащий врач": "Иванов", SNILS_COL: "ДА"},
            {"Номер КВС": "1", "Лечащий врач": "Иванов", SNILS_COL: "ДА"},
            {"Номер КВС": "2", "Лечащий врач": "Петров", SNILS_COL: "НЕТ"},
            {"Номер КВС": "3", "Лечащий врач": "Сидоров", SNILS_COL: "ДА"},
        ]
    )
    empty = cases_coverage_lists(pd.DataFrame(), None)
    assert empty["with_violations"] == []
    lists = cases_coverage_lists(prepared, None)
    assert len(lists["without_violations"]) == 3
    assert lists["with_violations"] == []
    note_row = next(r for r in lists["without_violations"] if r["КВС"] == "2")
    assert note_row["пометка"] == SNILS_NOTE

    viol = pd.DataFrame([{"КВС": "2", "тип_нарушения": "Эпикриз"}])
    lists2 = cases_coverage_lists(prepared, viol)
    assert {r["КВС"] for r in lists2["with_violations"]} == {"2"}
    assert lists2["with_violations"][0]["нарушений"] == 1

    cov = cases_coverage_by_snils(prepared, None)
    assert cov is not None
    assert cov["without_violations_snils"] == 2
    assert cov["without_violations_no_snils"] == 1
    assert len(cov["lists"]["without_violations_snils"]) == 2


def test_extract_discharge_period_placeholders():
    df = pd.DataFrame({"Дата выписки из стационара": ["01.01.1900", "01.01.1900"]})
    assert extract_discharge_period(df) == (None, None)
    df2 = pd.DataFrame({"Дата выписки из стационара": ["15.03.2026", "20.03.2026"]})
    start, end = extract_discharge_period(df2)
    assert start is not None and end is not None
    assert start.year == 2026


def test_resource_path_and_base_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("ANALIZ_BASE_DIR", str(tmp_path))
    assert get_base_dir() == tmp_path.resolve()
    f = tmp_path / "res.txt"
    f.write_text("ok", encoding="utf-8")
    assert resource_path("res.txt") == f.resolve()

    missing = resource_path("нет_такого.txt")
    assert missing.name == "нет_такого.txt"

    meipass = tmp_path / "bundle"
    meipass.mkdir()
    bundled = meipass / "bundled.txt"
    bundled.write_text("b", encoding="utf-8")
    monkeypatch.setattr("paths.sys", type("S", (), {"_MEIPASS": str(meipass), "frozen": False, "executable": ""})())
    # resource_path checks get_base_dir first — clear env so base misses, then MEIPASS hits
    monkeypatch.delenv("ANALIZ_BASE_DIR", raising=False)
    # get_base_dir without env returns project root; force missing local then MEIPASS
    monkeypatch.setattr("paths.get_base_dir", lambda: tmp_path / "empty_base")
    assert resource_path("bundled.txt") == bundled


def test_ops_filter_and_violations_summary_and_scope_errors():
    ops = normalize_ops_df(
        pd.DataFrame(
            [
                {
                    "Дата начала операции": "01.01.2026",
                    "Время начала операции": "08:00",
                    "Дата окончания операции": "01.01.2026",
                    "Время окончания операции": "13:00",
                    "№ истории": "1",
                    "Услуга": "A16",
                    "Опер.стол": "1",
                    "Отделение госпитализации": "ЛОР",
                }
            ]
        )
    )
    empty = filter_ops_by_departments(ops, [])
    assert empty.empty
    assert ops_violations_summary(long_count=2, missing_table_count=1, long_op_hours=4)[0]["Количество"] == 2

    with pytest.raises(ValueError, match="хотя бы одно"):
        analyze_ops(ops, scope="multi", departments=[])
    with pytest.raises(ValueError, match="Нет данных"):
        analyze_ops(
            pd.DataFrame(
                [
                    {
                        "Дата начала операции": "01.01.2026",
                        "№ истории": "1",
                        "Услуга": "A16",
                        "Опер.стол": "1",
                        "Отделение госпитализации": "ЛОР",
                    }
                ]
            ),
            scope="multi",
            departments=["НетТакого"],
        )


def test_load_ksg_requires_dates(tmp_path):
    # Minimal sheet without Поступление/Выписка → MissingColumnsError via after_load
    path = tmp_path / "ksg_bad.xlsx"
    # Build a workbook that looks like KSG headers but without date cols
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.append(["Отчёт КСГ по законченным случаям"])
    ws.append([])
    ws.append(["№ талона", "Врач", "Код услуги", "Сумма к оплате", "Дата рождения", "КСЛП итоговый", "КЗ"])
    ws.append(["1", "A", "A16.08.001", "1000", "01.01.1980", "0", "1"])
    wb.save(path)
    with pytest.raises(MissingColumnsError):
        load_ksg_excel(str(path))
