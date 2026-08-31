"""Нормализация отделений в реестре КСГ."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

from excel_io import list_departments, pick_default_department

DEPT_CODE_RE = re.compile(r"^(\S+)\s*/\s*(.+)$")
LOR_NAME_MARKERS = ("оторинолар", "лор")


def parse_ksg_department(raw: Any) -> tuple[str | None, str, str]:
    """(код, нормализованное имя, исходная строка)."""
    original = str(raw or "").strip()
    if not original:
        return None, "", ""
    match = DEPT_CODE_RE.match(original)
    if match:
        code = match.group(1).strip()
        name = match.group(2).strip()
        return code, name or original, original
    return None, original, original


def is_lor_department(name: str, code: str | None = None) -> bool:
    lower = name.lower()
    if any(marker in lower for marker in LOR_NAME_MARKERS):
        return True
    if code and str(code).strip().startswith("009"):
        return True
    return False


def normalize_ksg_departments(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляет код/исходное имя; «Отделение» — нормализованное для фильтрации."""
    if df is None or df.empty or "Отделение" not in df.columns:
        return df.copy() if df is not None else pd.DataFrame()
    out = df.copy()
    parsed = out["Отделение"].map(parse_ksg_department)
    out["Отделение_код"] = [p[0] for p in parsed]
    out["Отделение_исходное"] = [p[2] for p in parsed]
    out["Отделение"] = [p[1] or p[2] for p in parsed]
    return out


def list_ksg_departments(df: pd.DataFrame) -> list[str]:
    normalized = normalize_ksg_departments(df)
    return list_departments(normalized, column="Отделение")


def pick_default_ksg_department(
    departments: list[str],
    df: pd.DataFrame | None = None,
    preferred: str | None = None,
) -> str | None:
    if not departments:
        return None
    if preferred:
        pref = preferred.strip()
        pref_l = pref.lower()
        for dep in departments:
            if dep.strip().lower() == pref_l:
                return dep
        for dep in departments:
            dl = dep.lower()
            if pref_l in dl or dl in pref_l:
                return dep
    if df is not None and not df.empty and "Отделение" in df.columns:
        work = normalize_ksg_departments(df)
        for _, row in work.iterrows():
            name = str(row.get("Отделение") or "").strip()
            code = row.get("Отделение_код")
            if name and is_lor_department(name, str(code) if pd.notna(code) else None):
                if name in departments:
                    return name
    return pick_default_department(departments, preferred)


def filter_ksg_dataframe(
    df: pd.DataFrame,
    scope: str,
    department: str = "",
    departments: list[str] | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    from lor_analysis import filter_by_department, filter_by_departments

    work = normalize_ksg_departments(df)
    all_depts = list_ksg_departments(work)
    scope = (scope or "single").strip().lower()
    if scope == "all":
        return work, all_depts
    if scope == "multi":
        names = [str(d).strip() for d in (departments or []) if str(d).strip()]
        if not names:
            return work.iloc[0:0].copy(), []
        filtered = filter_by_departments(work, names)
        return filtered, names
    dep = (department or "").strip()
    if not dep and all_depts:
        dep = all_depts[0]
    filtered = filter_by_department(work, dep or None)
    active = [dep] if dep else []
    return filtered, active
