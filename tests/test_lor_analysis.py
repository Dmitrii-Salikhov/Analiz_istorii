import pandas as pd

from lor_analysis import analyze_lor, filter_by_department, format_doctor_name, prepare_lor_dataframe


def _sample_row(**overrides):
    base = {
        "Отделение": "Оториноларингологическое отделение",
        "Номер КВС": "КВС-1",
        "Возраст на момент госпитализации в стационар": "40",
        "Тип госпитализации": "Плановая",
        "Всего дней проведено в стационаре (от поступления до исхода в днях)": "3",
        "Лечащий врач": "Иванов Иван Иванович",
        "Наличие заполненного первичного осмотра в указанном движении": "ДА",
        "Наличие оформленного эпикриза в указанном движении": "ДА",
        "Статус МКСБ": "Подписана",
        "Наличие оформленных лекарственных назначений в указанном движении": "1",
        "Количество дневниковых записей, которое необходимо было завести в указанном движении": "2",
        "Количество оформленных дневниковых записей в указанном движении": "2",
        "Другие связанные документы": "83 - Информированное добровольное согласие",
        "Хир. активность (количество)": "0",
        "Хир. активность (протоколы)": "0",
    }
    base.update(overrides)
    return base


def test_format_doctor_name():
    assert format_doctor_name("Петров Пётр Сидорович") == "Петров П.С."
    assert format_doctor_name("Салихов Дмитрий Александрович") == "Салихов Д.А."
    assert format_doctor_name("Салихов Д.А.") == "Салихов Д.А."
    assert format_doctor_name("Салихов Д. А.") == "Салихов Д.А."
    assert format_doctor_name("САЛИХОВ ДМИТРИЙ АЛЕКСАНДРОВИЧ") == "САЛИХОВ Д.А."
    # табельный номер + Имя Отчество Фамилия (как в выгрузке КСГ)
    assert format_doctor_name("022201 Дмитрий Николаевич Салихов") == "Салихов Д.Н."
    assert format_doctor_name("022201 Д.Н. Салихов") == "Салихов Д.Н."
    assert format_doctor_name("022201 Салихов Дмитрий Николаевич") == "Салихов Д.Н."
    assert format_doctor_name("022201 / Белов Дмитрий Геннадьевич") == "Белов Д.Г."
    assert format_doctor_name("022201/ Белов Дмитрий Геннадьевич") == "Белов Д.Г."
    assert format_doctor_name("") == "неизвестно"


def test_emk_report_basename_and_shares():
    from datetime import date

    from lor_analysis import emk_report_basename, violation_share_table

    assert "01.06.2026" in emk_report_basename(date(2026, 6, 1), date(2026, 6, 30))
    assert emk_report_basename(None, None) == "Отчет анализа ЭМК"

    viol = pd.DataFrame(
        {
            "тип_нарушения": ["ИДС", "ИДС", "Эпикриз"],
        }
    )
    share = violation_share_table(viol)
    assert list(share["Тип нарушения"]) == ["ИДС", "Эпикриз"]
    assert share.loc[0, "Доля, %"] == 66.7


def test_analyze_detects_ids_and_primary():
    df = pd.DataFrame(
        [
            _sample_row(),
            _sample_row(
                **{
                    "Номер КВС": "КВС-2",
                    "Наличие заполненного первичного осмотра в указанном движении": "НЕТ",
                    "Другие связанные документы": "нет",
                }
            ),
        ]
    )
    result = analyze_lor(df)
    assert result.total_patients == 2
    types = set(result.violations_df["тип_нарушения"].tolist())
    assert "Первичный осмотр" in types
    assert "ИДС" in types


def test_skp_counts_and_operations():
    from lor_analysis import parse_hir_operations

    assert parse_hir_operations(
        "A16.01.004 Обработка;A16.18.007 Колостомия"
    ) == [("A16.01.004", "Обработка"), ("A16.18.007", "Колостомия")]

    df = pd.DataFrame(
        [
            _sample_row(
                **{
                    "Номер КВС": "КВС-0",
                    "Всего дней проведено в стационаре (от поступления до исхода в днях)": "0",
                    "Хир. активность (операции)": "A16.01.004 Обработка раны",
                    "Хир. активность (количество)": "1",
                }
            ),
            _sample_row(
                **{
                    "Номер КВС": "КВС-1d",
                    "Всего дней проведено в стационаре (от поступления до исхода в днях)": "1",
                }
            ),
            _sample_row(
                **{
                    "Номер КВС": "КВС-3",
                    "Всего дней проведено в стационаре (от поступления до исхода в днях)": "3",
                }
            ),
        ]
    )
    result = analyze_lor(df)
    assert result.skp_days_0 == 1
    assert result.skp_days_1 == 1
    assert result.skp_count == 2
    assert len(result.skp_cases) == 2
    assert "A16.01.004" in result.skp_operations["Код услуги"].tolist()
    assert int(result.skp_operations.iloc[0]["Количество случаев СКП"]) == 1


def test_filter_by_department_exact():
    df = pd.DataFrame(
        [
            _sample_row(Отделение="ЛОР"),
            _sample_row(Отделение="Хирургия", **{"Номер КВС": "2"}),
        ]
    )
    filtered = filter_by_department(df, "ЛОР")
    assert len(filtered) == 1
    assert prepare_lor_dataframe(filtered)["Возраст"].iloc[0] == 40


def test_long_stay_threshold_and_summary():
    from lor_analysis import format_violations_summary_sections

    df = pd.DataFrame(
        [
            _sample_row(
                **{
                    "Номер КВС": "КВС-L",
                    "Всего дней проведено в стационаре (от поступления до исхода в днях)": "10",
                }
            ),
        ]
    )
    default = analyze_lor(df)
    assert "Длительная госпитализация" in set(default.violations_df["тип_нарушения"])

    strict = analyze_lor(df, {"long_stay_days": 15})
    assert "Длительная госпитализация" not in set(strict.violations_df["тип_нарушения"].tolist())

    sections = format_violations_summary_sections(default.violations_df, long_stay_days=7)
    assert sections
    assert any("КВС-L" in s["text"] for s in sections)

