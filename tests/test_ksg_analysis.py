import pandas as pd

from ksg_analysis import (
    analyze_ksg,
    build_default_reference,
    build_month_comparison,
    ksg_period_sort_key,
    sort_ksg_files_chronologically,
)


def _ksg_row(**overrides):
    base = {
        "№ талона": "T1",
        "Врач": "Доктор А",
        "Код услуги": "A16.08.013.001",
        "Сумма к оплате": "25000",
        "Дата рождения": "01.01.1980",
        "КСЛП итоговый": "0",
        "КЗ": "1.2",
        "Поступление": "15.06.2026",
    }
    base.update(overrides)
    return base


def test_analyze_ksg_thresholds_and_totals():
    settings = {
        "date_format": "dayfirst",
        "ksg_threshold_low": 20000,
        "ksg_threshold_high": 100000,
        "kslp_age_min": 0,
        "kslp_age_max": 4,
        "kslp_senior_age": 75,
        "kslp_operations_codes": ["A16.08.017.001", "A16.08.013.001", "A16.08.010.003"],
    }
    df = pd.DataFrame(
        [
            _ksg_row(),
            _ksg_row(**{"№ талона": "T2", "Сумма к оплате": "15000"}),
            _ksg_row(**{"№ талона": "T3", "Сумма к оплате": "150000", "Врач": "Доктор Б"}),
        ]
    )
    result = analyze_ksg(df, build_default_reference(), settings)
    assert result["total_patients"] == 3
    assert len(result["low_money"]) == 1
    assert len(result["high_money"]) == 1
    assert result["total_sum"] == 190000.0


def test_kslp_child_requires_nonzero():
    settings = {
        "date_format": "dayfirst",
        "ksg_threshold_low": 20000,
        "ksg_threshold_high": 100000,
        "kslp_age_min": 0,
        "kslp_age_max": 4,
        "kslp_senior_age": 75,
        "kslp_operations_codes": ["A16.08.017.001", "A16.08.013.001", "A16.08.010.003"],
    }
    df = pd.DataFrame(
        [
            _ksg_row(
                **{
                    "Дата рождения": "01.01.2023",
                    "Поступление": "01.06.2026",
                    "КСЛП итоговый": "0",
                }
            )
        ]
    )
    result = analyze_ksg(df, build_default_reference(), settings)
    assert result["total_kslp_issues"] >= 1


def test_ksg_period_uses_vypiska_not_postuplenie():
    df = pd.DataFrame(
        {
            "Поступление": ["28.04.2026", "02.05.2026"],
            "Выписка": ["05.05.2026", "20.05.2026"],
        }
    )
    assert ksg_period_sort_key(df, "file.xlsx")[:2] == (2026, 5)


def test_short_month_label_from_vypiska():
    from gui.ui_theme import short_month_label

    df = pd.DataFrame(
        {
            "Поступление": ["25.05.2026"],
            "Выписка": ["10.06.2026"],
        }
    )
    label = short_month_label("anything.xlsx", df)
    assert "июн" in label and "2026" in label


def test_sort_ksg_files_chronologically():
    files = [
        {"name": "июнь.xlsx", "df": None, "results": {}},
        {"name": "май 2026.xlsx", "df": None, "results": {}},
        {"name": "апрель 2026.xlsx", "df": None, "results": {}},
    ]
    ordered = sort_ksg_files_chronologically(files)
    assert [f["name"] for f in ordered] == ["апрель 2026.xlsx", "май 2026.xlsx", "июнь.xlsx"]


def test_build_month_comparison_sorts_ascending():
    fake = [
        {
            "name": "июнь.xlsx",
            "df": None,
            "results": {
                "total_patients": 12,
                "total_sum": 150.0,
                "avg_kz_total": 1.2,
                "total_kslp_issues": 1,
                "doctor_sums": pd.DataFrame({"Врач": ["А", "Б"], "Сумма к оплате": [50.0, 100.0]}),
            },
        },
        {
            "name": "май.xlsx",
            "df": None,
            "results": {
                "total_patients": 10,
                "total_sum": 100.0,
                "avg_kz_total": 1.1,
                "total_kslp_issues": 2,
                "doctor_sums": pd.DataFrame({"Врач": ["А"], "Сумма к оплате": [100.0]}),
            },
        },
    ]
    cmp = build_month_comparison(fake)
    assert cmp["names"] == ["май.xlsx", "июнь.xlsx"]
    assert cmp["total_patients"] == [10, 12]
    assert "А" in cmp["doctors"] and "Б" in cmp["doctors"]
