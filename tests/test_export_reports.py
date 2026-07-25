from __future__ import annotations

from pathlib import Path

import pandas as pd

from export_reports import export_emk_excel, export_emk_txt, export_ksg_excel, export_ksg_txt
from lor_analysis import LorAnalysisResult


def _empty_result() -> LorAnalysisResult:
    empty = pd.DataFrame(
        columns=["КВС", "возраст", "тип госпитализации", "врач", "тип_нарушения", "нарушение"]
    )
    return LorAnalysisResult(
        total_patients=0,
        avg_beddays=0.0,
        urgent=0,
        planned=0,
        age_dist=pd.Series(dtype=int),
        violations_df=empty,
        doctor_stats=pd.DataFrame(columns=["врач", "количество нарушений"]),
        ids_stats=pd.DataFrame(columns=["врач", "нарушения по ИДС"]),
        long_stay=pd.DataFrame(),
        df=pd.DataFrame(),
        skp_count=0,
        skp_days_0=0,
        skp_days_1=0,
        skp_cases=pd.DataFrame(),
        skp_operations=pd.DataFrame(),
    )


def test_export_emk_txt(tmp_path: Path):
    out = tmp_path / "emk.txt"
    path = export_emk_txt(
        out,
        _empty_result(),
        file_name="test.xlsx",
        department="ЛОР",
        sections={"Метаданные": True, "Основные показатели": True},
    )
    text = Path(path).read_text(encoding="utf-8")
    assert "Основные показатели" in text or "ОСНОВНЫЕ ПОКАЗАТЕЛИ" in text
    assert "test.xlsx" in text


def test_export_emk_excel(tmp_path: Path):
    out = tmp_path / "emk.xlsx"
    path = export_emk_excel(
        out,
        _empty_result(),
        file_name="test.xlsx",
        department="ЛОР",
    )
    assert Path(path).exists()
    assert Path(path).stat().st_size > 0


def test_export_ksg(tmp_path: Path):
    results = {
        "total_patients": 1,
        "patient_counts": pd.DataFrame({"Врач": ["Иванов"], "Количество": [1]}),
        "ops_pivot": pd.DataFrame(),
        "total_sum": 1000.0,
        "sum_by_doctor": pd.DataFrame({"Врач": ["Иванов"], "Сумма к оплате": [1000.0]}),
        "low_money": pd.DataFrame(),
        "high_money": pd.DataFrame(),
        "kslp_issues": pd.DataFrame(),
        "avg_kz_doctor": pd.DataFrame({"Врач": ["Иванов"], "КЗ": [1.0]}),
        "avg_kz_total": 1.0,
    }
    txt = export_ksg_txt(tmp_path / "ksg.txt", results, file_name="a.xlsx", settings={})
    assert Path(txt).read_text(encoding="utf-8").find("Иванов") >= 0
    xlsx = export_ksg_excel(tmp_path / "ksg.xlsx", results, file_name="a.xlsx")
    assert Path(xlsx).exists()
