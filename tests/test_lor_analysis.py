import pandas as pd

from lor_analysis import (
    analyze_lor,
    filter_by_department,
    filter_by_departments,
    format_department_scope_label,
    format_doctor_name,
    format_violations_summary_sections,
    prepare_lor_dataframe,
)


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
    # педиатрия: «Фамилия Отчество Имя», «Отчество Фамилия», «Отчество И. Фамилия»
    assert format_doctor_name("Кагерманов Хизриевна Абдула") == "Кагерманов А.Х."
    assert format_doctor_name("Хизриевна Кагерманов") == "Кагерманов Х."
    assert format_doctor_name("Хизриевна К. Кагерманов") == "Кагерманов К.Х."
    assert format_doctor_name("Кагерманов Абдула Хизриевна") == "Кагерманов А.Х."


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


def test_optional_count_metrics_detect_deficits():
    from lor_analysis import format_violations_summary_sections

    df = pd.DataFrame(
        [
            _sample_row(
                **{
                    "Номер КВС": "КВС-ok",
                    "Количество оформленных направлений на лабораторные исследования в указанном движении": "4",
                    "Количество проведенных лабораторных исследований в указанном движении": "4",
                    "Количество оформленных направлений на инструментальные методы лечения в указанном движении": "2",
                    "Количество проведенных инструментальных исследований в указанном движении": "2",
                    "Количество оформленных направлений на консультативные услуги в указанном движении": "1",
                    "Количество оформленных консультативных услуг в указанном движении": "1",
                    "Количество необходимых реанимационных дневников в указанном движении": "3",
                    "Количество оформленных реанимационных дневников в указанном движении": "3",
                }
            ),
            _sample_row(
                **{
                    "Номер КВС": "КВС-lab",
                    "Количество оформленных направлений на лабораторные исследования в указанном движении": "5",
                    "Количество проведенных лабораторных исследований в указанном движении": "2",
                    "Количество оформленных направлений на инструментальные методы лечения в указанном движении": "0",
                    "Количество проведенных инструментальных исследований в указанном движении": "0",
                    "Количество оформленных направлений на консультативные услуги в указанном движении": "0",
                    "Количество оформленных консультативных услуг в указанном движении": "0",
                    "Количество необходимых реанимационных дневников в указанном движении": "0",
                    "Количество оформленных реанимационных дневников в указанном движении": "0",
                }
            ),
            _sample_row(
                **{
                    "Номер КВС": "КВС-mix",
                    "Количество оформленных направлений на лабораторные исследования в указанном движении": "0",
                    "Количество проведенных лабораторных исследований в указанном движении": "0",
                    "Количество оформленных направлений на инструментальные методы лечения в указанном движении": "3",
                    "Количество проведенных инструментальных исследований в указанном движении": "1",
                    "Количество оформленных направлений на консультативные услуги в указанном движении": "2",
                    "Количество оформленных консультативных услуг в указанном движении": "0",
                    "Количество необходимых реанимационных дневников в указанном движении": "8",
                    "Количество оформленных реанимационных дневников в указанном движении": "3",
                }
            ),
        ]
    )
    result = analyze_lor(df)
    types = set(result.violations_df["тип_нарушения"].tolist())
    assert "Лабораторные исследования" in types
    assert "Инструментальные исследования" in types
    assert "Консультативные услуги" in types
    assert "Реанимационные дневники" in types
    ok_kvs = set(
        result.violations_df.loc[
            result.violations_df["тип_нарушения"].isin(
                {
                    "Лабораторные исследования",
                    "Инструментальные исследования",
                    "Консультативные услуги",
                    "Реанимационные дневники",
                }
            ),
            "КВС",
        ]
    )
    assert "КВС-ok" not in ok_kvs
    sections = format_violations_summary_sections(result.violations_df)
    lab = next(s for s in sections if s["id"] == "Лабораторные исследования")
    assert "КВС-lab" in lab["text"]
    assert "создано направлений: 5, выполнено исследований: 2" in lab["text"]
    cons = next(s for s in sections if s["id"] == "Консультативные услуги")
    assert "КВС-mix" in cons["text"]
    assert "направлено: 2, завершено: 0" in cons["text"]
    icu = next(s for s in sections if s["id"] == "Реанимационные дневники")
    assert "КВС-mix" in icu["text"]


def test_optional_count_metrics_skipped_when_columns_absent():
    df = pd.DataFrame([_sample_row()])
    result = analyze_lor(df)
    types = set(result.violations_df["тип_нарушения"].tolist())
    assert "Лабораторные исследования" not in types
    assert "Инструментальные исследования" not in types
    assert "Консультативные услуги" not in types
    assert "Реанимационные дневники" not in types


def test_optional_count_pair_ignored_if_incomplete():
    df = pd.DataFrame(
        [
            _sample_row(
                **{
                    "Количество оформленных направлений на лабораторные исследования в указанном движении": "9",
                }
            )
        ]
    )
    result = analyze_lor(df)
    assert "Лабораторные исследования" not in set(result.violations_df["тип_нарушения"].tolist())


def test_optional_emd_storage_flags_unsent():
    from lor_analysis import EMD_EPICRISIS_TYPE, format_violations_summary_sections

    present = 'Наличие ЭМД "Выписной эпикриз"'
    status = 'Статус ЭМД "Выписной эпикриз"'
    number = 'Номер ЭМД "Выписной эпикриз"'
    df = pd.DataFrame(
        [
            _sample_row(
                **{
                    "Номер КВС": "КВС-reg",
                    present: "ДА",
                    status: "07 Зарегистрирован",
                    number: "200.50.26.08.008579373",
                }
            ),
            _sample_row(
                **{
                    "Номер КВС": "КВС-sent",
                    present: "ДА",
                    status: "06 Отправлен",
                }
            ),
            _sample_row(
                **{
                    "Номер КВС": "КВС-form",
                    present: "ДА",
                    status: "01 Сформирован",
                }
            ),
            _sample_row(
                **{
                    "Номер КВС": "КВС-err",
                    present: "ДА",
                    status: "08 Ошибка регистрации",
                }
            ),
            _sample_row(
                **{
                    "Номер КВС": "КВС-none",
                    present: "",
                    status: "",
                }
            ),
            _sample_row(
                **{
                    "Номер КВС": "КВС-no-epi",
                    "Наличие оформленного эпикриза в указанном движении": "НЕТ",
                    present: "",
                    status: "",
                }
            ),
            _sample_row(
                **{
                    "Номер КВС": "КВС-num",
                    present: "ДА",
                    status: "",
                    number: "234.50.26.08.011139078",
                }
            ),
        ]
    )
    result = analyze_lor(df)
    emd = result.violations_df[result.violations_df["тип_нарушения"] == EMD_EPICRISIS_TYPE]
    flagged = set(emd["КВС"].astype(str))
    assert flagged == {"КВС-form", "КВС-err", "КВС-none"}
    assert "КВС-reg" not in flagged
    assert "КВС-sent" not in flagged
    assert "КВС-num" not in flagged
    assert "КВС-no-epi" not in flagged
    assert "Эпикриз" in set(
        result.violations_df.loc[result.violations_df["КВС"] == "КВС-no-epi", "тип_нарушения"]
    )
    err_text = emd.loc[emd["КВС"] == "КВС-err", "нарушение"].iloc[0]
    assert "Ошибка регистрации" in err_text
    sections = format_violations_summary_sections(result.violations_df)
    emd_sec = next(s for s in sections if s["id"] == EMD_EPICRISIS_TYPE)
    assert "КВС-form" in emd_sec["text"]
    assert "не отправлен в хранилище" in emd_sec["text"]


def test_optional_emd_skipped_when_columns_absent():
    from lor_analysis import EMD_EPICRISIS_TYPE

    result = analyze_lor(pd.DataFrame([_sample_row()]))
    assert EMD_EPICRISIS_TYPE not in set(result.violations_df["тип_нарушения"].tolist())


def test_referral_investigation_violation_text():
    from lor_analysis import format_count_deficit_violation

    assert format_count_deficit_violation("Лабораторные исследования", 3, 1, "x") == (
        "создано направлений: 3, выполнено исследований: 1"
    )
    assert format_count_deficit_violation("Инструментальные исследования", 7, 4, "x") == (
        "создано направлений: 7, выполнено исследований: 4"
    )
    assert format_count_deficit_violation("Консультативные услуги", 1, 0, "x") == (
        "направлено: 1, завершено: 0"
    )
    assert format_count_deficit_violation("Дневниковые записи", 2, 1, "Недостаточно дневников") == (
        "Недостаточно дневников: нужно 2, оформлено 1"
    )


def test_emk_info_checks_can_be_disabled():
    present = 'Наличие ЭМД "Выписной эпикриз"'
    status = 'Статус ЭМД "Выписной эпикриз"'
    df = pd.DataFrame(
        [
            _sample_row(
                **{
                    "Количество оформленных направлений на лабораторные исследования в указанном движении": "5",
                    "Количество проведенных лабораторных исследований в указанном движении": "1",
                    present: "ДА",
                    status: "01 Сформирован",
                }
            )
        ]
    )
    enabled = analyze_lor(df)
    types_on = set(enabled.violations_df["тип_нарушения"].tolist())
    assert "Лабораторные исследования" in types_on
    assert "ЭМД выписной эпикриз" in types_on

    disabled = analyze_lor(
        df,
        {
            "emk_info_checks": {
                "lab": False,
                "instr": False,
                "cons": False,
                "rean": False,
                "emd": False,
            }
        },
    )
    types_off = set(disabled.violations_df["тип_нарушения"].tolist())
    assert "Лабораторные исследования" not in types_off
    assert "ЭМД выписной эпикриз" not in types_off


def test_emk_info_checks_excluded_from_doctor_stats():
    df = pd.DataFrame(
        [
            _sample_row(
                **{
                    "Лечащий врач": "Иванов Иван Иванович",
                    "Количество оформленных направлений на лабораторные исследования в указанном движении": "5",
                    "Количество проведенных лабораторных исследований в указанном движении": "1",
                }
            )
        ]
    )
    result = analyze_lor(df)
    assert "Лабораторные исследования" in set(result.violations_df["тип_нарушения"].tolist())
    assert result.doctor_stats.empty


def test_filter_by_departments_strict():
    df = pd.DataFrame(
        [
            _sample_row(Отделение="ЛОР"),
            _sample_row(Отделение="Хирургия", **{"Номер КВС": "2"}),
            _sample_row(Отделение="Терапия", **{"Номер КВС": "3"}),
        ]
    )
    filtered = filter_by_departments(df, ["ЛОР", "Терапия"])
    assert len(filtered) == 2
    assert set(filtered["Отделение"]) == {"ЛОР", "Терапия"}


def test_analyze_multi_departments_sums_patients():
    df = pd.DataFrame(
        [
            _sample_row(Отделение="ЛОР", **{"Номер КВС": "A"}),
            _sample_row(Отделение="Хирургия", **{"Номер КВС": "B"}),
        ]
    )
    combined = filter_by_departments(df, ["ЛОР", "Хирургия"])
    result = analyze_lor(combined)
    assert result.total_patients == 2


def test_violations_summary_grouped_by_department():
    viol = pd.DataFrame(
        [
            {
                "КВС": "1",
                "возраст": 40,
                "тип госпитализации": "Плановая",
                "врач": "Иванов Иван Иванович",
                "отделение": "ЛОР",
                "тип_нарушения": "ИДС",
                "нарушение": "x",
            },
            {
                "КВС": "2",
                "возраст": 50,
                "тип госпитализации": "Плановая",
                "врач": "Петров Петр Петрович",
                "отделение": "Хирургия",
                "тип_нарушения": "ИДС",
                "нарушение": "y",
            },
        ]
    )
    sections = format_violations_summary_sections(
        viol,
        group_by_department=True,
        department_order=["ЛОР", "Хирургия"],
    )
    assert sections[0]["text"].count("[ЛОР]") == 1
    assert sections[0]["text"].count("[Хирургия]") == 1


def test_format_department_scope_label():
    assert format_department_scope_label("all", departments_total=12) == "все отделения (12)"
    assert format_department_scope_label(
        "multi",
        departments=["A", "B", "C", "D"],
        departments_total=10,
    ) == "4 отделений из 10"
    assert format_department_scope_label("multi", departments=["ЛОР", "Хирургия"]) == "ЛОР; Хирургия"
    assert format_department_scope_label("multi", departments=[]) == "выбранные отделения"
    assert format_department_scope_label("single", department="ЛОР") == "ЛОР"


def test_doctor_name_and_helpers():
    from lor_analysis import (
        age_group,
        emk_report_basename,
        extract_admission_period,
        extract_discharge_period,
        filter_by_department,
        format_doctor_name,
        format_hir_operations_short,
        is_admission_department,
        parse_hir_operations,
        violation_share_table,
    )

    assert format_doctor_name("") == "неизвестно"
    assert format_doctor_name("022201 / Салихов Дмитрий Николаевич") == "Салихов Д.Н."
    assert format_doctor_name("Д.Н. Салихов") == "Салихов Д.Н."
    assert format_doctor_name("Дмитрий Николаевич Салихов") == "Салихов Д.Н."
    assert format_doctor_name("—") == "неизвестно" or format_doctor_name("/") == "неизвестно"
    assert age_group(float("nan")) == "неизвестно"
    assert age_group(10) == "0-14 лет"
    assert age_group(16) == "15-17 лет"
    assert age_group(40) == "18-64 года"
    assert age_group(70) == "65+ лет"
    assert parse_hir_operations(None) == []
    assert parse_hir_operations("-") == []
    assert parse_hir_operations("A16.01 оп; ; B16") == [("A16.01", "оп"), ("B16", "")]
    assert format_hir_operations_short("") == "—"
    assert is_admission_department("Приёмное отделение")
    assert not is_admission_department("ЛОР")
    assert emk_report_basename(None, None).startswith("Отчет анализа ЭМК")
    from datetime import date
    from lor_analysis import EMK_VARIANT_CURRENT

    assert "текущие" in emk_report_basename(
        None, None, emk_variant=EMK_VARIANT_CURRENT, as_of=date(2026, 8, 22)
    )
    empty = pd.DataFrame()
    assert extract_discharge_period(empty) == (None, None)
    assert extract_admission_period(empty) == (None, None)
    df = pd.DataFrame({"Отделение": ["ЛОР отделение", "Терапия"]})
    assert len(filter_by_department(df, None)) == 2
    assert len(filter_by_department(df, "ЛОР")) == 1
    assert filter_by_departments(df, []).empty
    share = violation_share_table(pd.DataFrame())
    assert list(share.columns) == ["Тип нарушения", "Количество", "Доля, %"]


def test_current_patients_unique_kvs_and_rules():
    from datetime import date

    from lor_analysis import EMK_VARIANT_CURRENT, collapse_current_patients_to_unique_kvs

    df = pd.DataFrame(
        [
            _sample_row(
                **{
                    "Номер КВС": "K1",
                    "Отделение": "Приемное отделение",
                    "№ движения пациента в рамках госпитализации": "1",
                    "Дата и время поступления в указанном движении": "01.08.2026 10:00:00",
                    "Наличие заполненного первичного осмотра в указанном движении": "",
                    "Всего дней проведено в стационаре (от поступления до исхода в днях)": "-46200",
                }
            ),
            _sample_row(
                **{
                    "Номер КВС": "K1",
                    "Отделение": "Оториноларингологическое отделение",
                    "№ движения пациента в рамках госпитализации": "2",
                    "Дата и время поступления в указанном движении": "01.08.2026 12:00:00",
                    "Наличие заполненного первичного осмотра в указанном движении": "",
                    "Всего дней проведено в стационаре (от поступления до исхода в днях)": "-46200",
                }
            ),
            _sample_row(
                **{
                    "Номер КВС": "K2",
                    "Отделение": "Приемное отделение",
                    "№ движения пациента в рамках госпитализации": "1",
                    "Дата и время поступления в указанном движении": "10.08.2026 09:00:00",
                    "Наличие заполненного первичного осмотра в указанном движении": "",
                    "Всего дней проведено в стационаре (от поступления до исхода в днях)": "-46200",
                }
            ),
        ]
    )
    collapsed = collapse_current_patients_to_unique_kvs(df)
    assert len(collapsed) == 2
    assert set(collapsed["Номер КВС"]) == {"K1", "K2"}

    result = analyze_lor(
        df,
        emk_variant=EMK_VARIANT_CURRENT,
        as_of=date(2026, 8, 22),
    )
    assert result.total_patients == 2
    assert result.avg_beddays > 0
    types = set(result.violations_df["тип_нарушения"].tolist())
    assert "Эпикриз" not in types
    assert "МКСБ" not in types
    assert "ИДС" not in types
    # K1 bed dept without primary → violation; K2 only admission → no primary violation
    primary = result.violations_df[result.violations_df["тип_нарушения"] == "Первичный осмотр"]
    assert list(primary["КВС"]) == ["K1"]


def test_snils_note_on_document_violations():
    from lor_analysis import (
        SNILS_NOTE,
        cases_coverage_by_snils,
        violation_share_table_by_snils,
    )

    df = pd.DataFrame(
        [
            _sample_row(
                **{
                    "Номер КВС": "S1",
                    "Наличие СНИЛС": "ДА",
                    "Наличие заполненного первичного осмотра в указанном движении": "НЕТ",
                    "Наличие оформленного эпикриза в указанном движении": "НЕТ",
                    "Статус МКСБ": "Не подписана",
                }
            ),
            _sample_row(
                **{
                    "Номер КВС": "S2",
                    "Наличие СНИЛС": "НЕТ",
                    "Наличие заполненного первичного осмотра в указанном движении": "НЕТ",
                    "Наличие оформленного эпикриза в указанном движении": "НЕТ",
                    "Статус МКСБ": "Не подписана",
                    "Хир. активность (количество)": "2",
                    "Хир. активность (протоколы)": "1",
                }
            ),
            _sample_row(
                **{
                    "Номер КВС": "S3",
                    "Наличие СНИЛС": "НЕТ",
                    "Другие связанные документы": "нет",
                }
            ),
        ]
    )
    result = analyze_lor(df)
    assert list(result.violations_df.columns[:2]) == ["КВС", "пометка"]
    epic = result.violations_df[result.violations_df["тип_нарушения"] == "Эпикриз"]
    notes = dict(zip(epic["КВС"].astype(str), epic["пометка"].astype(str)))
    assert notes["S1"] == ""
    assert notes["S2"] == SNILS_NOTE
    ops = result.violations_df[result.violations_df["тип_нарушения"] == "Протоколы операций"]
    assert list(ops["пометка"]) == [SNILS_NOTE]
    ids = result.violations_df[result.violations_df["тип_нарушения"] == "ИДС"]
    # ИДС не помечаем
    assert all(str(x) == "" for x in ids["пометка"])

    share = violation_share_table_by_snils(result.violations_df)
    assert "С СНИЛС" in share.columns and "Без СНИЛС" in share.columns
    cov = cases_coverage_by_snils(result.df, result.violations_df)
    assert cov is not None
    assert cov["with_violations_no_snils"] >= 1
    assert cov["with_violations_snils"] >= 1


def test_snils_absent_column_no_notes():
    from lor_analysis import cases_coverage_by_snils

    df = pd.DataFrame(
        [
            _sample_row(
                **{
                    "Номер КВС": "X1",
                    "Наличие оформленного эпикриза в указанном движении": "НЕТ",
                }
            ),
        ]
    )
    result = analyze_lor(df)
    epic = result.violations_df[result.violations_df["тип_нарушения"] == "Эпикриз"]
    assert list(epic["пометка"]) == [""]
    assert cases_coverage_by_snils(result.df, result.violations_df) is None


def test_summary_bullet_includes_short_snils_note():
    from lor_analysis import SNILS_NOTE, format_violations_summary_sections

    df = pd.DataFrame(
        [
            _sample_row(
                **{
                    "Номер КВС": "26/38758",
                    "Наличие СНИЛС": "НЕТ",
                    "Наличие заполненного первичного осмотра в указанном движении": "НЕТ",
                    "Лечащий врач": "Кагерманов Абдула Хизриевна",
                }
            ),
        ]
    )
    result = analyze_lor(df)
    assert SNILS_NOTE in set(result.violations_df["пометка"])
    sections = format_violations_summary_sections(result.violations_df)
    primary = next(s for s in sections if "Первичн" in s["title"] or s["id"] == "Первичный осмотр")
    assert "26/38758 - нет СНИЛС" in primary["text"]
    assert "Врач:" in primary["text"]


def test_collapse_without_movement_and_empty_analyze():
    from datetime import date

    from lor_analysis import EMK_VARIANT_CURRENT, collapse_current_patients_to_unique_kvs

    df = pd.DataFrame(
        [
            _sample_row(
                **{
                    "Номер КВС": "K1",
                    "Отделение": "Приемное отделение",
                    "Дата и время поступления в указанном движении": "01.08.2026 10:00:00",
                }
            ),
            _sample_row(
                **{
                    "Номер КВС": "K1",
                    "Отделение": "ЛОР",
                    "Дата и время поступления в указанном движении": "01.08.2026 12:00:00",
                }
            ),
        ]
    )
    # drop movement col if present
    if "№ движения пациента в рамках госпитализации" in df.columns:
        df = df.drop(columns=["№ движения пациента в рамках госпитализации"])
    collapsed = collapse_current_patients_to_unique_kvs(df)
    assert len(collapsed) == 1
    assert collapsed.iloc[0]["Отделение"] == "ЛОР"

    empty = analyze_lor(df.iloc[0:0], emk_variant=EMK_VARIANT_CURRENT, as_of=date(2026, 8, 22))
    assert empty.total_patients == 0
    assert empty.to_dict()["total_patients"] == 0


def test_emd_and_skp_helpers():
    from lor_analysis import (
        EMD_EPICRISIS_NUMBER_COL,
        EMD_EPICRISIS_PRESENT_COL,
        EMD_EPICRISIS_STATUS_COL,
        _emd_violation_text,
        build_skp_tables,
        emd_sent_to_storage_mask,
        prepare_lor_dataframe,
    )

    row_err = pd.Series(
        {
            EMD_EPICRISIS_STATUS_COL: "Ошибка отправки",
            EMD_EPICRISIS_PRESENT_COL: "ДА",
        }
    )
    assert "Ошибка" in _emd_violation_text(row_err)
    row_st = pd.Series(
        {EMD_EPICRISIS_STATUS_COL: "Черновик", EMD_EPICRISIS_PRESENT_COL: ""}
    )
    assert "не отправлен" in _emd_violation_text(row_st).lower() or "хранилищ" in _emd_violation_text(row_st).lower()
    row_yes = pd.Series(
        {EMD_EPICRISIS_STATUS_COL: "", EMD_EPICRISIS_PRESENT_COL: "ДА"}
    )
    assert "не зарегистрирован" in _emd_violation_text(row_yes)
    row_no = pd.Series(
        {EMD_EPICRISIS_STATUS_COL: "", EMD_EPICRISIS_PRESENT_COL: ""}
    )
    assert "не отправлен" in _emd_violation_text(row_no).lower()

    df = pd.DataFrame(
        [
            {
                EMD_EPICRISIS_STATUS_COL: "Зарегистрирован",
                EMD_EPICRISIS_NUMBER_COL: "",
            },
            {
                EMD_EPICRISIS_STATUS_COL: "Ошибка отправки",
                EMD_EPICRISIS_NUMBER_COL: "123",
            },
        ]
    )
    mask = emd_sent_to_storage_mask(df)
    assert bool(mask.iloc[0]) is True
    assert bool(mask.iloc[1]) is True

    prepared = prepare_lor_dataframe(pd.DataFrame([_sample_row(**{
        "Номер КВС": "S1",
        "Всего дней проведено в стационаре (от поступления до исхода в днях)": 0,
        "Хир. активность (операции)": "A16.01 тест",
        "Хир. активность (количество)": 1,
    })]))
    cases, ops, c0, c1 = build_skp_tables(prepared)
    assert c0 + c1 >= 1
    assert not cases.empty

