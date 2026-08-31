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


def test_low_high_money_include_service_column():
    settings = {
        "date_format": "dayfirst",
        "ksg_threshold_low": 20000,
        "ksg_threshold_high": 100000,
        "kslp_age_min": 0,
        "kslp_age_max": 4,
        "kslp_senior_age": 75,
        "kslp_operations_codes": [],
    }
    ref = build_default_reference()
    df = pd.DataFrame(
        [
            _ksg_row(**{"№ талона": "T-low", "Сумма к оплате": "15000", "Код услуги": "A16.08.013.001"}),
            _ksg_row(
                **{
                    "№ талона": "T-high",
                    "Сумма к оплате": "150000",
                    "Код услуги": "",
                }
            ),
        ]
    )
    result = analyze_ksg(df, ref, settings)
    assert "Услуга" in result["low_money"].columns
    low_svc = result["low_money"].iloc[0]["Услуга"]
    assert "A16.08.013.001" in str(low_svc)
    assert "Услуга отсутствует" not in str(low_svc)
    assert result["high_money"].iloc[0]["Услуга"] == "Услуга отсутствует"


def test_format_ksg_case_frame_always_has_service_column():
    from ksg_analysis import _format_ksg_case_frame

    frame = _format_ksg_case_frame(
        pd.DataFrame(
            [
                {
                    "№ талона": "T1",
                    "Врач": "Иванов Иван Иванович",
                    "Сумма к оплате": 1000,
                }
            ]
        )
    )
    assert "Услуга" in frame.columns
    assert frame.iloc[0]["Услуга"] == "Услуга отсутствует"


def test_analyze_ksg_includes_patient_fio_in_case_tables():
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
            _ksg_row(
                **{
                    "№ талона": "T-low",
                    "Сумма к оплате": "15000",
                    "ФИО пациента": "Петров Пётр Петрович",
                }
            ),
            _ksg_row(
                **{
                    "№ талона": "T-kslp",
                    "ФИО пациента": "Сидорова Анна Сергеевна",
                    "Дата рождения": "01.01.2023",
                    "Поступление": "01.06.2026",
                    "КСЛП итоговый": "0",
                }
            ),
        ]
    )
    result = analyze_ksg(df, build_default_reference(), settings)
    assert "ФИО пациента" in result["low_money"].columns
    assert result["low_money"].iloc[0]["ФИО пациента"] == "Петров П.П."
    assert "ФИО пациента" in result["kslp_issues"].columns
    assert result["kslp_issues"].iloc[0]["ФИО пациента"] == "Сидорова А.С."


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


def test_kslp_rule_all_codes_require_nonzero():
    settings = {
        "date_format": "dayfirst",
        "ksg_threshold_low": 20000,
        "ksg_threshold_high": 100000,
        "kslp_age_min": 0,
        "kslp_age_max": 4,
        "kslp_senior_age": 75,
        "kslp_rules": [
            {
                "id": "r1",
                "name": "Тройка",
                "codes": ["A16.08.017.001", "A16.08.013.001", "A16.08.010.003"],
            }
        ],
    }
    codes = "A16.08.017.001 A16.08.013.001 A16.08.010.003"
    df = pd.DataFrame(
        [
            _ksg_row(**{"Код услуги": codes, "КСЛП итоговый": "0"}),
            _ksg_row(**{"№ талона": "T2", "Код услуги": "A16.08.017.001", "КСЛП итоговый": "0"}),
        ]
    )
    result = analyze_ksg(df, build_default_reference(), settings)
    assert result["total_kslp_issues"] == 1
    assert "Тройка" in result["kslp_issues"].iloc[0]["Замечание"]


def test_kslp_any_of_two_rules_matches():
    settings = {
        "date_format": "dayfirst",
        "ksg_threshold_low": 20000,
        "ksg_threshold_high": 100000,
        "kslp_age_min": 0,
        "kslp_age_max": 4,
        "kslp_senior_age": 75,
        "kslp_rules": [
            {"id": "r1", "name": "Правило A", "codes": ["A16.08.017.001", "A16.08.013.001"]},
            {"id": "r2", "name": "Правило B", "codes": ["A16.08.010.003"]},
        ],
    }
    df = pd.DataFrame(
        [
            _ksg_row(**{"Код услуги": "A16.08.010.003", "КСЛП итоговый": "0"}),
        ]
    )
    result = analyze_ksg(df, build_default_reference(), settings)
    assert result["total_kslp_issues"] == 1
    assert "Правило B" in result["kslp_issues"].iloc[0]["Замечание"]


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


def test_analyze_ksg_with_department_uses_profile():
    from ksg_kslp_profiles import BUILTIN_LOR

    settings = {
        "date_format": "dayfirst",
        "ksg_threshold_low": 20000,
        "ksg_threshold_high": 100000,
        "ksg_department_profiles": {"Терапевтия": "standard", "ЛОР": BUILTIN_LOR},
        "ksg_kslp_profiles": {
            BUILTIN_LOR: {
                "id": BUILTIN_LOR,
                "mode": "rules",
                "rules": [{"id": "r1", "name": "Ops", "codes": ["A16.08.010.003"]}],
                "age_min": 0,
                "age_max": 4,
                "senior_age": 75,
            },
            "standard": {"id": "standard", "mode": "age_only", "age_min": 0, "age_max": 4, "senior_age": 75, "rules": []},
        },
    }
    df = pd.DataFrame(
        [
            _ksg_row(**{"Отделение": "ЛОР", "Код услуги": "A16.08.010.003", "КСЛП итоговый": "0"}),
            _ksg_row(**{"№ талона": "T2", "Отделение": "Терапевтия", "Код услуги": "A16.08.010.003", "КСЛП итоговый": "0"}),
        ]
    )
    result = analyze_ksg(df, build_default_reference(), settings)
    assert result["total_kslp_issues"] == 1
    assert not result["by_department"].empty


def test_build_department_comparison():
    from ksg_analysis import build_department_comparison

    item = {
        "df_ksg": pd.DataFrame(
            [
                _ksg_row(**{"Отделение": "ЛОР", "№ талона": "A"}),
                _ksg_row(**{"Отделение": "Терапевтия", "№ талона": "B", "Врач": "Доктор Б"}),
            ]
        ),
        "departments": ["ЛОР", "Терапевтия"],
    }
    settings = {"date_format": "dayfirst", "ksg_threshold_low": 20000, "ksg_threshold_high": 100000}
    summary = build_department_comparison(
        item,
        departments=["ЛОР", "Терапевтия"],
        period="all",
        source="ksg",
        reference=build_default_reference(),
        settings=settings,
    )
    assert len(summary["labels"]) == 2
    assert sum(summary["total_patients"]) == 2

    """Сравнение выбранных файлов (как indices в ksg.compare)."""
    fake = [
        {
            "name": "апрель.xlsx",
            "label": "апр 2026",
            "df": None,
            "results": {
                "total_patients": 8,
                "total_sum": 80.0,
                "avg_kz_total": 1.0,
                "total_kslp_issues": 0,
                "doctor_sums": pd.DataFrame({"Врач": ["А"], "Сумма к оплате": [80.0]}),
            },
        },
        {
            "name": "май.xlsx",
            "label": "май 2026",
            "df": None,
            "results": {
                "total_patients": 10,
                "total_sum": 100.0,
                "avg_kz_total": 1.1,
                "total_kslp_issues": 1,
                "doctor_sums": pd.DataFrame({"Врач": ["А"], "Сумма к оплате": [100.0]}),
            },
        },
        {
            "name": "июнь.xlsx",
            "label": "июн 2026",
            "df": None,
            "results": {
                "total_patients": 12,
                "total_sum": 150.0,
                "avg_kz_total": 1.2,
                "total_kslp_issues": 2,
                "doctor_sums": pd.DataFrame({"Врач": ["А"], "Сумма к оплате": [150.0]}),
            },
        },
    ]
    # как UI: indices [0, 2] → апрель + июнь
    selected = [fake[0], fake[2]]
    cmp = build_month_comparison(selected)
    assert cmp["names"] == ["апрель.xlsx", "июнь.xlsx"]
    assert cmp["total_patients"] == [8, 12]
    assert cmp["doctor_sums"]["А"] == [80.0, 150.0]
