"""Чистый анализ КСГ (без UI)."""
from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from paths import resource_path
from lor_analysis import (
    PATIENT_FIO_COL,
    format_department_scope_label,
    format_doctor_name,
    format_patient_name,
)
from ksg_kslp_profiles import (
    normalize_department_profile_map,
    normalize_ksg_kslp_profiles,
    resolve_row_kslp_settings,
)
from ksg_policy_checks import build_policy_smo_issues, policy_smo_check_available

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


def _month_ru(month: int) -> str:
    names = {
        1: "январь",
        2: "февраль",
        3: "март",
        4: "апрель",
        5: "май",
        6: "июнь",
        7: "июль",
        8: "август",
        9: "сентябрь",
        10: "октябрь",
        11: "ноябрь",
        12: "декабрь",
    }
    return names.get(month, str(month))


def _ksg_date_column(df: pd.DataFrame) -> str | None:
    if "Выписка" in df.columns:
        return "Выписка"
    if "Поступление" in df.columns:
        return "Поступление"
    return None


def list_ksg_periods(df: pd.DataFrame) -> list[dict[str, str]]:
    col = _ksg_date_column(df)
    if not col or df.empty:
        return []
    dayfirst = True
    dates = pd.to_datetime(df[col], dayfirst=dayfirst, errors="coerce").dropna()
    if dates.empty:
        return []
    periods = sorted(dates.dt.to_period("M").unique())
    out: list[dict[str, str]] = []
    for period in periods:
        out.append(
            {
                "id": str(period),
                "label": f"{_month_ru(int(period.month))} {int(period.year)}",
            }
        )
    return out


def filter_ksg_by_period(df: pd.DataFrame, period: str | None) -> pd.DataFrame:
    if df.empty or not period or str(period).strip().lower() in ("", "all"):
        return df.copy()
    col = _ksg_date_column(df)
    if not col:
        return df.copy()
    dates = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
    target = pd.Period(str(period), freq="M")
    mask = dates.dt.to_period("M") == target
    return df.loc[mask.fillna(False)].copy()


def _analysis_settings(settings: Mapping[str, Any]) -> dict[str, Any]:
    cfg = dict(settings)
    profiles = normalize_ksg_kslp_profiles(cfg)
    cfg["ksg_kslp_profiles"] = profiles
    departments = [str(d).strip() for d in (cfg.get("_ksg_departments") or []) if str(d).strip()]
    cfg["ksg_department_profiles"] = normalize_department_profile_map(cfg, departments)
    return cfg


def _resolve_kslp_rules(settings: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Normalize kslp_rules from settings; fall back to flat kslp_operations_codes."""
    raw = settings.get("kslp_rules")
    rules: list[dict[str, Any]] = []
    if isinstance(raw, list):
        for i, item in enumerate(raw):
            if not isinstance(item, dict):
                continue
            codes = [str(c).strip() for c in (item.get("codes") or []) if str(c).strip()]
            if not codes:
                continue
            name = str(item.get("name") or f"Правило {i + 1}").strip() or f"Правило {i + 1}"
            rules.append({"id": str(item.get("id") or f"rule-{i + 1}"), "name": name, "codes": codes})
    if rules:
        return rules
    legacy = settings.get("kslp_operations_codes") or []
    codes = [str(c).strip() for c in legacy if str(c).strip()]
    if not codes:
        return []
    return [{"id": "legacy-ops", "name": "Правило 1", "codes": codes}]


def _matching_kslp_rules(code_set: set[str], rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    matched: list[dict[str, Any]] = []
    for rule in rules:
        codes = rule.get("codes") or []
        if codes and all(c in code_set for c in codes):
            matched.append(rule)
    return matched


def build_by_department_summary(
    df: pd.DataFrame,
    reference: Mapping[str, tuple[str, str]],
    settings: Mapping[str, Any],
) -> pd.DataFrame:
    if df.empty or "Отделение" not in df.columns:
        return pd.DataFrame(
            columns=["Отделение", "Пациенты", "Сумма", "Средний КЗ", "КСЛП"]
        )
    rows: list[dict[str, Any]] = []
    for dep, group in df.groupby("Отделение", dropna=False):
        part = analyze_ksg(group, reference, {**settings, "_skip_by_department": True})
        rows.append(
            {
                "Отделение": dep,
                "Пациенты": part["total_patients"],
                "Сумма": part["total_sum"],
                "Средний КЗ": part["avg_kz_total"],
                "КСЛП": part["total_kslp_issues"],
            }
        )
    out = pd.DataFrame(rows)
    if not out.empty:
        out = out.sort_values(["Сумма", "Отделение"], ascending=[False, True])
    return out.reset_index(drop=True)


def _ksg_money_columns(data: pd.DataFrame) -> list[str]:
    cols = ["№ талона"]
    if PATIENT_FIO_COL in data.columns:
        cols.append(PATIENT_FIO_COL)
    cols.append("Врач")
    if "Код услуги" in data.columns:
        cols.append("Код услуги")
    cols.extend(["Сумма к оплате", "Дата рождения"])
    if "Отделение" in data.columns:
        cols.append("Отделение")
    return cols


def _service_label(raw: Any, reference: Mapping[str, tuple[str, str]]) -> str:
    if pd.isna(raw):
        return "Услуга отсутствует"
    text = str(raw).strip()
    if not text or text.lower() in ("nan", "none", "null"):
        return "Услуга отсутствует"
    codes = [c for c in text.split() if c.strip()]
    if not codes:
        return "Услуга отсутствует"
    parts: list[str] = []
    for code in sorted(set(codes)):
        info = reference.get(code)
        parts.append(f"{code} ({info[0]})" if info else code)
    return ", ".join(parts)


def _format_ksg_case_frame(
    df: pd.DataFrame,
    reference: Mapping[str, tuple[str, str]] | None = None,
) -> pd.DataFrame:
    out = df.copy()
    if PATIENT_FIO_COL in out.columns:
        out[PATIENT_FIO_COL] = out[PATIENT_FIO_COL].map(format_patient_name)
    if "Врач" in out.columns:
        out["Врач"] = out["Врач"].map(format_doctor_name)
    ref = reference or {}
    if "Код услуги" in out.columns:
        out["Услуга"] = out["Код услуги"].map(lambda v: _service_label(v, ref))
        out = out.drop(columns=["Код услуги"])
    elif "Услуга" not in out.columns:
        out["Услуга"] = "Услуга отсутствует"
    else:
        out["Услуга"] = out["Услуга"].map(
            lambda v: _service_label(v, ref)
            if str(v or "").strip()
            else "Услуга отсутствует"
        )
    if "Услуга" in out.columns:
        cols = [c for c in out.columns if c != "Услуга"]
        insert_at = cols.index("Врач") + 1 if "Врач" in cols else len(cols)
        cols.insert(insert_at, "Услуга")
        out = out[cols]
    return out


def _kslp_issue_row(row: pd.Series, *, age: int, kslp: Any, note: str) -> dict[str, Any]:
    item: dict[str, Any] = {
        "№ талона": row["№ талона"],
        "Врач": format_doctor_name(row["Врач"]),
        "Дата рождения": row["Дата рождения"],
        "Возраст": age,
        "КСЛП": kslp,
        "Замечание": note,
    }
    if PATIENT_FIO_COL in row.index:
        item[PATIENT_FIO_COL] = format_patient_name(row.get(PATIENT_FIO_COL))
    if "Отделение" in row.index:
        item["Отделение"] = row.get("Отделение", "")
    return item


def _kslp_issue_columns(data: pd.DataFrame) -> list[str]:
    cols = ["№ талона"]
    if PATIENT_FIO_COL in data.columns:
        cols.append(PATIENT_FIO_COL)
    cols.append("Врач")
    if "Отделение" in data.columns:
        cols.append("Отделение")
    cols.extend(["Дата рождения", "Возраст", "КСЛП", "Замечание"])
    return cols


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
                    "Врач": format_doctor_name(row["Врач"]),
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
        ops_pivot.index = ops_pivot.index.set_names(["Код услуги", "Операция"])
    else:
        ops_pivot = pd.DataFrame()

    total_sum = float(data["Сумма к оплате"].sum())
    sum_by_doctor = (
        data.groupby("Врач")["Сумма к оплате"].sum().reset_index(name="Сумма к оплате")
    )
    doctor_sums = data.groupby("Врач")["Сумма к оплате"].sum().reset_index()

    low_thresh = float(settings.get("ksg_threshold_low", 20000))
    high_thresh = float(settings.get("ksg_threshold_high", 100000))
    cols_money = _ksg_money_columns(data)
    low_money = _format_ksg_case_frame(
        data[data["Сумма к оплате"] < low_thresh][cols_money].copy(),
        reference,
    )
    high_money = _format_ksg_case_frame(
        data[data["Сумма к оплате"] > high_thresh][cols_money].copy(),
        reference,
    )
    no_service = _format_ksg_case_frame(
        data[
            data["Код услуги"].isna() | (data["Код услуги"].astype(str).str.strip() == "")
        ][cols_money].copy(),
        reference,
    )

    cfg = _analysis_settings(settings)
    profiles = cfg.get("ksg_kslp_profiles") or {}
    department_profile_map = cfg.get("ksg_department_profiles") or {}
    use_profiles = "Отделение" in data.columns and bool(profiles)

    target_codes = list(settings.get("kslp_operations_codes") or [])
    age_min = int(settings.get("kslp_age_min", 0))
    age_max = int(settings.get("kslp_age_max", 4))
    senior_age = int(settings.get("kslp_senior_age", 75))
    kslp_rules = _resolve_kslp_rules(settings)
    if not target_codes and kslp_rules:
        target_codes = list(kslp_rules[0].get("codes") or [])

    kslp_issues = []
    for _, row in data.iterrows():
        age = row["Возраст"]
        kslp = row["КСЛП итоговый"]
        if pd.isna(kslp):
            continue

        if use_profiles:
            row_settings = resolve_row_kslp_settings(
                row.get("Отделение"),
                row.get("Отделение_код"),
                profiles,
                department_profile_map,
            )
            if not row_settings.get("check_kslp"):
                continue
            row_age_min = int(row_settings.get("age_min", age_min))
            row_age_max = int(row_settings.get("age_max", age_max))
            row_senior_age = int(row_settings.get("senior_age", senior_age))
            row_rules = list(row_settings.get("rules") or []) if row_settings.get("use_rules") else []
            profile_name = str(row_settings.get("profile_name") or "")
        else:
            row_age_min, row_age_max, row_senior_age = age_min, age_max, senior_age
            row_rules = kslp_rules
            profile_name = ""

        code_set = set(str(row["Код услуги"]).strip().split())
        is_child = row_age_min <= age <= row_age_max
        is_senior = age >= row_senior_age
        matched_rules = _matching_kslp_rules(code_set, row_rules)
        has_ops_rule = bool(matched_rules)
        need_kslp = is_child or is_senior or has_ops_rule

        code_names = []
        for c in code_set:
            info = reference.get(c)
            code_names.append(f"{c} ({info[0]})" if info else c)
        codes_str = ", ".join(sorted(code_names)) if code_names else "нет"

        if need_kslp and kslp == 0:
            reasons = []
            if is_child:
                reasons.append(f"ребёнок {row_age_min}-{row_age_max} лет")
            if is_senior:
                reasons.append(f"возраст ≥{row_senior_age} лет")
            for rule in matched_rules:
                rule_codes = ", ".join(rule["codes"])
                reasons.append(f"правило «{rule['name']}» ({rule_codes})")
            note = f"КСЛП должен быть >0 (основание: {'; '.join(reasons)}). Коды услуг: {codes_str}"
            if profile_name:
                note = f"[{profile_name}] {note}"
            kslp_issues.append(_kslp_issue_row(row, age=age, kslp=kslp, note=note))
        elif not need_kslp and kslp > 0:
            rule_hint = (
                f"{len(row_rules)} правил(а) по операциям"
                if row_rules
                else "нет правил по операциям"
            )
            note = (
                f"КСЛП > 0 без показаний (нет оснований: не ребёнок {row_age_min}-{row_age_max}, "
                f"возраст < {row_senior_age}, не сработало ни одно правило операций — {rule_hint}). "
                f"Коды услуг: {codes_str}"
            )
            if profile_name:
                note = f"[{profile_name}] {note}"
            kslp_issues.append(_kslp_issue_row(row, age=age, kslp=kslp, note=note))

    kslp_columns = _kslp_issue_columns(data)
    kslp_issues_df = pd.DataFrame(kslp_issues, columns=kslp_columns)

    data["Возрастная группа"] = data["Возраст"].apply(_age_group)
    age_dist = data["Возрастная группа"].value_counts()
    age_sum = data.groupby("Возрастная группа")["Сумма к оплате"].sum()
    age_kz = data.groupby("Возрастная группа")["КЗ"].mean().round(3)
    avg_kz_doctor = data.groupby("Врач")["КЗ"].mean().reset_index(name="Средний КЗ").round(3)
    avg_kz_total = round(float(data["КЗ"].mean()), 3) if len(data) else 0.0

    by_department = pd.DataFrame()
    if not settings.get("_skip_by_department"):
        by_department = build_by_department_summary(data, reference, settings)

    policy_check_available = policy_smo_check_available(data)
    policy_check_enabled = bool(settings.get("ksg_check_policy_smo")) and policy_check_available
    policy_issues_df = (
        build_policy_smo_issues(data) if policy_check_enabled else pd.DataFrame()
    )
    other_violations: dict[str, int] = {}
    if policy_check_enabled and not policy_issues_df.empty:
        other_violations["Полис / СМО"] = len(policy_issues_df)

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
        "policy_issues": policy_issues_df,
        "policy_check_enabled": policy_check_enabled,
        "policy_check_available": policy_check_available,
        "by_department": by_department,
        "age_dist": age_dist,
        "age_sum": age_sum,
        "age_kz": age_kz,
        "avg_kz_doctor": avg_kz_doctor,
        "avg_kz_total": avg_kz_total,
        "total_kslp_issues": len(kslp_issues_df),
        "total_policy_issues": len(policy_issues_df),
        "other_violations": other_violations,
        "thresholds": {"low": low_thresh, "high": high_thresh},
        "kslp_settings": {
            "age_min": age_min,
            "age_max": age_max,
            "senior_age": senior_age,
            "codes": target_codes,
            "rules": kslp_rules,
        },
    }


def ksg_period_sort_key(df: pd.DataFrame | None, name: str = "") -> tuple[int, int, int]:
    """Ключ сортировки месяца: (год, месяц, день) по графе «Выписка»."""
    if df is not None and not df.empty:
        # Период отчёта КСГ = месяц выписки, не поступления
        date_col = "Выписка" if "Выписка" in df.columns else (
            "Поступление" if "Поступление" in df.columns else None
        )
        if date_col:
            dates = pd.to_datetime(df[date_col], dayfirst=True, errors="coerce").dropna()
            if not dates.empty:
                periods = dates.dt.to_period("M")
                mode = periods.mode()
                mid = mode.iloc[0] if not mode.empty else periods.min()
                return int(mid.year), int(mid.month), 1

    lower = (name or "").lower()
    year_match = re.search(r"(20\d{2})", lower)
    year = int(year_match.group(1)) if year_match else 9999
    month_map = [
        (1, ("январ",)),
        (2, ("феврал",)),
        (3, ("март", "марте")),
        (4, ("апрел",)),
        (5, ("май", "мая", "мае")),
        (6, ("июн",)),
        (7, ("июл",)),
        (8, ("август",)),
        (9, ("сентябр",)),
        (10, ("октябр",)),
        (11, ("ноябр",)),
        (12, ("декабр",)),
    ]
    month = 12
    for num, aliases in month_map:
        if any(a in lower for a in aliases):
            month = num
            break
    return year, month, 1


def ksg_item_primary_df(item: Mapping[str, Any]) -> pd.DataFrame | None:
    """DataFrame КСГ из элемента сессии без неоднозначного truth-value."""
    df = item.get("df_ksg")
    if df is None:
        df = item.get("df")
    return df if isinstance(df, pd.DataFrame) else None


def sort_ksg_files_chronologically(files: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Сортирует загруженные КСГ-файлы по возрастанию периода."""
    return sorted(
        files,
        key=lambda f: ksg_period_sort_key(ksg_item_primary_df(f), f.get("name", "")),
    )


def build_month_comparison(files: list[dict[str, Any]]) -> dict[str, Any]:
    """Сводное сравнение нескольких загруженных КСГ-файлов (месяцев) по возрастанию."""
    files = sort_ksg_files_chronologically(files)
    names = [f["name"] for f in files]
    results = [f["results"] for f in files]
    summary = {
        "names": names,
        "files": files,
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


def build_department_comparison(
    item: dict[str, Any],
    *,
    departments: list[str],
    period: str,
    source: str,
    reference: Mapping[str, tuple[str, str]],
    settings: Mapping[str, Any],
) -> dict[str, Any]:
    from ksg_departments import filter_ksg_dataframe

    if source == "other":
        df_full = item.get("df_other")
    else:
        df_full = item.get("df_ksg")
        if df_full is None:
            df_full = item.get("df")
    if df_full is None or getattr(df_full, "empty", True):
        return {
            "labels": [],
            "departments": [],
            "total_patients": [],
            "total_sum": [],
            "avg_kz": [],
            "kslp_issues": [],
        }
    df_full = filter_ksg_by_period(df_full, period)
    labels: list[str] = []
    patients: list[int] = []
    sums: list[float] = []
    kz_values: list[float] = []
    kslp_counts: list[int] = []
    deps_out: list[str] = []
    analyze_cfg = dict(settings)
    analyze_cfg["_ksg_departments"] = list(item.get("departments") or [])
    for dep in departments:
        filtered, _ = filter_ksg_dataframe(df_full, "single", dep, [])
        if filtered.empty:
            continue
        result = analyze_ksg(filtered, reference, {**analyze_cfg, "_skip_by_department": True})
        labels.append(dep)
        deps_out.append(dep)
        patients.append(int(result.get("total_patients") or 0))
        sums.append(float(result.get("total_sum") or 0))
        kz_values.append(float(result.get("avg_kz_total") or 0))
        kslp_counts.append(int(result.get("total_kslp_issues") or 0))
    return {
        "labels": labels,
        "departments": deps_out,
        "total_patients": patients,
        "total_sum": sums,
        "avg_kz": kz_values,
        "kslp_issues": kslp_counts,
    }
