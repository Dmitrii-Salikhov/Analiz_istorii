"""JSON-RPC handlers for Electron UI (no Tk)."""

from __future__ import annotations

import math
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from config_store import load_config, push_recent_file, save_config
from excel_io import list_departments, load_ksg_excel, load_lor_excel, pick_default_department
from export_reports import (
    EMK_SECTIONS,
    export_emk_excel,
    export_emk_txt,
    export_ksg_excel,
    export_ksg_txt,
)
from gui.ui_theme import short_month_label
from ksg_analysis import (
    analyze_ksg,
    build_month_comparison,
    load_reference,
    sort_ksg_files_chronologically,
)
from lor_analysis import (
    analyze_lor,
    emk_report_basename,
    filter_by_department,
    format_violations_summary_sections,
    violation_share_table,
)
from updater import read_current_version

# In-memory sessions
_EMK: dict[str, Any] = {
    "path": None,
    "file_name": None,
    "df_full": None,
    "departments": [],
    "department": "",
    "analysis": None,
}
_KSG: dict[str, Any] = {
    "files": [],  # [{name, path, df, results, label}]
    "active": 0,
    "reference": None,
    "reference_status": "",
}


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.isoformat()
    if isinstance(value, pd.Series):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, pd.DataFrame):
        return _df_records(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return str(value)


def _df_records(df: pd.DataFrame | None, limit: int | None = None) -> list[dict[str, Any]]:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return []
    view = df if limit is None else df.head(limit)
    # Pivot / groupby tables keep code+name in the index — include them in records
    if isinstance(view.index, pd.MultiIndex) or view.index.name is not None:
        view = view.reset_index()
    # Flatten MultiIndex columns (rare) to string keys
    if isinstance(view.columns, pd.MultiIndex):
        view = view.copy()
        view.columns = [
            " ".join(str(x) for x in col if x != "").strip() if isinstance(col, tuple) else str(col)
            for col in view.columns
        ]
    records = view.where(pd.notnull(view), None).to_dict(orient="records")
    return [_json_safe(row) for row in records]


def _ensure_ksg_reference() -> tuple[dict, str]:
    if _KSG["reference"] is None:
        ref, status = load_reference()
        _KSG["reference"] = ref
        _KSG["reference_status"] = status
    return _KSG["reference"], _KSG["reference_status"]


def _emk_payload(result, department: str) -> dict[str, Any]:
    share = violation_share_table(result.violations_df)
    viol_df = result.violations_df
    if viol_df is not None and not viol_df.empty and "КВС" in viol_df.columns:
        with_viol = int(viol_df["КВС"].nunique())
    else:
        with_viol = 0
    total = int(result.total_patients or 0)
    without_viol = max(0, total - with_viol)
    return {
        "department": department,
        "file_name": _EMK.get("file_name"),
        "path": _EMK.get("path"),
        "period_start": _json_safe(result.period_start),
        "period_end": _json_safe(result.period_end),
        "report_basename": emk_report_basename(result.period_start, result.period_end),
        "total_patients": result.total_patients,
        "avg_beddays": result.avg_beddays,
        "urgent": result.urgent,
        "planned": result.planned,
        "age_dist": _json_safe(result.age_dist),
        "skp_count": result.skp_count,
        "skp_days_0": result.skp_days_0,
        "skp_days_1": result.skp_days_1,
        "violation_share": _df_records(share),
        "violations": _df_records(result.violations_df, limit=5000),
        "doctor_stats": _df_records(result.doctor_stats),
        "ids_stats": _df_records(result.ids_stats),
        "long_stay": _df_records(result.long_stay, limit=2000),
        "skp_cases": _df_records(result.skp_cases),
        "skp_operations": _df_records(result.skp_operations, limit=5000),
        "violations_total": int(len(result.violations_df)) if result.violations_df is not None else 0,
        "cases_with_violations": with_viol,
        "cases_without_violations": without_viol,
    }


def _ksg_file_summary(item: dict[str, Any]) -> dict[str, Any]:
    r = item.get("results") or {}
    return {
        "name": item.get("name"),
        "path": item.get("path"),
        "label": item.get("label"),
        "total_patients": r.get("total_patients"),
        "total_sum": r.get("total_sum"),
        "avg_kz_total": r.get("avg_kz_total"),
    }


def _ksg_analyze_payload(results: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_patients": results.get("total_patients"),
        "total_sum": results.get("total_sum"),
        "avg_kz_total": results.get("avg_kz_total"),
        "patient_counts": _json_safe(results.get("patient_counts")),
        "sum_by_doctor": _df_records(results.get("sum_by_doctor")),
        "ops_pivot": _df_records(results.get("ops_pivot"), limit=500),
        "unknown_codes": list(results.get("unknown_codes") or [])[:200],
        "low_money": _df_records(results.get("low_money"), limit=2000),
        "high_money": _df_records(results.get("high_money"), limit=2000),
        "no_service": _df_records(results.get("no_service"), limit=2000),
        "kslp_issues": _df_records(results.get("kslp_issues"), limit=2000),
        "age_dist": _json_safe(results.get("age_dist")),
        "age_sum": _json_safe(results.get("age_sum")),
        "age_kz": _json_safe(results.get("age_kz")),
        "avg_kz_doctor": _df_records(results.get("avg_kz_doctor")),
        "thresholds": results.get("thresholds"),
        "kslp_settings": results.get("kslp_settings"),
    }


def ping(_params: dict[str, Any]) -> dict[str, Any]:
    return {"ok": True, "service": "analiz-istorii"}


def app_version(_params: dict[str, Any]) -> dict[str, Any]:
    return {"version": read_current_version()}


def config_get(_params: dict[str, Any]) -> dict[str, Any]:
    return {"config": load_config()}


def config_set(params: dict[str, Any]) -> dict[str, Any]:
    patch = params.get("config") or {}
    if not isinstance(patch, dict):
        raise ValueError("config must be an object")
    cfg = load_config()
    cfg.update(patch)
    preferred = str(cfg.get("preferred_department") or "").strip()
    if preferred:
        known = list(cfg.get("known_departments") or [])
        if preferred not in known:
            known.insert(0, preferred)
            cfg["known_departments"] = known
    save_config(cfg)
    return {"config": cfg}


def emk_load(params: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(params.get("path") or "")).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")
    loaded = load_lor_excel(str(path))
    df = loaded.dataframe
    departments = list_departments(df)
    cfg = load_config()
    preferred = pick_default_department(departments, cfg.get("preferred_department"))
    known = list(cfg.get("known_departments") or [])
    for d in departments:
        if d and d not in known:
            known.append(d)
    cfg["known_departments"] = known
    _EMK["path"] = str(path)
    _EMK["file_name"] = path.name
    _EMK["df_full"] = df
    _EMK["departments"] = departments
    _EMK["analysis"] = None
    _EMK["department"] = ""
    push_recent_file(cfg, "recent_emk", str(path))
    save_config(cfg)
    return {
        "path": str(path),
        "file_name": path.name,
        "departments": departments,
        "preferred_department": preferred,
        "known_departments": known,
        "rows": int(len(df)),
        "sheet_name": loaded.sheet_name,
    }


def emk_analyze(params: dict[str, Any]) -> dict[str, Any]:
    if _EMK["df_full"] is None:
        raise RuntimeError("Сначала загрузите файл ЭМК")
    department = str(params.get("department") or "").strip()
    df = filter_by_department(_EMK["df_full"], department or None)
    cfg = load_config()
    result = analyze_lor(df, cfg)
    _EMK["analysis"] = result
    _EMK["department"] = department
    payload = _emk_payload(result, department)
    payload["long_stay_days"] = int(cfg.get("long_stay_days", 7))
    payload["violations_summary"] = format_violations_summary_sections(
        result.violations_df,
        long_stay_days=int(cfg.get("long_stay_days", 7)),
    )
    return payload


def emk_violations_summary(_params: dict[str, Any]) -> dict[str, Any]:
    result = _EMK.get("analysis")
    if result is None:
        raise RuntimeError("Сначала выполните анализ ЭМК")
    cfg = load_config()
    days = int(cfg.get("long_stay_days", 7))
    return {
        "long_stay_days": days,
        "sections": format_violations_summary_sections(
            result.violations_df, long_stay_days=days
        ),
    }


def emk_export(params: dict[str, Any]) -> dict[str, Any]:
    result = _EMK.get("analysis")
    if result is None:
        raise RuntimeError("Сначала выполните анализ ЭМК")
    fmt = str(params.get("format") or "xlsx").lower()
    path = Path(str(params.get("path") or "")).expanduser()
    if not path.parent.exists():
        raise FileNotFoundError(f"Папка не найдена: {path.parent}")
    sections = params.get("sections")
    if sections is not None and not isinstance(sections, dict):
        raise ValueError("sections must be an object")
    file_name = str(_EMK.get("file_name") or "")
    department = str(_EMK.get("department") or "")
    if fmt in ("txt", "text"):
        saved = export_emk_txt(
            path, result, file_name=file_name, department=department, sections=sections
        )
    else:
        saved = export_emk_excel(
            path, result, file_name=file_name, department=department, sections=sections
        )
    return {"path": saved, "format": "txt" if fmt in ("txt", "text") else "xlsx"}


def emk_sections(_params: dict[str, Any]) -> dict[str, Any]:
    return {"sections": list(EMK_SECTIONS)}


def ksg_load(params: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(params.get("path") or "")).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Файл не найден: {path}")
    df = load_ksg_excel(str(path))
    ref, status = _ensure_ksg_reference()
    cfg = load_config()
    results = analyze_ksg(df, ref, cfg)
    label = short_month_label(path.name, df)
    item = {
        "name": path.name,
        "path": str(path),
        "df": df,
        "results": results,
        "label": label,
    }
    # replace if same path
    files = [f for f in _KSG["files"] if f.get("path") != str(path)]
    files.append(item)
    _KSG["files"] = sort_ksg_files_chronologically(files)
    _KSG["active"] = next(
        (i for i, f in enumerate(_KSG["files"]) if f.get("path") == str(path)),
        len(_KSG["files"]) - 1,
    )
    push_recent_file(cfg, "recent_ksg", str(path))
    save_config(cfg)
    return {
        "files": [_ksg_file_summary(f) for f in _KSG["files"]],
        "active": _KSG["active"],
        "reference_status": status,
        "analysis": _ksg_analyze_payload(results),
    }


def ksg_list(_params: dict[str, Any]) -> dict[str, Any]:
    _ensure_ksg_reference()
    return {
        "files": [_ksg_file_summary(f) for f in _KSG["files"]],
        "active": _KSG["active"],
        "reference_status": _KSG["reference_status"],
    }


def ksg_set_active(params: dict[str, Any]) -> dict[str, Any]:
    idx = int(params.get("index", 0))
    if idx < 0 or idx >= len(_KSG["files"]):
        raise IndexError("Неверный индекс файла КСГ")
    _KSG["active"] = idx
    item = _KSG["files"][idx]
    return {
        "active": idx,
        "file": _ksg_file_summary(item),
        "analysis": _ksg_analyze_payload(item["results"]),
    }


def ksg_remove(params: dict[str, Any]) -> dict[str, Any]:
    idx = int(params.get("index", -1))
    if idx < 0 or idx >= len(_KSG["files"]):
        raise IndexError("Неверный индекс файла КСГ")
    _KSG["files"].pop(idx)
    if _KSG["files"]:
        _KSG["active"] = min(_KSG["active"], len(_KSG["files"]) - 1)
    else:
        _KSG["active"] = 0
    return ksg_list({})


def ksg_reanalyze(_params: dict[str, Any]) -> dict[str, Any]:
    ref, status = _ensure_ksg_reference()
    cfg = load_config()
    for item in _KSG["files"]:
        item["results"] = analyze_ksg(item["df"], ref, cfg)
        item["label"] = short_month_label(item["name"], item["df"])
    active = _KSG["files"][_KSG["active"]] if _KSG["files"] else None
    return {
        "files": [_ksg_file_summary(f) for f in _KSG["files"]],
        "active": _KSG["active"],
        "reference_status": status,
        "analysis": _ksg_analyze_payload(active["results"]) if active else None,
    }


def ksg_export(params: dict[str, Any]) -> dict[str, Any]:
    if not _KSG["files"]:
        raise RuntimeError("Сначала загрузите файл КСГ")
    idx = int(params.get("index", _KSG["active"]))
    if idx < 0 or idx >= len(_KSG["files"]):
        raise IndexError("Неверный индекс файла КСГ")
    item = _KSG["files"][idx]
    fmt = str(params.get("format") or "xlsx").lower()
    path = Path(str(params.get("path") or "")).expanduser()
    if not path.parent.exists():
        raise FileNotFoundError(f"Папка не найдена: {path.parent}")
    cfg = load_config()
    if fmt in ("txt", "text"):
        saved = export_ksg_txt(
            path, item["results"], file_name=item["name"], settings=cfg
        )
    else:
        saved = export_ksg_excel(path, item["results"], file_name=item["name"])
    return {"path": saved, "format": "txt" if fmt in ("txt", "text") else "xlsx"}


def ksg_compare(params: dict[str, Any]) -> dict[str, Any]:
    indices = params.get("indices")
    if indices is None:
        selected = list(_KSG["files"])
    else:
        selected = [_KSG["files"][int(i)] for i in indices]
    if len(selected) < 2:
        raise ValueError("Для сравнения нужно минимум 2 файла")
    summary = build_month_comparison(selected)
    sorted_files = summary.get("files") or selected
    return {
        "labels": [f.get("label") or f.get("name") for f in sorted_files],
        "names": summary.get("names"),
        "total_patients": summary.get("total_patients"),
        "total_sum": summary.get("total_sum"),
        "avg_kz": summary.get("avg_kz"),
        "kslp_issues": summary.get("kslp_issues"),
        "doctors": summary.get("doctors"),
        "doctor_sums": _json_safe(summary.get("doctor_sums")),
    }


def ref_operations(_params: dict[str, Any]) -> dict[str, Any]:
    ref, status = _ensure_ksg_reference()
    items = [
        {"code": code, "name": name, "group": group}
        for code, (name, group) in sorted(ref.items(), key=lambda x: x[0])
    ]
    return {"items": items, "status": status}


def ref_departments(_params: dict[str, Any]) -> dict[str, Any]:
    cfg = load_config()
    known = list(cfg.get("known_departments") or [])
    session = list(_EMK.get("departments") or [])
    merged: list[str] = []
    for d in session + known:
        if d and d not in merged:
            merged.append(d)
    preferred = cfg.get("preferred_department") or ""
    if preferred and preferred not in merged:
        merged.insert(0, preferred)
    return {"departments": merged, "preferred": preferred}


HANDLERS = {
    "ping": ping,
    "app.version": app_version,
    "config.get": config_get,
    "config.set": config_set,
    "ref.operations": ref_operations,
    "ref.departments": ref_departments,
    "emk.load": emk_load,
    "emk.analyze": emk_analyze,
    "emk.export": emk_export,
    "emk.sections": emk_sections,
    "emk.violationsSummary": emk_violations_summary,
    "ksg.load": ksg_load,
    "ksg.list": ksg_list,
    "ksg.setActive": ksg_set_active,
    "ksg.remove": ksg_remove,
    "ksg.reanalyze": ksg_reanalyze,
    "ksg.compare": ksg_compare,
    "ksg.export": ksg_export,
}


def dispatch(method: str | None, params: dict[str, Any]) -> Any:
    if not method or method not in HANDLERS:
        raise ValueError(f"Unknown method: {method}")
    return HANDLERS[method](params)
