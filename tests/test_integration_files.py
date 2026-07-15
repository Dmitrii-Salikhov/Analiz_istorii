from pathlib import Path

import pytest

from excel_io import load_ksg_excel, load_lor_excel, list_departments
from ksg_analysis import analyze_ksg, load_reference
from lor_analysis import analyze_lor, filter_by_department


ROOT = Path(__file__).resolve().parents[1]


def _first_existing(*names: str) -> Path | None:
    for name in names:
        p = ROOT / name
        if p.exists():
            return p
    # also match by glob for encoded names
    for p in ROOT.glob("*.xlsx"):
        if any(key in p.name for key in names):
            return p
    return None


@pytest.mark.skipif(
    not list(ROOT.glob("*ЭМК*.xlsx")) and not list(ROOT.glob("*суммарно*.xlsx")),
    reason="нет локального ЭМК xlsx",
)
def test_real_lor_excel_pipeline():
    files = list(ROOT.glob("*суммарно*.xlsx")) + list(ROOT.glob("*ЭМК*.xlsx"))
    path = files[0]
    loaded = load_lor_excel(str(path))
    deps = list_departments(loaded.dataframe)
    assert deps
    filtered = filter_by_department(loaded.dataframe, deps[0])
    result = analyze_lor(filtered)
    assert result.total_patients >= 0


@pytest.mark.skipif(
    not list(ROOT.glob("*КСГ*.xlsx")) and not list(ROOT.glob("*Ксг*.xlsx")) and not list(ROOT.glob("*ксг*.xlsx")),
    reason="нет локального КСГ xlsx",
)
def test_real_ksg_excel_pipeline():
    files = list(ROOT.glob("*КСГ*.xlsx")) + list(ROOT.glob("*Ксг*.xlsx")) + list(ROOT.glob("*ксг*.xlsx"))
    path = files[0]
    df = load_ksg_excel(str(path))
    ref, _ = load_reference()
    result = analyze_ksg(
        df,
        ref,
        {
            "date_format": "dayfirst",
            "ksg_threshold_low": 20000,
            "ksg_threshold_high": 100000,
            "kslp_age_min": 0,
            "kslp_age_max": 4,
            "kslp_senior_age": 75,
            "kslp_operations_codes": [
                "A16.08.017.001",
                "A16.08.013.001",
                "A16.08.010.003",
            ],
        },
    )
    assert result["total_patients"] >= 0
