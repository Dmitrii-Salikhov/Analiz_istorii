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


def test_emk_synonym_nomer_kvs():
    aliases = DEFAULT_EMK_PROFILE["aliases"]
    rename, report = build_rename_map(["№ КВС", "Лечащий врач"], aliases)
    assert rename["№ КВС"] == "Номер КВС"
    assert any(m["canonical"] == "Номер КВС" for m in report.matched)


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
