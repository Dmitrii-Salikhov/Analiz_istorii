"""Чистый анализ КСГ (без UI)."""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from paths import resource_path

DEFAULT_REFERENCE_MAPPING = [
    ("Аденотомия", "A16.08.002.001", "на миндалинах и аденоидах (5.2)"),
    ("Тонзиллотомия", "A16.08.064", "на миндалинах и аденоидах (5.2)"),
    ("Миринготомия план", "A16.25.011", "на ухе (5.1)"),
    ("Пластика раковин", "A16.08.010.003", "органы дыхания (6)"),
    ("ПТА", "A16.08.012", "на миндалинах и аденоидах (5.2)"),
    ("Миринготомия экстр", "A16.25.011", "на ухе (5.1)"),
    ("Полипотомия", "A16.08.009.001, A16.08.071", "органы дыхания (6)"),
    ("Септопластика", "A16.08.013.001", "органы дыхания (6)"),
    ("Гайморотомия", "A16.08.017.001", "органы дыхания (6)"),
    ("Тонзиллэктомия", "A16.08.001.001", "на миндалинах и аденоидах (5.2)"),
    ("Увулопластика", "A16.07.087", "органы дыхания (6)"),
    ("Фурункул НСП", "A16.01.011, A16.25.001", "на ухе (5.1)"),
    ("Фурункул носа", "A16.08.018", "органы дыхания (6)"),
    ("Трахеостомия", "A16.08.003", "органы дыхания (6)"),
    ("Репозиция костей носа", "A16.03.034.002", "органы дыхания (6)"),
    ("Остановка кровотечения", "A16.12.020.001", "органы дыхания (6)"),
    ("Синехии носа", "A16.08.055", "органы дыхания (6)"),
    ("Удаление новообразования носа", "A16.08.035.001", "органы дыхания (6)"),
    ("Удаление новообразования уха", "A16.25.035, A16.25.040", "на ухе (5.1)"),
    ("Удаление новообразования глотки", "A16.08.054, A16.08.054.002", "органы дыхания (6)"),
    ("Удаление новообразования гортани", "A16.08.040, A16.08.040.003, A16.08.040.008", "органы дыхания (6)"),
    ("Удаление инородного тела", "A16.25.008, A16.25.008.001", "органы дыхания (6)"),
    ("Пластика местными тканями", "A16.01.010.002", "кожа и подкожная клетчатка (17)"),
    ("Наложение вторичных швов", "A16.01.008.001", "кожа и подкожная клетчатка (17)"),
    ("Биопсия гортани", "A11.08.001", "органы дыхания (6)"),
]


def build_default_reference() -> dict[str, tuple[str, str]]:
    ref: dict[str, tuple[str, str]] = {}
    for name, codes, group in DEFAULT_REFERENCE_MAPPING:
        for code in codes.split(","):
            code = code.strip()
            if code:
                ref[code] = (name, group)
    return ref


def load_reference(csv_path: Path | None = None) -> tuple[dict[str, tuple[str, str]], str]:
    """
    Возвращает (справочник, статус-строка).
    """
    path = csv_path or resource_path("KSGoperacii.csv")
    if path.exists():
        try:
            df = pd.read_csv(path, sep=";", dtype=str)
            ref: dict[str, tuple[str, str]] = {}
            for _, row in df.iterrows():
                code = str(row.iloc[0]).strip()
                name = str(row.iloc[1]).strip()
                group = (
                    str(row.iloc[2]).split(",")[0].strip()
                    if pd.notna(row.iloc[2])
                    else "???"
                )
                if code:
                    ref[code] = (name, group)
            return ref, f"Справочник КСГ: загружен из {path.name}"
        except Exception as e:
            logging.error("Ошибка загрузки справочника: %s", e)
            return build_default_reference(), (
                f"Справочник КСГ: ошибка чтения {path.name}, используется встроенный"
            )
    return build_default_reference(), "Справочник КСГ: используется встроенный (CSV не найден)"


def _age_group(age) -> str:
    if pd.isna(age):
        return "неизвестно"
    if age <= 14:
        return "0-14 лет"
    if age <= 17:
        return "15-17 лет"
    if age <= 64:
        return "18-64 года"
    return "65+ лет"


def analyze_ksg(
    df: pd.DataFrame,
    reference: Mapping[str, tuple[str, str]],
    settings: Mapping[str, Any],
) -> dict[str, Any]:
    data = df.copy()
    data["Сумма к оплате"] = pd.to_numeric(
        data["Сумма к оплате"].astype(str).str.replace(",", ".", regex=False),
        errors="coerce",
    )
    data["КСЛП итоговый"] = pd.to_numeric(
        data["КСЛП итоговый"].astype(str).str.replace(",", ".", regex=False),
        errors="coerce",
    )
    data["КЗ"] = pd.to_numeric(
        data["КЗ"].astype(str).str.replace(",", ".", regex=False),
        errors="coerce",
    )

    date_col = "Поступление" if "Поступление" in data.columns else "Выписка"
    dayfirst = settings.get("date_format", "dayfirst") == "dayfirst"
    data[date_col] = pd.to_datetime(data[date_col], dayfirst=dayfirst, errors="coerce")
    data["Дата рождения"] = pd.to_datetime(
        data["Дата рождения"], dayfirst=dayfirst, errors="coerce"
    )
    data = data.dropna(subset=[date_col, "Дата рождения"]).copy()

    data["Возраст"] = data.apply(
        lambda row: (row[date_col].year - row["Дата рождения"].year)
        - (
            (row[date_col].month, row[date_col].day)
            < (row["Дата рождения"].month, row["Дата рождения"].day)
        ),
        axis=1,
    )

    patient_counts = (
        data.groupby("Врач")["№ талона"].nunique().reset_index(name="Количество пациентов")
    )
    total_patients = int(data["№ талона"].nunique())

    operations = []
    unknown_codes: set[str] = set()
    for _, row in data.iterrows():
        for code in str(row["Код услуги"]).split():
            if not code:
                continue
            cat_info = reference.get(code)
            if cat_info is None:
                unknown_codes.add(code)
                category, group = "???", "Неизвестно"
            else:
                category, group = cat_info
            operations.append(
                {
                    "Врач": row["Врач"],
                    "Код услуги": code,
                    "Категория": category,
                    "Группа": group,
                }
            )
    ops_df = pd.DataFrame(operations)
    if not ops_df.empty:
        ops_pivot = ops_df.pivot_table(
            index=["Код услуги", "Категория"], columns="Врач", aggfunc="size", fill_value=0
        )
    else:
        ops_pivot = pd.DataFrame()

    total_sum = float(data["Сумма к оплате"].sum())
    sum_by_doctor = (
        data.groupby("Врач")["Сумма к оплате"].sum().reset_index(name="Сумма к оплате")
    )
    doctor_sums = data.groupby("Врач")["Сумма к оплате"].sum().reset_index()

    low_thresh = float(settings.get("ksg_threshold_low", 20000))
    high_thresh = float(settings.get("ksg_threshold_high", 100000))
    cols_money = ["№ талона", "Врач", "Сумма к оплате", "Дата рождения"]
    low_money = data[data["Сумма к оплате"] < low_thresh][cols_money].copy()
    high_money = data[data["Сумма к оплате"] > high_thresh][cols_money].copy()
    no_service = data[
        data["Код услуги"].isna() | (data["Код услуги"].astype(str).str.strip() == "")
    ][cols_money].copy()

    target_codes = list(settings.get("kslp_operations_codes") or [])
    age_min = int(settings.get("kslp_age_min", 0))
    age_max = int(settings.get("kslp_age_max", 4))
    senior_age = int(settings.get("kslp_senior_age", 75))

    kslp_issues = []
    for _, row in data.iterrows():
        age = row["Возраст"]
        kslp = row["КСЛП итоговый"]
        if pd.isna(kslp):
            continue
        code_set = set(str(row["Код услуги"]).strip().split())
        is_child = age_min <= age <= age_max
        is_senior = age >= senior_age
        has_all_three = bool(target_codes) and all(c in code_set for c in target_codes)
        need_kslp = is_child or is_senior or has_all_three

        code_names = []
        for c in code_set:
            info = reference.get(c)
            code_names.append(f"{c} ({info[0]})" if info else c)
        codes_str = ", ".join(sorted(code_names)) if code_names else "нет"

        if need_kslp and kslp == 0:
            reasons = []
            if is_child:
                reasons.append(f"ребёнок {age_min}-{age_max} лет")
            if is_senior:
                reasons.append(f"возраст ≥{senior_age} лет")
            if has_all_three:
                reasons.append("наличие полного набора целевых операций")
            kslp_issues.append(
                (
                    row["№ талона"],
                    row["Врач"],
                    row["Дата рождения"],
                    age,
                    kslp,
                    f"КСЛП должен быть >0 (основание: {'; '.join(reasons)}). Коды услуг: {codes_str}",
                )
            )
        elif not need_kslp and kslp > 0:
            kslp_issues.append(
                (
                    row["№ талона"],
                    row["Врач"],
                    row["Дата рождения"],
                    age,
                    kslp,
                    (
                        f"КСЛП > 0 без показаний (нет оснований: не ребёнок {age_min}-{age_max}, "
                        f"возраст < {senior_age}, нет полного набора операций). "
                        f"Коды услуг: {codes_str}"
                    ),
                )
            )

    kslp_issues_df = pd.DataFrame(
        kslp_issues,
        columns=["№ талона", "Врач", "Дата рождения", "Возраст", "КСЛП", "Замечание"],
    )

    data["Возрастная группа"] = data["Возраст"].apply(_age_group)
    age_dist = data["Возрастная группа"].value_counts()
    age_sum = data.groupby("Возрастная группа")["Сумма к оплате"].sum()
    age_kz = data.groupby("Возрастная группа")["КЗ"].mean().round(3)
    avg_kz_doctor = data.groupby("Врач")["КЗ"].mean().reset_index(name="Средний КЗ").round(3)
    avg_kz_total = round(float(data["КЗ"].mean()), 3) if len(data) else 0.0

    return {
        "patient_counts": patient_counts,
        "total_patients": total_patients,
        "ops_pivot": ops_pivot,
        "unknown_codes": sorted(unknown_codes),
        "total_sum": total_sum,
        "sum_by_doctor": sum_by_doctor,
        "doctor_sums": doctor_sums,
        "low_money": low_money,
        "high_money": high_money,
        "no_service": no_service,
        "kslp_issues": kslp_issues_df,
        "age_dist": age_dist,
        "age_sum": age_sum,
        "age_kz": age_kz,
        "avg_kz_doctor": avg_kz_doctor,
        "avg_kz_total": avg_kz_total,
        "total_kslp_issues": len(kslp_issues_df),
        "other_violations": {},
        "thresholds": {"low": low_thresh, "high": high_thresh},
        "kslp_settings": {
            "age_min": age_min,
            "age_max": age_max,
            "senior_age": senior_age,
            "codes": target_codes,
        },
    }


def build_month_comparison(files: list[dict[str, Any]]) -> dict[str, Any]:
    """Сводное сравнение нескольких загруженных КСГ-файлов (месяцев)."""
    names = [f["name"] for f in files]
    results = [f["results"] for f in files]
    summary = {
        "names": names,
        "total_patients": [r["total_patients"] for r in results],
        "total_sum": [r["total_sum"] for r in results],
        "avg_kz": [r["avg_kz_total"] for r in results],
        "kslp_issues": [r["total_kslp_issues"] for r in results],
    }
    all_doctors: set[str] = set()
    for r in results:
        all_doctors.update(r["doctor_sums"]["Врач"].dropna().tolist())
    doctors = sorted(all_doctors)
    by_doctor: dict[str, list[float]] = {doc: [] for doc in doctors}
    for r in results:
        sums = r["doctor_sums"].set_index("Врач")["Сумма к оплате"]
        for doc in doctors:
            by_doctor[doc].append(float(sums.get(doc, 0) or 0))
    summary["doctors"] = doctors
    summary["doctor_sums"] = by_doctor
    return summary
