import pandas as pd

from ksg_departments import (
    filter_ksg_dataframe,
    is_lor_department,
    list_ksg_departments,
    normalize_ksg_departments,
    parse_ksg_department,
    pick_default_ksg_department,
)
from ksg_analysis import filter_ksg_by_period, list_ksg_periods


def test_parse_ksg_department_empty_and_plain():
    assert parse_ksg_department("") == (None, "", "")
    assert parse_ksg_department(None) == (None, "", "")
    code, name, original = parse_ksg_department("Терапия")
    assert code is None
    assert name == "Терапия"
    assert original == "Терапия"


def test_is_lor_department_by_name_and_code():
    assert is_lor_department("Оториноларингologическое отделение")
    assert is_lor_department("Хирургия", "009")
    assert not is_lor_department("Терапия", "011")


def test_normalize_ksg_departments_edge_cases():
    assert normalize_ksg_departments(None).empty
    assert normalize_ksg_departments(pd.DataFrame({"x": [1]})).equals(pd.DataFrame({"x": [1]}))


def test_pick_default_ksg_department():
    df = normalize_ksg_departments(
        pd.DataFrame(
            {
                "Отделение": ["009 / Оториноларингologическое отделение", "011 / Педиатрия"],
                "№ талона": ["1", "2"],
            }
        )
    )
    depts = list_ksg_departments(df)
    assert pick_default_ksg_department([], df) is None
    assert pick_default_ksg_department(depts, df) == depts[0]
    assert pick_default_ksg_department(depts, df, preferred="педиатр") == depts[1]
    assert pick_default_ksg_department(depts, df, preferred=depts[1]) == depts[1]


def test_filter_ksg_multi_and_empty_department():
    df = normalize_ksg_departments(
        pd.DataFrame(
            {
                "Отделение": ["009 / ЛОР", "011 / Педиатрия", "012 / Терапия"],
                "№ талона": ["1", "2", "3"],
            }
        )
    )
    depts = list_ksg_departments(df)
    filtered, active = filter_ksg_dataframe(df, "multi", "", [depts[0], depts[2]])
    assert len(filtered) == 2
    assert active == [depts[0], depts[2]]

    empty, active2 = filter_ksg_dataframe(df, "multi", "", [])
    assert empty.empty
    assert active2 == []

    single, active3 = filter_ksg_dataframe(df, "single", "", [])
    assert len(single) == 1
    assert active3 == [depts[0]]


def test_parse_ksg_department_strips_code():
    code, name, original = parse_ksg_department("009 / Оториноларингologическое отделение")
    assert code == "009"
    assert "Оторинолар" in name
    assert original.startswith("009")


def test_filter_ksg_by_scope_all():
    df = pd.DataFrame(
        {
            "Отделение": ["009 / ЛОР", "011 / Педиатрия"],
            "№ талона": ["1", "2"],
        }
    )
    normalized = normalize_ksg_departments(df)
    filtered, deps = filter_ksg_dataframe(normalized, "all", "", [])
    assert len(filtered) == 2
    assert len(deps) == 2


def test_filter_ksg_by_single_department():
    df = normalize_ksg_departments(
        pd.DataFrame(
            {
                "Отделение": ["009 / Оториноларингologическое отделение", "011 / Педиатрия"],
                "№ талона": ["1", "2"],
            }
        )
    )
    lor_name = list_ksg_departments(df)[0]
    filtered, active = filter_ksg_dataframe(df, "single", lor_name, [])
    assert len(filtered) == 1
    assert active == [lor_name]


def test_list_ksg_periods_and_filter():
    df = pd.DataFrame(
        {
            "Выписка": ["10.08.2026", "22.07.2026"],
            "№ талона": ["1", "2"],
        }
    )
    periods = list_ksg_periods(df)
    assert len(periods) == 2
    only_aug = filter_ksg_by_period(df, "2026-08")
    assert len(only_aug) == 1
