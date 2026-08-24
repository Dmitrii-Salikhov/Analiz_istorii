"""Тесты проверок опержурнала."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from excel_io import load_ops_excel
from ops_analysis import (
    analyze_ops,
    duration_hours,
    extract_surgeon,
    find_long_operations,
    find_missing_or_table,
    normalize_ops_df,
    parse_op_datetime,
)


def test_parse_op_datetime_and_duration():
    start = parse_op_datetime("27.02.2026", "10:00")
    end = parse_op_datetime("27.02.2026", "14:30")
    assert start is not None and end is not None
    h = duration_hours(start, end)
    assert h == pytest.approx(4.5)


def test_duration_keeps_cross_day_errors():
    """Ошибочная дата окончания на другой день — длительность как в отчёте (для поиска ошибок)."""
    start = parse_op_datetime("11.02.2026", "12:30")
    end = parse_op_datetime("12.02.2026", "13:20")
    h = duration_hours(start, end)
    assert h == pytest.approx(24.833333, rel=1e-4)


def test_fmt_hours_hm():
    from ops_analysis import _fmt_hours

    assert _fmt_hours(0.333333) == "0:20"
    assert _fmt_hours(1.083333) == "1:05"
    assert _fmt_hours(4.5) == "4:30"
    assert _fmt_hours(24.833333) == "24:50"


def test_extract_surgeon_full_name():
    team = "Хирург Гасанов Магомед Тагирович; Операционная сестра Чекрыжова Ольга Ивановна"
    assert extract_surgeon(team) == "Гасанов Магомед Тагирович"
    assert extract_surgeon("") == "Не указан"


def test_long_ops_threshold():
    ops = pd.DataFrame(
        [
            {
                "КВС": "26/1",
                "Пациент": "Иванов",
                "Хирург": "Петров",
                "Услуга": "A16.08.001",
                "Опер.стол": "1",
                "Начало": parse_op_datetime("01.01.2026", "08:00"),
                "Конец": parse_op_datetime("01.01.2026", "13:00"),
                "Длительность_ч": 5.0,
                "Дата": parse_op_datetime("01.01.2026", "08:00"),
            },
            {
                "КВС": "26/2",
                "Пациент": "Сидоров",
                "Хирург": "Петров",
                "Услуга": "A16.08.002",
                "Опер.стол": "2",
                "Начало": parse_op_datetime("01.01.2026", "08:00"),
                "Конец": parse_op_datetime("01.01.2026", "11:00"),
                "Длительность_ч": 3.0,
                "Дата": parse_op_datetime("01.01.2026", "08:00"),
            },
            {
                "КВС": "26/3",
                "Пациент": "Козлов",
                "Хирург": "Петров",
                "Услуга": "A16.08.003",
                "Опер.стол": "3",
                "Начало": parse_op_datetime("01.01.2026", "08:00"),
                "Конец": parse_op_datetime("01.01.2026", "12:00"),
                "Длительность_ч": 4.0,
                "Дата": parse_op_datetime("01.01.2026", "08:00"),
            },
        ]
    )
    long4 = find_long_operations(ops, max_hours=4)
    assert len(long4) == 1
    assert long4[0]["КВС"] == "26/1"
    assert "длительность > 4" in long4[0]["Причина"]
    assert "Длительность_ч" not in long4[0]
    assert long4[0]["Длительность"] == "5:00"

    # cross-day → reason mentions dates
    ops2 = ops.copy()
    ops2.loc[0, "Длительность_ч"] = 24.83
    ops2.loc[0, "Начало"] = parse_op_datetime("11.02.2026", "12:30")
    ops2.loc[0, "Конец"] = parse_op_datetime("12.02.2026", "13:20")
    long_cross = find_long_operations(ops2, max_hours=4)
    assert any("даты начала и окончания различаются" in r["Причина"] for r in long_cross)

    long2 = find_long_operations(ops, max_hours=2)
    assert len(long2) == 3


def test_missing_or_table():
    ops = pd.DataFrame(
        [
            {
                "КВС": "26/9610",
                "Пациент": "ИВАНОВ",
                "Хирург": "Гасанов",
                "Услуга": "A16.08.012 - ВСКРЫТИЕ",
                "Опер.стол": "",
                "Дата": None,
                "Длительность_ч": 0.3,
            },
            {
                "КВС": "26/7331",
                "Пациент": "",
                "Хирург": "Баганов",
                "Услуга": "A16.08.002.001",
                "Опер.стол": "5 Опер.стол - ЛОР",
                "Дата": None,
                "Длительность_ч": 0.5,
            },
        ]
    )
    miss = find_missing_or_table(ops)
    assert len(miss) == 1
    assert miss[0]["КВС"] == "26/9610"
    assert miss[0]["Причина"] == "не занесена на опер.стол"


def test_analyze_ops_uses_config_threshold():
    raw = pd.DataFrame(
        {
            "Дата начала операции": ["01.01.2026"],
            "Время начала операции": ["08:00"],
            "Дата окончания операции": ["01.01.2026"],
            "Время окончания операции": ["11:00"],
            "№ истории": ["26/100"],
            "Фамилия, имя, отчество пациента": ["Тестов Т.Т."],
            "Опер.стол": ["1"],
            "Услуга": ["A16.08.001 - тест"],
            "Операционная бригада": ["Хирург Иванов Иван Иванович"],
        }
    )
    r3 = analyze_ops(raw, {"long_op_hours": 2})
    assert r3.long_count == 1
    assert r3.long_ops[0]["Хирург"] == "Иванов Иван Иванович"
    r5 = analyze_ops(raw, {"long_op_hours": 5})
    assert r5.long_count == 0


def test_ops_department_filter():
    raw = pd.DataFrame(
        {
            "Дата начала операции": ["01.01.2026", "01.01.2026", "01.01.2026"],
            "Время начала операции": ["08:00", "08:00", "08:00"],
            "Дата окончания операции": ["01.01.2026", "01.01.2026", "01.01.2026"],
            "Время окончания операции": ["13:00", "11:00", "13:00"],
            "№ истории": ["26/1", "26/2", "26/3"],
            "Услуга": ["A16.08.001", "A16.08.002", "A16.08.003"],
            "Опер.стол": ["1", "2", ""],
            "Отделение госпитализации": ["ЛОР", "Хирургия", "ЛОР"],
            "Операционная бригада": [
                "Хирург Иванов Иван Иванович",
                "Хирург Петров Пётр Петрович",
                "Хирург Иванов Иван Иванович",
            ],
        }
    )
    from ops_analysis import list_ops_departments

    deps = list_ops_departments(raw)
    assert deps == ["ЛОР", "Хирургия"]
    all_r = analyze_ops(raw, {"long_op_hours": 4})
    assert all_r.total_ops == 3
    lor = analyze_ops(raw, {"long_op_hours": 4}, department="ЛОР")
    assert lor.department == "ЛОР"
    assert lor.total_ops == 2
    assert lor.long_count == 2
    assert lor.missing_table_count == 1
    surg = analyze_ops(raw, {"long_op_hours": 4}, department="Хирургия")
    assert surg.total_ops == 1
    assert surg.long_count == 0
    assert surg.missing_table_count == 0


def test_real_ops_excel_if_present():
    path = Path("Отчет по выполненным операциям и операционным столам (19).xlsx")
    if not path.exists():
        pytest.skip("sample ops xlsx not in workspace")
    loaded = load_ops_excel(str(path))
    assert "№ истории" in loaded.dataframe.columns
    assert "Опер.стол" in loaded.dataframe.columns
    result = analyze_ops(loaded.dataframe, {"long_op_hours": 4}, file_name=path.name)
    assert result.total_ops > 0
    assert result.missing_table_count >= 1
    # error rows have required display fields
    for row in result.long_ops[:3] + result.missing_table[:3]:
        assert "КВС" in row
        assert "Хирург" in row
        assert "Услуга" in row
        assert "Причина" in row


def test_parse_op_datetime_edge_cases():
    from datetime import datetime

    from ops_analysis import _fmt_hours, _fmt_kvs, _clean_text, long_op_hours_from_config

    assert parse_op_datetime(None) is None
    assert parse_op_datetime(float("nan")) is None
    assert parse_op_datetime("nan") is None
    assert parse_op_datetime("27.02.2026 10:15:00") is not None
    assert parse_op_datetime(pd.Timestamp("2026-02-27"), "10:15") is not None
    assert parse_op_datetime(datetime(2026, 2, 27), datetime(2026, 1, 1, 11, 30)) is not None
    assert parse_op_datetime("not-a-date") is None
    assert parse_op_datetime("27.02.2026", "invalid") is not None
    assert duration_hours(None, None) is None
    assert duration_hours(pd.Timestamp("2026-01-02"), pd.Timestamp("2026-01-01")) is None
    assert _fmt_kvs(None) == ""
    assert _fmt_kvs(float("nan")) == ""
    assert _fmt_kvs("nan") == ""
    assert _fmt_hours("x") == ""
    assert _fmt_hours(-1) == ""
    assert _clean_text(None) == ""
    assert _clean_text("nan") == ""
    assert long_op_hours_from_config(None) == 4.0
    assert long_op_hours_from_config({"long_op_hours": "bad"}) == 4.0
    assert long_op_hours_from_config({"long_op_hours": 6}) == 6.0


def test_normalize_skips_blank_and_list_deps():
    from ops_analysis import list_ops_departments

    raw = pd.DataFrame(
        {
            "Дата начала операции": [None, "01.01.2026"],
            "№ истории": ["", "26/1"],
            "Услуга": ["", "A16"],
            "Опер.стол": ["", ""],
            "Отделение": ["", "ЛОР"],
        }
    )
    norm = normalize_ops_df(raw)
    assert len(norm) == 1
    assert list_ops_departments(pd.DataFrame({"x": [1]})) == []
    assert find_long_operations(None) == []
    assert find_long_operations(pd.DataFrame({"КВС": ["1"]})) == []
    assert find_missing_or_table(None) == []
    assert find_missing_or_table(pd.DataFrame()) == []


def test_long_ops_date_mismatch_and_dedupe():
    start = pd.Timestamp("2026-01-01 10:00")
    end = pd.Timestamp("2026-01-02 12:00")
    ops = pd.DataFrame(
        [
            {
                "КВС": "1",
                "Пациент": "A",
                "Хирург": "B",
                "Услуга": "A16",
                "Опер.стол": "1",
                "Отделение": "ЛОР",
                "Длительность_ч": 26.0,
                "Начало": start,
                "Конец": end,
                "Дата": start.normalize(),
            },
            {
                "КВС": "1",
                "Пациент": "A",
                "Хирург": "B",
                "Услуга": "A16",
                "Опер.стол": "1",
                "Отделение": "ЛОР",
                "Длительность_ч": 26.0,
                "Начало": start,
                "Конец": end,
                "Дата": start.normalize(),
            },
            {
                "КВС": "2",
                "Пациент": "C",
                "Хирург": "D",
                "Услуга": "A16",
                "Опер.стол": "",
                "Отделение": "ЛОР",
                "Длительность_ч": float("nan"),
                "Начало": start,
                "Конец": end,
                "Дата": start.normalize(),
            },
        ]
    )
    long = find_long_operations(ops, max_hours=4)
    assert len(long) == 1
    assert "различаются" in long[0]["Причина"]
    miss = find_missing_or_table(ops)
    assert len(miss) == 1


def test_analyze_ops_scope_all_and_multi():
    raw = pd.DataFrame(
        [
            {
                "Дата начала операции": "01.01.2026",
                "Время начала операции": "08:00",
                "Дата окончания операции": "01.01.2026",
                "Время окончания операции": "13:00",
                "№ истории": "1",
                "Фамилия, имя, отчество пациента": "A",
                "Опер.стол": "1",
                "Услуга": "A16.08.001",
                "Операционная бригада": "Хирург Иванов И.И.",
                "Отделение госпитализации": "ЛОР",
            },
            {
                "Дата начала операции": "01.01.2026",
                "Время начала операции": "09:00",
                "Дата окончания операции": "01.01.2026",
                "Время окончания операции": "10:00",
                "№ истории": "2",
                "Фамилия, имя, отчество пациента": "B",
                "Опер.стол": "",
                "Услуга": "A16.08.002",
                "Операционная бригада": "Хирург Петров П.П.",
                "Отделение госпитализации": "Хирургия",
            },
            {
                "Дата начала операции": "01.01.2026",
                "Время начала операции": "09:00",
                "Дата окончания операции": "01.01.2026",
                "Время окончания операции": "14:30",
                "№ истории": "3",
                "Фамилия, имя, отчество пациента": "C",
                "Опер.стол": "2",
                "Услуга": "A16.08.003",
                "Операционная бригада": "Хирург Сидоров С.С.",
                "Отделение госпитализации": "Хирургия",
            },
        ]
    )
    all_res = analyze_ops(raw, {"long_op_hours": 4}, scope="all")
    assert all_res.scope == "all"
    assert all_res.total_ops == 3
    assert all_res.long_count == 2
    assert all_res.missing_table_count == 1
    assert all_res.violations_summary[0]["Количество"] == 2
    assert all_res.violations_summary[1]["Количество"] == 1

    multi = analyze_ops(
        raw,
        {"long_op_hours": 4},
        scope="multi",
        departments=["Хирургия"],
    )
    assert multi.scope == "multi"
    assert multi.total_ops == 2
    assert multi.long_count == 1
    assert multi.missing_table_count == 1
    assert "Хирургия" in multi.department

    single = analyze_ops(raw, {"long_op_hours": 4}, department="ЛОР", scope="single")
    assert single.total_ops == 1
    assert single.long_count == 1
    assert single.missing_table_count == 0
