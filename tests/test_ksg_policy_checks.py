import pandas as pd

from ksg_analysis import analyze_ksg, build_default_reference
from ksg_policy_checks import (
    build_policy_smo_issues,
    is_missing_policy_number,
    is_missing_smo,
    policy_smo_check_available,
)


def test_policy_smo_detection_helpers():
    assert is_missing_policy_number("Number")
    assert is_missing_policy_number("")
    assert is_missing_policy_number("999999999999999") is False
    assert is_missing_smo("Code_MSK + Name_MSK")
    assert is_missing_smo("-")
    assert is_missing_smo('50005 - ООО "СМК РЕСО-МЕД"') is False


def test_build_policy_smo_issues_flags_missing_fields():
    df = pd.DataFrame(
        [
            {
                "№ талона": "T1",
                "Врач": "Иванов И.И.",
                "Номер полиса": "1234567890",
                "СМО": '50005 - ООО "СМК РЕСО-МЕД"',
            },
            {
                "№ талона": "T2",
                "Врач": "Петров П.П.",
                "Номер полиса": "",
                "СМО": '50005 - ООО "СМК РЕСО-МЕД"',
            },
            {
                "№ талона": "T3",
                "Врач": "Сидоров С.С.",
                "Номер полиса": "1234567890",
                "СМО": "-",
            },
            {
                "№ талона": "T4",
                "Врач": "Козлов К.К.",
                "Номер полиса": "",
                "СМО": "",
            },
        ]
    )
    issues = build_policy_smo_issues(df)
    assert len(issues) == 3
    assert set(issues["№ талона"]) == {"T2", "T3", "T4"}
    assert issues.loc[issues["№ талона"] == "T2", "Замечание"].iloc[0] == "Не указан номер полиса"
    assert issues.loc[issues["№ талона"] == "T3", "Замечание"].iloc[0] == "Не указана СМО"
    assert (
        issues.loc[issues["№ талона"] == "T4", "Замечание"].iloc[0]
        == "Не указаны номер полиса и СМО"
    )


def test_analyze_ksg_policy_check_optional():
    df = pd.DataFrame(
        [
            {
                "№ талона": "T1",
                "Врач": "Доктор А",
                "Код услуги": "A16.08.013.001",
                "Сумма к оплате": "25000",
                "Дата рождения": "01.01.1980",
                "КСЛП итоговый": "0",
                "КЗ": "1.2",
                "Поступление": "15.06.2026",
                "Номер полиса": "",
                "СМО": "50005 - СМО",
            }
        ]
    )
    settings = {
        "date_format": "dayfirst",
        "ksg_threshold_low": 20000,
        "ksg_threshold_high": 100000,
        "kslp_age_min": 0,
        "kslp_age_max": 4,
        "kslp_senior_age": 75,
        "kslp_operations_codes": [],
    }
    off = analyze_ksg(df, build_default_reference(), settings)
    assert off["policy_check_available"] is True
    assert off["policy_check_enabled"] is False
    assert off["total_policy_issues"] == 0

    on = analyze_ksg(df, build_default_reference(), {**settings, "ksg_check_policy_smo": True})
    assert on["policy_check_enabled"] is True
    assert on["total_policy_issues"] == 1
    assert on["other_violations"]["Полис / СМО"] == 1


def test_policy_smo_check_available_requires_columns():
    assert policy_smo_check_available(pd.DataFrame({"№ талона": ["1"]})) is False
    assert policy_smo_check_available(
        pd.DataFrame({"№ талона": ["1"], "Номер полиса": ["1"], "СМО": ["x"]})
    )


def test_build_policy_smo_issues_includes_optional_columns():
    df = pd.DataFrame(
        [
            {
                "№ талона": "T5",
                "ФИО пациента": "Иванов Иван Иванович",
                "Врач": "Иванов И.И.",
                "Отделение": "ЛОР",
                "Номер полиса": "",
                "СМО": "50005 - СМО",
            }
        ]
    )
    issues = build_policy_smo_issues(df)
    assert len(issues) == 1
    assert issues.iloc[0]["ФИО пациента"] == "Иванов И.И."
    assert issues.iloc[0]["Отделение"] == "ЛОР"
    assert is_missing_smo("нет") is True
