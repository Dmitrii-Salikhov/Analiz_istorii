"""Опциональная проверка номера полиса и СМО в отчётах КСГ."""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

from lor_analysis import PATIENT_FIO_COL, format_doctor_name, format_patient_name

POLICY_NUMBER_COL = "Номер полиса"
POLICY_SERIES_COL = "Серия полиса"
SMO_COL = "СМО"

_PLACEHOLDER_RE = re.compile(
    r"(^number$|^series$|code_msk|name_msk|msk_ot|\+p\.|p\.(num|ser|fam|im|ot))",
    re.I,
)


def _clean_cell(val: Any) -> str:
    return str(val or "").strip()


def is_missing_policy_number(val: Any) -> bool:
    s = _clean_cell(val)
    if not s or s.lower() in ("nan", "none", "null", "-", "—", "0", "нет"):
        return True
    compact = re.sub(r"\s+", "", s)
    if _PLACEHOLDER_RE.search(compact):
        return True
    return not re.search(r"\d", s)


def is_missing_smo(val: Any) -> bool:
    s = _clean_cell(val)
    if not s or s.lower() in ("nan", "none", "null", "-", "—", "0", "нет"):
        return True
    compact = re.sub(r"\s+", "", s)
    if _PLACEHOLDER_RE.search(compact):
        return True
    if re.match(r"^\d{5}\s*-", s):
        return False
    return not (len(s) >= 5 and re.search(r"[A-Za-zА-Яа-яЁё]", s))


def policy_smo_check_available(df: pd.DataFrame) -> bool:
    return POLICY_NUMBER_COL in df.columns and SMO_COL in df.columns


def _policy_issue_note(*, missing_number: bool, missing_smo: bool) -> str:
    if missing_number and missing_smo:
        return "Не указаны номер полиса и СМО"
    if missing_number:
        return "Не указан номер полиса"
    return "Не указана СМО"


def _display_cell(val: Any) -> str:
    s = _clean_cell(val)
    if not s or s.lower() == "nan":
        return "—"
    return s


def build_policy_smo_issues(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or not policy_smo_check_available(df):
        return pd.DataFrame()

    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        missing_number = is_missing_policy_number(row.get(POLICY_NUMBER_COL))
        missing_smo = is_missing_smo(row.get(SMO_COL))
        if not missing_number and not missing_smo:
            continue
        item: dict[str, Any] = {
            "№ талона": row.get("№ талона", ""),
            "Врач": format_doctor_name(row.get("Врач", "")),
            POLICY_NUMBER_COL: _display_cell(row.get(POLICY_NUMBER_COL)),
            SMO_COL: _display_cell(row.get(SMO_COL)),
            "Замечание": _policy_issue_note(missing_number=missing_number, missing_smo=missing_smo),
        }
        if PATIENT_FIO_COL in row.index:
            item[PATIENT_FIO_COL] = format_patient_name(row.get(PATIENT_FIO_COL))
        if "Отделение" in row.index:
            item["Отделение"] = row.get("Отделение", "")
        rows.append(item)

    columns = ["№ талона"]
    if PATIENT_FIO_COL in df.columns:
        columns.append(PATIENT_FIO_COL)
    columns.extend(["Врач"])
    if "Отделение" in df.columns:
        columns.append("Отделение")
    columns.extend([POLICY_NUMBER_COL, SMO_COL, "Замечание"])
    return pd.DataFrame(rows, columns=columns)
