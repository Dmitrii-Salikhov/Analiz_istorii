"""Чистый анализ отчёта по заполнению ЭМК (без UI)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


def format_doctor_name(full_name) -> str:
    if pd.isna(full_name) or full_name == "":
        return "неизвестно"
    parts = str(full_name).strip().split()
    if not parts:
        return "неизвестно"
    last = parts[0]
    initials = []
    for part in parts[1:]:
        if part and part[0].isalpha():
            initials.append(part[0].upper() + ".")
    if initials:
        return f"{last} {' '.join(initials)}"
    return last


def _has_ids(doc_str) -> bool:
    if pd.isna(doc_str):
        return False
    text = str(doc_str)
    return (
        "83 - Информированное добровольное согласие" in text
        or "ИДС" in text
        or "Информированное добровольное согласие" in text
    )


def age_group(age) -> str:
    if pd.isna(age):
        return "неизвестно"
    if age <= 14:
        return "0-14 лет"
    if age <= 17:
        return "15-17 лет"
    if age <= 64:
        return "18-64 года"
    return "65+ лет"


def prepare_lor_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["Возраст"] = pd.to_numeric(
        out["Возраст на момент госпитализации в стационар"], errors="coerce"
    )
    out["Койко-дни"] = pd.to_numeric(
        out["Всего дней проведено в стационаре (от поступления до исхода в днях)"],
        errors="coerce",
    )
    out["Койко-дни_скор"] = out["Койко-дни"].apply(lambda x: 1 if pd.isna(x) or x == 0 else x)
    out["Хир_кол"] = (
        pd.to_numeric(out["Хир. активность (количество)"], errors="coerce").fillna(0).astype(int)
    )
    out["Хир_прот"] = (
        pd.to_numeric(out["Хир. активность (протоколы)"], errors="coerce").fillna(0).astype(int)
    )
    out["Лекарства"] = pd.to_numeric(
        out["Наличие оформленных лекарственных назначений в указанном движении"],
        errors="coerce",
    ).fillna(0)
    out["Дневники_необх"] = pd.to_numeric(
        out["Количество дневниковых записей, которое необходимо было завести в указанном движении"],
        errors="coerce",
    ).fillna(0)
    out["Дневники_факт"] = pd.to_numeric(
        out["Количество оформленных дневниковых записей в указанном движении"],
        errors="coerce",
    ).fillna(0)
    return out


def filter_by_department(df: pd.DataFrame, department: str | None) -> pd.DataFrame:
    if not department:
        return df.copy()
    mask = df["Отделение"].astype(str).str.contains(department, na=False, case=False, regex=False)
    # Exact match preferred when possible
    exact = df["Отделение"].astype(str).str.strip() == department.strip()
    if exact.any():
        return df[exact].copy()
    return df[mask].copy()


@dataclass
class LorAnalysisResult:
    total_patients: int
    avg_beddays: float
    urgent: int
    planned: int
    age_dist: pd.Series
    violations_df: pd.DataFrame
    doctor_stats: pd.DataFrame
    ids_stats: pd.DataFrame
    long_stay: pd.DataFrame
    df: pd.DataFrame

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_patients": self.total_patients,
            "avg_beddays": self.avg_beddays,
            "urgent": self.urgent,
            "planned": self.planned,
            "age_dist": self.age_dist,
            "violations_df": self.violations_df,
            "doctor_stats": self.doctor_stats,
            "ids_stats": self.ids_stats,
            "long_stay": self.long_stay,
            "df": self.df,
        }


def analyze_lor(df: pd.DataFrame) -> LorAnalysisResult:
    prepared = prepare_lor_dataframe(df)
    total = len(prepared)
    empty_viol = pd.DataFrame(
        columns=["КВС", "возраст", "тип госпитализации", "врач", "тип_нарушения", "нарушение"]
    )
    if total == 0:
        return LorAnalysisResult(
            total_patients=0,
            avg_beddays=0.0,
            urgent=0,
            planned=0,
            age_dist=pd.Series(dtype=int),
            violations_df=empty_viol,
            doctor_stats=pd.DataFrame(columns=["врач", "количество нарушений"]),
            ids_stats=pd.DataFrame(columns=["врач", "нарушения по ИДС"]),
            long_stay=prepared.iloc[0:0],
            df=prepared,
        )

    avg_beddays = float(prepared["Койко-дни_скор"].sum() / total)
    type_lower = prepared["Тип госпитализации"].astype(str).str.lower()
    urgent = int(type_lower.str.contains("экстрен", na=False).sum())
    planned = int(type_lower.str.contains("планов", na=False).sum())

    prepared["Возрастная группа"] = prepared["Возраст"].apply(age_group)
    age_dist = prepared["Возрастная группа"].value_counts()

    violations: list[dict] = []

    def add_rows(subset: pd.DataFrame, tip: str, text_fn):
        for _, row in subset.iterrows():
            violations.append(
                {
                    "КВС": row["Номер КВС"],
                    "возраст": row["Возраст"],
                    "тип госпитализации": row["Тип госпитализации"],
                    "врач": row["Лечащий врач"],
                    "тип_нарушения": tip,
                    "нарушение": text_fn(row),
                }
            )

    primary_col = "Наличие заполненного первичного осмотра в указанном движении"
    add_rows(
        prepared[prepared[primary_col] != "ДА"],
        "Первичный осмотр",
        lambda r: "Отсутствует первичный осмотр (не 'ДА')",
    )
    epicrisis_col = "Наличие оформленного эпикриза в указанном движении"
    add_rows(
        prepared[prepared[epicrisis_col] != "ДА"],
        "Эпикриз",
        lambda r: "Отсутствует эпикриз (не 'ДА')",
    )
    add_rows(
        prepared[prepared["Статус МКСБ"] != "Подписана"],
        "МКСБ",
        lambda r: "МКСБ не подписана",
    )
    add_rows(
        prepared[prepared["Лекарства"] == 0],
        "Лекарственные назначения",
        lambda r: "Нет лекарственных назначений (0)",
    )
    add_rows(
        prepared[prepared["Дневники_факт"] < prepared["Дневники_необх"]],
        "Дневниковые записи",
        lambda r: (
            f"Недостаточно дневников: нужно {int(r['Дневники_необх'])}, "
            f"оформлено {int(r['Дневники_факт'])}"
        ),
    )
    docs_col = "Другие связанные документы"
    add_rows(
        prepared[~prepared[docs_col].apply(_has_ids)],
        "ИДС",
        lambda r: "Отсутствует ИДС",
    )

    long_stay = prepared[prepared["Койко-дни_скор"] > 7]
    add_rows(
        long_stay,
        "Длительная госпитализация",
        lambda r: f"Койко-день >7 дней ({int(r['Койко-дни_скор'])})",
    )

    surg = prepared[prepared["Хир_кол"] > 0]
    for _, row in surg.iterrows():
        op = int(row["Хир_кол"])
        prot = int(row["Хир_прот"])
        if prot < op:
            violations.append(
                {
                    "КВС": row["Номер КВС"],
                    "возраст": row["Возраст"],
                    "тип госпитализации": row["Тип госпитализации"],
                    "врач": row["Лечащий врач"],
                    "тип_нарушения": "Протоколы операций",
                    "нарушение": f"Несоответствие протоколов: операций {op}, протоколов {prot}",
                }
            )
        elif prot > op:
            violations.append(
                {
                    "КВС": row["Номер КВС"],
                    "возраст": row["Возраст"],
                    "тип госпитализации": row["Тип госпитализации"],
                    "врач": row["Лечащий врач"],
                    "тип_нарушения": "Протоколы операций",
                    "нарушение": f"Избыток протоколов: операций {op}, протоколов {prot}",
                }
            )

    violations_df = pd.DataFrame(violations) if violations else empty_viol

    violations_for_doctor = violations_df[
        violations_df["тип_нарушения"] != "Длительная госпитализация"
    ] if not violations_df.empty else empty_viol

    if not violations_for_doctor.empty:
        doctor_stats = (
            violations_for_doctor.groupby("врач")
            .size()
            .reset_index(name="количество нарушений")
            .sort_values(by="количество нарушений", ascending=True)
            .reset_index(drop=True)
        )
    else:
        doctor_stats = pd.DataFrame(columns=["врач", "количество нарушений"])

    ids_viol = (
        violations_df[violations_df["тип_нарушения"] == "ИДС"]
        if not violations_df.empty
        else empty_viol
    )
    if not ids_viol.empty:
        ids_stats = (
            ids_viol.groupby("врач")
            .size()
            .reset_index(name="нарушения по ИДС")
            .sort_values(by="нарушения по ИДС", ascending=True)
            .reset_index(drop=True)
        )
    else:
        ids_stats = pd.DataFrame(columns=["врач", "нарушения по ИДС"])

    return LorAnalysisResult(
        total_patients=total,
        avg_beddays=avg_beddays,
        urgent=urgent,
        planned=planned,
        age_dist=age_dist,
        violations_df=violations_df,
        doctor_stats=doctor_stats,
        ids_stats=ids_stats,
        long_stay=long_stay,
        df=prepared,
    )
