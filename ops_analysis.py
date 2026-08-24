"""Проверки опержурнала: длительные операции и незанесение на опер. стол."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional, Sequence

import pandas as pd

DEFAULT_LONG_OP_HOURS = 4.0

# Canonical column names after alias map
COL_DATE_START = "Дата начала операции"
COL_TIME_START = "Время начала операции"
COL_DATE_END = "Дата окончания операции"
COL_TIME_END = "Время окончания операции"
COL_KVS = "№ истории"
COL_PATIENT = "Фамилия, имя, отчество пациента"
COL_TABLE = "Опер.стол"
COL_SERVICE = "Услуга"
COL_TEAM = "Операционная бригада"
COL_DEPT = "Отделение госпитализации"

OPS_REQUIRED_COLUMNS: tuple[str, ...] = (
    COL_DATE_START,
    COL_KVS,
    COL_SERVICE,
    COL_TABLE,
)

OPS_OPTIONAL_COLUMNS: tuple[str, ...] = (
    COL_TIME_START,
    COL_DATE_END,
    COL_TIME_END,
    COL_PATIENT,
    COL_TEAM,
    COL_DEPT,
)


def parse_op_datetime(date_val: Any, time_val: Any = None) -> Optional[pd.Timestamp]:
    """Дата + время операции → Timestamp (DD.MM.YYYY / ISO + HH:MM)."""
    if date_val is None or (isinstance(date_val, float) and pd.isna(date_val)):
        return None
    if isinstance(date_val, pd.Timestamp):
        base = date_val.to_pydatetime()
    elif isinstance(date_val, datetime):
        base = date_val
    else:
        s = str(date_val).strip()
        if not s or s.lower() in ("nan", "none", "nat"):
            return None
        if " " in s and re.match(r"^\d{1,2}[./]\d{1,2}[./]\d{2,4}\s+\d", s):
            s_date, s_time = s.split(None, 1)
            if time_val is None or (isinstance(time_val, float) and pd.isna(time_val)):
                time_val = s_time
            s = s_date
        base_ts = pd.to_datetime(s, dayfirst=True, errors="coerce")
        if pd.isna(base_ts):
            return None
        base = base_ts.to_pydatetime()

    hour, minute, second = 0, 0, 0
    if time_val is not None and not (isinstance(time_val, float) and pd.isna(time_val)):
        if isinstance(time_val, datetime):
            hour, minute, second = time_val.hour, time_val.minute, time_val.second
        elif isinstance(time_val, pd.Timestamp):
            hour, minute, second = time_val.hour, time_val.minute, time_val.second
        else:
            ts = str(time_val).strip()
            if ts and ts.lower() not in ("nan", "none"):
                m = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?", ts)
                if m:
                    hour = int(m.group(1))
                    minute = int(m.group(2))
                    second = int(m.group(3) or 0)
                else:
                    t_parsed = pd.to_datetime(ts, errors="coerce")
                    if pd.notna(t_parsed):
                        hour, minute, second = t_parsed.hour, t_parsed.minute, t_parsed.second
    try:
        return pd.Timestamp(
            year=base.year,
            month=base.month,
            day=base.day,
            hour=hour,
            minute=minute,
            second=second,
        )
    except (ValueError, OverflowError):
        return None


def duration_hours(start: Any, end: Any) -> Optional[float]:
    """Длительность в часах по датам/времени из отчёта (без «исправления» суток)."""
    if start is None or end is None or pd.isna(start) or pd.isna(end):
        return None
    try:
        hours = float((pd.Timestamp(end) - pd.Timestamp(start)).total_seconds()) / 3600.0
        if hours < 0:
            return None
        return hours
    except Exception:
        return None


def extract_surgeon(team_str: str) -> str:
    """ФИО хирурга из «Операционная бригада»."""
    text = str(team_str or "").strip()
    if not text or text.lower() in ("nan", "none"):
        return "Не указан"
    # Полное ФИО или инициалы после слова «Хирург»
    m = re.search(
        r"(?:Основной\s+)?Хирург\s+([^;]+?)(?=\s*;|\s*Операцион|$)",
        text,
        flags=re.IGNORECASE,
    )
    if m:
        name = re.sub(r"\s+", " ", m.group(1)).strip(" .,;")
        if name:
            return name
    return "Не указан"


def _fmt_kvs(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none"):
        return ""
    return s


def _fmt_hours(val: Any) -> str:
    """Человекочитаемая длительность: 0:20, 1:05, 4:30."""
    try:
        h = float(val)
    except (TypeError, ValueError):
        return ""
    if h < 0 or h != h:  # NaN
        return ""
    total_min = int(round(h * 60))
    hh, mm = divmod(total_min, 60)
    return f"{hh}:{mm:02d}"


def _clean_text(val: Any) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none"):
        return ""
    return s


def long_op_hours_from_config(config: dict[str, Any] | None) -> float:
    if not config:
        return DEFAULT_LONG_OP_HOURS
    try:
        return float(config.get("long_op_hours", DEFAULT_LONG_OP_HOURS))
    except (TypeError, ValueError):
        return DEFAULT_LONG_OP_HOURS


def normalize_ops_df(df: pd.DataFrame) -> pd.DataFrame:
    """Строки журнала → канонические поля для проверок."""
    rows: list[dict[str, Any]] = []
    for _, row in df.iterrows():
        date_start = row.get(COL_DATE_START) if COL_DATE_START in df.columns else None
        if date_start is None or (isinstance(date_start, float) and pd.isna(date_start)):
            # skip empty header leftovers
            if not _clean_text(row.get(COL_KVS) if COL_KVS in df.columns else None):
                continue
        time_start = row.get(COL_TIME_START) if COL_TIME_START in df.columns else None
        date_end = row.get(COL_DATE_END) if COL_DATE_END in df.columns else date_start
        time_end = row.get(COL_TIME_END) if COL_TIME_END in df.columns else None
        start_dt = parse_op_datetime(date_start, time_start)
        end_dt = parse_op_datetime(date_end, time_end)
        hours = duration_hours(start_dt, end_dt)
        team = _clean_text(row.get(COL_TEAM) if COL_TEAM in df.columns else None)
        dept = _clean_text(row.get(COL_DEPT) if COL_DEPT in df.columns else None)
        if not dept and "Отделение" in df.columns:
            dept = _clean_text(row.get("Отделение"))
        rows.append(
            {
                "КВС": _fmt_kvs(row.get(COL_KVS) if COL_KVS in df.columns else None),
                "Пациент": _clean_text(row.get(COL_PATIENT) if COL_PATIENT in df.columns else None),
                "Хирург": extract_surgeon(team),
                "Услуга": _clean_text(row.get(COL_SERVICE) if COL_SERVICE in df.columns else None),
                "Опер.стол": _clean_text(row.get(COL_TABLE) if COL_TABLE in df.columns else None),
                "Отделение": dept,
                "Начало": start_dt,
                "Конец": end_dt,
                "Длительность_ч": hours,
                "Дата": start_dt.normalize() if start_dt is not None else None,
            }
        )
    return pd.DataFrame(rows)


def list_ops_departments(df: pd.DataFrame) -> list[str]:
    """Уникальные отделения из отчёта операций."""
    col = COL_DEPT if COL_DEPT in df.columns else ("Отделение" if "Отделение" in df.columns else None)
    if not col:
        return []
    values = (
        df[col]
        .fillna("")
        .astype(str)
        .map(lambda x: _clean_text(x))
        .loc[lambda s: s.str.len() > 0]
        .unique()
        .tolist()
    )
    return sorted(values, key=lambda s: s.lower())


def filter_ops_by_departments(ops: pd.DataFrame, departments: Sequence[str]) -> pd.DataFrame:
    """Строгое совпадение по колонке «Отделение» в нормализованном журнале."""
    names = {str(d).strip() for d in departments if str(d).strip()}
    if not names or ops is None or getattr(ops, "empty", True) or "Отделение" not in ops.columns:
        return ops.iloc[0:0].copy() if ops is not None else pd.DataFrame()
    col = ops["Отделение"].astype(str).str.strip()
    return ops.loc[col.isin(names)].copy()


def format_ops_department_scope_label(
    scope: str,
    *,
    department: str = "",
    departments: Sequence[str] | None = None,
    departments_total: int = 0,
) -> str:
    if scope == "all":
        return f"все отделения ({departments_total})"
    if scope == "multi":
        deps = [str(d).strip() for d in (departments or []) if str(d).strip()]
        if not deps:
            return "выбранные отделения"
        if len(deps) <= 3:
            return "; ".join(deps)
        return f"{len(deps)} отделений из {departments_total}"
    return department.strip()


def ops_violations_summary(
    *,
    long_count: int,
    missing_table_count: int,
    long_op_hours: float,
) -> list[dict[str, Any]]:
    """Сводка количеств по типам нарушений (для мульти-отделения)."""
    return [
        {
            "Тип нарушения": f"Длительные (>{float(long_op_hours):g} ч)",
            "Количество": int(long_count),
        },
        {
            "Тип нарушения": "Без опер.стола",
            "Количество": int(missing_table_count),
        },
    ]


def _base_row(r: pd.Series, *, reason: str, hours: Any = None) -> dict[str, Any]:
    return {
        "КВС": _fmt_kvs(r.get("КВС")),
        "Пациент": _clean_text(r.get("Пациент")),
        "Хирург": _clean_text(r.get("Хирург")) or "Не указан",
        "Услуга": _clean_text(r.get("Услуга")),
        "Длительность": _fmt_hours(hours if hours is not None else r.get("Длительность_ч")),
        "Причина": reason,
        "Опер.стол": _clean_text(r.get("Опер.стол")),
        "Отделение": _clean_text(r.get("Отделение")),
    }


def find_long_operations(
    ops: pd.DataFrame,
    *,
    max_hours: float = DEFAULT_LONG_OP_HOURS,
) -> list[dict[str, Any]]:
    """Операции с длительностью строго больше max_hours (как в отчёте, в т.ч. ошибочные даты)."""
    if ops is None or getattr(ops, "empty", True):
        return []
    if "Длительность_ч" not in ops.columns:
        return []
    thr = float(max_hours)
    out: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for _, r in ops.iterrows():
        hours = r.get("Длительность_ч")
        if hours is None or (isinstance(hours, float) and pd.isna(hours)):
            continue
        try:
            h = float(hours)
        except (TypeError, ValueError):
            continue
        if h <= thr:
            continue
        key = (
            _fmt_kvs(r.get("КВС")),
            str(r.get("Услуга") or "")[:80],
            _fmt_hours(h),
            str(r.get("Начало") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        start = r.get("Начало")
        end = r.get("Конец")
        date_mismatch = False
        try:
            if start is not None and end is not None and not pd.isna(start) and not pd.isna(end):
                date_mismatch = pd.Timestamp(start).normalize() != pd.Timestamp(end).normalize()
        except Exception:
            pass
        reason = f"длительность > {thr:g} ч"
        if date_mismatch:
            reason += " (даты начала и окончания различаются)"
        out.append(_base_row(r, reason=reason, hours=h))
    return out


def find_missing_or_table(ops: pd.DataFrame) -> list[dict[str, Any]]:
    """Услуга есть, а «Опер.стол» пустой."""
    if ops is None or getattr(ops, "empty", True):
        return []
    out: list[dict[str, Any]] = []
    seen: set[tuple] = set()
    for _, r in ops.iterrows():
        service = _clean_text(r.get("Услуга"))
        if not service:
            continue
        # «- не определено» без кода всё равно услуга — стол должен быть
        table = _clean_text(r.get("Опер.стол"))
        if table:
            continue
        key = (_fmt_kvs(r.get("КВС")), service[:80], str(r.get("Дата") or ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(_base_row(r, reason="не занесена на опер.стол"))
    return out


@dataclass
class OpsAnalysisResult:
    file_name: str = ""
    department: str = ""
    scope: str = "single"
    departments_in_scope: list[str] = field(default_factory=list)
    departments_total: int = 0
    total_ops: int = 0
    long_op_hours: float = DEFAULT_LONG_OP_HOURS
    long_ops: list[dict[str, Any]] = field(default_factory=list)
    missing_table: list[dict[str, Any]] = field(default_factory=list)
    violations_summary: list[dict[str, Any]] = field(default_factory=list)
    ops_df: pd.DataFrame | None = None

    @property
    def long_count(self) -> int:
        return len(self.long_ops)

    @property
    def missing_table_count(self) -> int:
        return len(self.missing_table)


def analyze_ops(
    df: pd.DataFrame,
    config: dict[str, Any] | None = None,
    *,
    file_name: str = "",
    department: str | None = None,
    departments: Sequence[str] | None = None,
    scope: str = "single",
) -> OpsAnalysisResult:
    thr = long_op_hours_from_config(config)
    ops = normalize_ops_df(df)
    # drop completely empty rows
    if not ops.empty:
        mask = ops["КВС"].astype(str).str.strip().ne("") | ops["Услуга"].astype(str).str.strip().ne("")
        ops = ops.loc[mask].copy()

    all_depts = (
        sorted(
            {
                str(x).strip()
                for x in (ops["Отделение"].tolist() if "Отделение" in ops.columns else [])
                if str(x).strip()
            },
            key=lambda s: s.lower(),
        )
        if not ops.empty
        else []
    )
    scope_norm = str(scope or "single").strip().lower()
    if scope_norm not in ("single", "multi", "all"):
        scope_norm = "single"

    active: list[str] = []
    if scope_norm == "all":
        active = list(all_depts)
        label = format_ops_department_scope_label(
            "all", departments_total=len(all_depts)
        )
    elif scope_norm == "multi":
        deps = [str(d).strip() for d in (departments or []) if str(d).strip()]
        if not deps:
            raise ValueError("Выберите хотя бы одно отделение")
        ops = filter_ops_by_departments(ops, deps)
        if ops.empty:
            raise ValueError("Нет данных по выбранным отделениям")
        active = deps
        label = format_ops_department_scope_label(
            "multi",
            departments=deps,
            departments_total=len(all_depts),
        )
    else:
        dept = (department or "").strip()
        if dept and not ops.empty and "Отделение" in ops.columns:
            ops = ops.loc[ops["Отделение"].astype(str).str.strip() == dept].copy()
        active = [dept] if dept else []
        label = dept

    long_ops = find_long_operations(ops, max_hours=thr)
    missing = find_missing_or_table(ops)
    return OpsAnalysisResult(
        file_name=file_name,
        department=label,
        scope=scope_norm,
        departments_in_scope=active,
        departments_total=len(all_depts),
        total_ops=int(len(ops)),
        long_op_hours=thr,
        long_ops=long_ops,
        missing_table=missing,
        violations_summary=ops_violations_summary(
            long_count=len(long_ops),
            missing_table_count=len(missing),
            long_op_hours=thr,
        ),
        ops_df=ops,
    )
