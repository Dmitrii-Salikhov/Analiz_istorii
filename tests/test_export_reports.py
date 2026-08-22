from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from export_reports import (
    export_emk_excel,
    export_emk_txt,
    export_ksg_excel,
    export_ksg_txt,
    export_ops_excel,
    export_ops_txt,
)
from lor_analysis import LorAnalysisResult


def _full_result() -> LorAnalysisResult:
    viol = pd.DataFrame(
        [
            {
                "КВС": "1",
                "возраст": 40,
                "тип госпитализации": "плановая",
                "врач": "Иванов Иван Иванович",
                "тип_нарушения": "ИДС",
                "нарушение": "Отсутствует ИДС",
            },
            {
                "КВС": "2",
                "возраст": 50,
                "тип госпитализации": "экстренная",
                "врач": "Петров П.П.",
                "тип_нарушения": "Эпикриз",
                "нарушение": "Нет эпикриза",
            },
        ]
    )
    return LorAnalysisResult(
        total_patients=2,
        avg_beddays=3.5,
        urgent=1,
        planned=1,
        age_dist=pd.Series({"18-64 года": 2}),
        violations_df=viol,
        doctor_stats=pd.DataFrame(
            {"врач": ["Иванов Иван Иванович"], "количество нарушений": [1]}
        ),
        ids_stats=pd.DataFrame(
            {"врач": ["Иванов Иван Иванович"], "нарушения по ИДС": [1]}
        ),
        long_stay=pd.DataFrame(
            [
                {
                    "Номер КВС": "9",
                    "Возраст": 60,
                    "Койко-дни_скор": 12,
                    "Лечащий врач": "Сидоров С.С.",
                }
            ]
        ),
        df=pd.DataFrame(),
        period_start=date(2026, 1, 1),
        period_end=date(2026, 1, 31),
        skp_count=2,
        skp_days_0=1,
        skp_days_1=1,
        skp_cases=pd.DataFrame(
            [{"КВС": "3", "Койко-дни": 0, "Тип": "плановая", "Врач": "A", "Операции": "—", "Кол-во операций": 0}]
        ),
        skp_operations=pd.DataFrame(
            [{"Код услуги": "A16", "Наименование": "оп", "Количество случаев СКП": 1}]
        ),
    )


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


@dataclass
class _OpsResult:
    file_name: str = "ops.xlsx"
    department: str = "ЛОР"
    total_ops: int = 2
    long_op_hours: float = 4.0
    long_ops: list[dict[str, Any]] = field(default_factory=list)
    missing_table: list[dict[str, Any]] = field(default_factory=list)

    @property
    def long_count(self) -> int:
        return len(self.long_ops)

    @property
    def missing_table_count(self) -> int:
        return len(self.missing_table)


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


def test_export_emk_txt_full_sections(tmp_path: Path):
    path = export_emk_txt(
        tmp_path / "full.txt",
        _full_result(),
        file_name="full.xlsx",
        department="ЛОР",
        sections=None,
    )
    text = Path(path).read_text(encoding="utf-8")
    assert "Структура нарушений" in text
    assert "ВОЗРАСТНЫЕ ГРУППЫ" in text
    assert "НАРУШЕНИЯ" in text
    assert "СВОДКА ПО ВРАЧАМ" in text
    assert "НАРУШЕНИЯ ПО ИДС" in text
    assert "Длительные госпитализации" in text
    assert "СКП" in text
    assert "Коды услуг" in text


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


def test_export_emk_excel_full(tmp_path: Path):
    path = export_emk_excel(
        tmp_path / "full.xlsx",
        _full_result(),
        file_name="full.xlsx",
        department="ЛОР",
    )
    assert Path(path).exists()
    sheets = pd.ExcelFile(path).sheet_names
    assert "Метаданные" in sheets
    assert "Структура нарушений" in sheets
    assert "СКП истории" in sheets


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


def test_export_ksg_with_flags(tmp_path: Path):
    results = {
        "total_patients": 2,
        "patient_counts": pd.DataFrame({"Врач": ["Иванов"], "Количество": [2]}),
        "ops_pivot": pd.DataFrame({"A16": [1]}, index=["Иванов"]),
        "total_sum": 5000.0,
        "sum_by_doctor": pd.DataFrame({"Врач": ["Иванов"], "Сумма к оплате": [5000.0]}),
        "low_money": pd.DataFrame({"КВС": ["1"], "Сумма": [100]}),
        "high_money": pd.DataFrame({"КВС": ["2"], "Сумма": [9000]}),
        "kslp_issues": pd.DataFrame({"КВС": ["1"], "Проблема": ["нет КСЛП"]}),
        "avg_kz_doctor": pd.DataFrame({"Врач": ["Иванов"], "КЗ": [1.2]}),
        "avg_kz_total": 1.2,
    }
    settings = {"ksg_threshold_low": 500, "ksg_threshold_high": 8000}
    txt = Path(
        export_ksg_txt(tmp_path / "ksg2.txt", results, file_name="b.xlsx", settings=settings)
    ).read_text(encoding="utf-8")
    assert "Нарушения КСЛП" in txt
    assert "Случаи с суммой" in txt
    xlsx = export_ksg_excel(tmp_path / "ksg2.xlsx", results, file_name="b.xlsx")
    sheets = pd.ExcelFile(xlsx).sheet_names
    assert "Операции" in sheets
    assert "КСЛП нарушения" in sheets


def test_export_ops(tmp_path: Path):
    result = _OpsResult(
        long_ops=[
            {
                "КВС": "1",
                "Пациент": "A",
                "Хирург": "B",
                "Услуга": "A16",
                "Длительность": "5:00",
                "Причина": "длительность > 4 ч",
                "Опер.стол": "1",
                "Отделение": "ЛОР",
            }
        ],
        missing_table=[
            {
                "КВС": "2",
                "Пациент": "C",
                "Хирург": "D",
                "Услуга": "A16",
                "Причина": "не занесена на опер.стол",
                "Опер.стол": "",
                "Отделение": "ЛОР",
            }
        ],
    )
    txt = Path(export_ops_txt(tmp_path / "ops.txt", result, file_name="ops.xlsx")).read_text(
        encoding="utf-8"
    )
    assert "ДЛИТЕЛЬНЫЕ" in txt
    assert "БЕЗ ОПЕР.СТОЛА" in txt
    xlsx = export_ops_excel(tmp_path / "ops.xlsx", result, file_name="ops.xlsx")
    assert Path(xlsx).exists()


def test_export_ops_empty(tmp_path: Path):
    result = _OpsResult(department="", long_ops=[], missing_table=[])
    export_ops_txt(tmp_path / "empty.txt", result, file_name="x.xlsx")
    path = export_ops_excel(tmp_path / "empty.xlsx", result, file_name="x.xlsx")
    assert Path(path).exists()
