from pathlib import Path

import pytest

from excel_io import load_ksg_workbook


@pytest.mark.skipif(
    not Path("Стационар_Реестр учета МП на основе КСГ 2.xlsx").exists(),
    reason="нет общего реестра КСГ",
)
def test_load_hospital_ksg_workbook():
    path = "Стационар_Реестр учета МП на основе КСГ 2.xlsx"
    loaded = load_ksg_workbook(path)
    assert len(loaded.ksg.dataframe) > 0
    assert "Отделение" in loaded.ksg.dataframe.columns
    if loaded.other_services is not None:
        assert len(loaded.other_services.dataframe) >= 0
