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
    assert format_doctor_name("Петров Пётр Сидорович") == "Петров П. С."
    assert format_doctor_name("") == "неизвестно"


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
