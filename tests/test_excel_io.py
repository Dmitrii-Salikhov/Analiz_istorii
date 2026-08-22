from excel_io import (
    ColumnMappingConflictError,
    MissingColumnsError,
    apply_column_aliases,
    build_rename_map,
    clean_column_name,
    detect_report_kinds,
    find_header_row,
    list_departments,
    load_excel_with_header,
    normalize_header,
    pick_default_department,
)
from report_profiles import DEFAULT_EMK_PROFILE, DEFAULT_KSG_PROFILE
import pandas as pd
import pytest


def test_clean_column_name():
    assert clean_column_name("  Номер   КВС  ") == "Номер КВС"


def test_normalize_header_number_sign():
    assert normalize_header("№ КВС") == "n квс"
    assert normalize_header("  Код   мед. услуги ") == "код мед. услуги"


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


def test_pick_default_prefers_exact_therapeutic_over_molokovo():
    """«Терапевтическое отделение» ≠ «Второе терапевтическое отделение Молоково»."""
    deps = sorted(
        [
            "Второе терапевтическое отделение Молоково",
            "Терапевтическое отделение",
            "Оториноларингологическое отделение",
        ],
        key=lambda s: s.lower(),
    )
    assert pick_default_department(deps, "Терапевтическое отделение") == (
        "Терапевтическое отделение"
    )
    assert pick_default_department(deps, "Второе терапевтическое отделение Молоково") == (
        "Второе терапевтическое отделение Молоково"
    )
    # короткий preferred — берём ближайшее по длине, не «Второе…»
    assert pick_default_department(deps, "терапевтическое") == "Терапевтическое отделение"


def test_emk_synonym_nomer_kvs():
    aliases = DEFAULT_EMK_PROFILE["aliases"]
    rename, report = build_rename_map(["№ КВС", "Лечащий врач"], aliases)
    assert rename["№ КВС"] == "Номер КВС"
    assert any(m["canonical"] == "Номер КВС" for m in report.matched)


def test_emk_optional_lab_headers_with_extra_spaces():
    aliases = DEFAULT_EMK_PROFILE["aliases"]
    rename, report = build_rename_map(
        [
            "Количество оформленных направлений на лабораторные исследования в указанном движении",
            "Количество проведенных инструментальных исследований  в указанном движении",
            "Количество оформленных  консультативных услуг в указанном движении",
            "Направления на консультации",
        ],
        aliases,
    )
    assert (
        rename["Количество оформленных направлений на лабораторные исследования в указанном движении"]
        == "Количество оформленных направлений на лабораторные исследования в указанном движении"
    )
    assert (
        rename["Количество проведенных инструментальных исследований  в указанном движении"]
        == "Количество проведенных инструментальных исследований в указанном движении"
    )
    assert (
        rename["Количество оформленных  консультативных услуг в указанном движении"]
        == "Количество оформленных консультативных услуг в указанном движении"
    )
    assert rename["Направления на консультации"] == (
        "Количество оформленных направлений на консультативные услуги в указанном движении"
    )
    canons = {m["canonical"] for m in report.matched}
    assert "Количество необходимых реанимационных дневников в указанном движении" not in canons


def test_emk_optional_emd_headers_with_quotes():
    aliases = DEFAULT_EMK_PROFILE["aliases"]
    rename, report = build_rename_map(
        [
            'Наличие ЭМД "Выписной эпикриз"',
            "Статус ЭМД Выписной эпикриз",
            "Номер ЭМД",
            "Системный ID пациента",
        ],
        aliases,
    )
    assert rename['Наличие ЭМД "Выписной эпикриз"'] == 'Наличие ЭМД "Выписной эпикриз"'
    assert rename["Статус ЭМД Выписной эпикриз"] == 'Статус ЭМД "Выписной эпикриз"'
    assert rename["Номер ЭМД"] == 'Номер ЭМД "Выписной эпикриз"'
    assert rename["Системный ID пациента"] == "Системное айди пациента"
    canons = {m["canonical"] for m in report.matched}
    assert 'Наличие ЭМД "Выписной эпикриз"' in canons


def test_ksg_synonym_kod_uslugi():
    aliases = DEFAULT_KSG_PROFILE["aliases"]
    rename, _ = build_rename_map(["Код мед. услуги", "Врач"], aliases)
    assert rename["Код мед. услуги"] == "Код услуги"


def test_column_conflict_two_to_one():
    aliases = {"Номер КВС": ["Номер КВС", "№ КВС", "КВС"]}
    with pytest.raises(ColumnMappingConflictError) as exc:
        build_rename_map(["№ КВС", "КВС"], aliases)
    assert "Номер КВС" in str(exc.value)


def test_column_conflict_prefers_exact_canonical():
    aliases = {"Отделение": ["Отделение", "Подразделение"]}
    rename, report = build_rename_map(["Подразделение", "Отделение"], aliases)
    assert rename["Отделение"] == "Отделение"
    assert "Подразделение" not in rename
    assert "Подразделение" in report.unused_headers


def test_apply_aliases_missing_required():
    df = pd.DataFrame({"№ КВС": [1], "Лишнее": [2]})
    with pytest.raises(MissingColumnsError) as exc:
        apply_column_aliases(
            df,
            DEFAULT_EMK_PROFILE["aliases"],
            ["Номер КВС", "Лечащий врач"],
        )
    assert "Лечащий врач" in exc.value.missing
    assert "Номер КВС" not in exc.value.missing


def test_custom_profile_header_fragments(tmp_path):
    path = tmp_path / "custom.xlsx"
    # header on row 1 with custom fragment words
    rows = [
        ["служебная строка", "", ""],
        ["ID случая", "Доктор", "Возраст пациента"],
        ["A1", "Иванов", "40"],
    ]
    pd.DataFrame(rows).to_excel(path, index=False, header=False)

    profile_aliases = {
        "Номер КВС": ["ID случая", "Номер КВС"],
        "Лечащий врач": ["Доктор", "Лечащий врач"],
        "Возраст на момент госпитализации в стационар": [
            "Возраст пациента",
            "Возраст на момент госпитализации в стационар",
        ],
    }
    # Minimal required set for this unit test
    required = list(profile_aliases.keys())
    # Pad other EMK required with dummy columns so load doesn't fail on missing
    # — instead use load_excel_with_header with only these required
    loaded = load_excel_with_header(
        str(path),
        required_fragments=["ID случая", "Доктор"],
        required_columns=required,
        aliases=profile_aliases,
        profile_id="custom",
        profile_name="Кастом",
    )
    assert "Номер КВС" in loaded.dataframe.columns
    assert "Лечащий врач" in loaded.dataframe.columns
    assert loaded.mapping is not None
    assert loaded.mapping.profile_id == "custom"
    assert loaded.dataframe.iloc[0]["Номер КВС"] == "A1"


def test_wrong_report_hint_ops_file_on_emk(tmp_path):
    from excel_io import HeaderNotFoundError, load_lor_excel, load_ops_excel

    path = tmp_path / "ops.xlsx"
    pd.DataFrame(
        {
            "Дата начала операции": ["01.01.2026"],
            "№ истории": ["26/1"],
            "Услуга": ["A16.08.001"],
            "Опер.стол": ["1"],
        }
    ).to_excel(path, index=False)

    assert "ops" in detect_report_kinds(str(path))
    with pytest.raises(HeaderNotFoundError) as exc:
        load_lor_excel(str(path))
    text = str(exc.value)
    assert "Похоже, загружен не тот отчёт" in text
    assert "Анализ ЭМК" in text
    assert "Операции" in text

    # correct tab still loads
    loaded = load_ops_excel(str(path))
    assert len(loaded.dataframe) == 1


def test_wrong_report_hint_unknown_file(tmp_path):
    from excel_io import HeaderNotFoundError, load_ops_excel

    path = tmp_path / "junk.xlsx"
    pd.DataFrame({"A": [1], "B": [2]}).to_excel(path, index=False)
    with pytest.raises(HeaderNotFoundError) as exc:
        load_ops_excel(str(path))
    text = str(exc.value)
    assert "Возможно, загружен не тот тип отчёта" in text
    assert "Операции" in text


def test_detect_and_load_current_patients_without_ids(tmp_path):
    from excel_io import detect_emk_variant, load_lor_excel

    path = tmp_path / "current.xlsx"
    # Title row + header + data (no «Другие связанные документы»)
    rows = [
        [None] * 5,
        ["Отчет по заполнению ЭМК в стационаре текущие", None, None, None, None],
        [
            "Номер КВС",
            "Возраст на момент госпитализации в стационар",
            "Отделение",
            "Тип госпитализации",
            "Лечащий врач",
            "Всего дней проведено в стационаре (от поступления до исхода в днях)",
            "Наличие заполненного первичного осмотра в указанном движении",
            "Наличие оформленного эпикриза в указанном движении",
            "Статус МКСБ",
            "Наличие оформленных лекарственных назначений в указанном движении",
            "Количество дневниковых записей, которое необходимо было завести в указанном движении",
            "Количество оформленных дневниковых записей в указанном движении",
            "Хир. активность (количество)",
            "Хир. активность (протоколы)",
            "Дата выписки из стационара",
            "Дата и время поступления в указанном движении",
        ],
        [
            "26/1",
            "40",
            "ЛОР",
            "Плановая",
            "Иванов И.И.",
            "-46200",
            "ДА",
            "",
            "Не подписана",
            "1",
            "2",
            "2",
            "0",
            "0",
            "01.01.1900",
            "01.08.2026 10:00:00",
        ],
    ]
    pd.DataFrame(rows).to_excel(path, index=False, header=False)
    assert detect_emk_variant(str(path)) == "current"
    loaded = load_lor_excel(str(path))
    assert loaded.emk_variant == "current"
    assert len(loaded.dataframe) == 1
