"""JSON-RPC handlers for Electron UI (no Tk)."""

from __future__ import annotations

import math
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from config_store import load_config, push_recent_file, save_config
from excel_io import (
    list_departments,
    load_ksg_excel,
    load_lor_excel,
    load_ops_excel,
    pick_default_department,
)
from report_profiles import get_active_profile
from export_reports import (
    EMK_SECTIONS,
    export_emk_excel,
    export_emk_txt,
    export_ksg_excel,
    export_ksg_txt,
    export_ops_excel,
    export_ops_txt,
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
    cases_coverage_by_snils,
    cases_coverage_lists,
    emk_report_basename,
    filter_by_department,
    filter_by_departments,
    format_department_scope_label,
    format_violations_summary_sections,
    snils_column_available,
    violation_share_table,
    violation_share_table_by_snils,
    EMK_VARIANT_CURRENT,
    EMK_VARIANT_DISCHARGED,
)
from ops_analysis import analyze_ops, list_ops_departments
from updater import read_current_version

# In-memory sessions
_EMK: dict[str, Any] = {
    "path": None,
    "file_name": None,
    "df_full": None,
    "departments": [],
    "department": "",
    "scope": "single",
    "departments_selected": [],
    "analysis": None,
    "emk_variant": EMK_VARIANT_DISCHARGED,
    "as_of": None,
}
_KSG: dict[str, Any] = {
    "files": [],  # [{name, path, df, results, label}]
    "active": 0,
    "reference": None,
    "reference_status": "",
}
_OPS: dict[str, Any] = {
    "path": None,
    "file_name": None,
    "df": None,
    "analysis": None,
    "departments": [],
    "department": "",
    "scope": "single",
    "departments_selected": [],
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


def _case_list_records(rows: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    if not rows:
        return []
    return _df_records(pd.DataFrame(rows), limit=5000)


def _ensure_ksg_reference() -> tuple[dict, str]:
    if _KSG["reference"] is None:
        ref, status = load_reference()
        _KSG["reference"] = ref
        _KSG["reference_status"] = status
    return _KSG["reference"], _KSG["reference_status"]


def _parse_as_of(raw: Any) -> date | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError as exc:
        raise ValueError("as_of: ожидается дата в формате ГГГГ-ММ-ДД") from exc


def _emk_payload(
    result,
    department_label: str,
    *,
    scope: str,
    departments_in_scope: list[str],
    departments_total: int,
    emk_variant: str,
    as_of: date | None = None,
) -> dict[str, Any]:
    share = violation_share_table(result.violations_df)
    share_snils = violation_share_table_by_snils(result.violations_df)
    viol_df = result.violations_df
    if viol_df is not None and not viol_df.empty and "КВС" in viol_df.columns:
        with_viol = int(viol_df["КВС"].nunique())
    else:
        with_viol = 0
    total = int(result.total_patients or 0)
    without_viol = max(0, total - with_viol)
    snils_ok = snils_column_available(result.df)
    coverage_snils = cases_coverage_by_snils(result.df, viol_df) if snils_ok else None
    coverage_lists = cases_coverage_lists(result.df, viol_df)
    # В UI-таблице нарушений служебный флаг есть_СНИЛС не показываем
    viol_for_ui = viol_df
    if viol_df is not None and not viol_df.empty and "есть_СНИЛС" in viol_df.columns:
        viol_for_ui = viol_df.drop(columns=["есть_СНИЛС"])
    from excel_io import EMK_VARIANT_LABELS

    coverage_counts = None
    coverage_snils_lists = None
    if coverage_snils:
        coverage_snils_lists = coverage_snils.get("lists")
        coverage_counts = {
            "with_violations_snils": coverage_snils["with_violations_snils"],
            "with_violations_no_snils": coverage_snils["with_violations_no_snils"],
            "without_violations_snils": coverage_snils["without_violations_snils"],
            "without_violations_no_snils": coverage_snils["without_violations_no_snils"],
        }

    return {
        "department": department_label,
        "scope": scope,
        "departments_in_scope": departments_in_scope,
        "departments_total": departments_total,
        "emk_variant": emk_variant,
        "emk_variant_label": EMK_VARIANT_LABELS.get(emk_variant, emk_variant),
        "as_of": _json_safe(as_of or result.period_end),
        "file_name": _EMK.get("file_name"),
        "path": _EMK.get("path"),
        "period_start": _json_safe(result.period_start),
        "period_end": _json_safe(result.period_end),
        "report_basename": emk_report_basename(
            result.period_start,
            result.period_end,
            emk_variant=emk_variant,
            as_of=as_of,
        ),
        "total_patients": result.total_patients,
        "avg_beddays": result.avg_beddays,
        "urgent": result.urgent,
        "planned": result.planned,
        "age_dist": _json_safe(result.age_dist),
        "skp_count": result.skp_count,
        "skp_days_0": result.skp_days_0,
        "skp_days_1": result.skp_days_1,
        "snils_available": snils_ok,
        "violation_share": _df_records(share),
        "violation_share_by_snils": _df_records(share_snils),
        "violations": _df_records(viol_for_ui, limit=5000),
        "doctor_stats": _df_records(result.doctor_stats),
        "ids_stats": _df_records(result.ids_stats),
        "long_stay": _df_records(result.long_stay, limit=2000),
        "skp_cases": _df_records(result.skp_cases),
        "skp_operations": _df_records(result.skp_operations, limit=5000),
        "violations_total": int(len(result.violations_df)) if result.violations_df is not None else 0,
        "cases_with_violations": with_viol,
        "cases_without_violations": without_viol,
        "cases_coverage_by_snils": coverage_counts,
        "cases_coverage_lists": {
            "with_violations": _case_list_records(coverage_lists.get("with_violations")),
            "without_violations": _case_list_records(coverage_lists.get("without_violations")),
            "with_violations_snils": _case_list_records(
                (coverage_snils_lists or {}).get("with_violations_snils")
            ),
            "with_violations_no_snils": _case_list_records(
                (coverage_snils_lists or {}).get("with_violations_no_snils")
            ),
            "without_violations_snils": _case_list_records(
                (coverage_snils_lists or {}).get("without_violations_snils")
            ),
            "without_violations_no_snils": _case_list_records(
                (coverage_snils_lists or {}).get("without_violations_no_snils")
            ),
        },
    }


def _parse_emk_scope(params: dict[str, Any]) -> tuple[str, str, list[str]]:
    scope = str(params.get("scope") or "single").strip().lower()
    if scope not in ("single", "multi", "all"):
        scope = "single"
    department = str(params.get("department") or "").strip()
    raw_deps = params.get("departments")
    departments: list[str] = []
    if isinstance(raw_deps, list):
        departments = [str(d).strip() for d in raw_deps if str(d).strip()]
    return scope, department, departments


def _emk_filter_dataframe(
    df_full: pd.DataFrame,
    scope: str,
    department: str,
    departments: list[str],
) -> tuple[pd.DataFrame, list[str]]:
    all_depts = list_departments(df_full)
    if scope == "all":
        return df_full.copy(), all_depts
    if scope == "multi":
        if not departments:
            raise ValueError("Выберите хотя бы одно отделение")
        filtered = filter_by_departments(df_full, departments)
        if filtered.empty:
            raise ValueError("Нет данных по выбранным отделениям")
        return filtered, departments
    filtered = filter_by_department(df_full, department or None)
    if filtered.empty and department:
        raise ValueError(f"Нет данных по отделению «{department}»")
    active = [department] if department else []
    return filtered, active


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


def app_changelog(_params: dict[str, Any]) -> dict[str, Any]:
    from changelog import CHANGELOG

    return {"entries": CHANGELOG[:8]}


def config_get(_params: dict[str, Any]) -> dict[str, Any]:
    return {"config": load_config()}


# Keys the Electron UI may update via config.set (defense in depth).
_CONFIG_SET_ALLOWED = frozenset(
    {
        "date_format",
        "theme",
        "ksg_threshold_low",
        "ksg_threshold_high",
        "kslp_age_min",
        "kslp_age_max",
        "kslp_senior_age",
        "long_stay_days",
        "long_op_hours",
        "kslp_operations_codes",
        "kslp_rules",
        "preferred_department",
        "known_departments",
        "github_repo",
        "check_updates_on_start",
        "emk_display",
        "emk_info_checks",
        "ksg_display",
        "ui_prefs",
        "last_main_tab",
        "window_geometry",
        "report_profiles",
    }
)


def _validate_github_repo(value: Any) -> str:
    repo = str(value or "").strip()
    if not repo:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("github_repo: ожидается формат owner/repo")
    return repo


def config_set(params: dict[str, Any]) -> dict[str, Any]:
    patch = params.get("config") or {}
    if not isinstance(patch, dict):
        raise ValueError("config must be an object")
    cfg = load_config()
    for key, value in patch.items():
        if key not in _CONFIG_SET_ALLOWED:
            continue
        if key == "github_repo":
            cfg[key] = _validate_github_repo(value)
        elif key in ("emk_display", "emk_info_checks", "ksg_display", "ui_prefs") and not isinstance(
            value, dict
        ):
            raise ValueError(f"{key} must be an object")
        elif key == "kslp_rules" and not isinstance(value, list):
            raise ValueError("kslp_rules must be a list")
        elif key == "report_profiles" and not isinstance(value, dict):
            raise ValueError("report_profiles must be an object")
        else:
            cfg[key] = value
    preferred = str(cfg.get("preferred_department") or "").strip()
    if preferred:
        known = list(cfg.get("known_departments") or [])
        if preferred not in known:
            known.insert(0, preferred)
            cfg["known_departments"] = known
    save_config(cfg)
    return {"config": cfg}


def emk_load(params: dict[str, Any]) -> dict[str, Any]:
    path = _assert_excel_path(params.get("path"))
    cfg = load_config()
    profile = get_active_profile(cfg, "emk")
    loaded = load_lor_excel(str(path), profile=profile, config=cfg)
    df = loaded.dataframe
    variant = loaded.emk_variant or EMK_VARIANT_DISCHARGED
    if variant == EMK_VARIANT_CURRENT:
        from lor_analysis import collapse_current_patients_to_unique_kvs

        departments = list_departments(collapse_current_patients_to_unique_kvs(df))
    else:
        departments = list_departments(df)
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
    _EMK["scope"] = "single"
    _EMK["departments_selected"] = []
    _EMK["emk_variant"] = variant
    _EMK["as_of"] = None
    push_recent_file(cfg, "recent_emk", str(path))
    save_config(cfg)
    mapping = loaded.mapping.to_dict() if loaded.mapping else None
    from excel_io import EMK_VARIANT_LABELS

    return {
        "path": str(path),
        "file_name": path.name,
        "departments": departments,
        "preferred_department": preferred,
        "known_departments": known,
        "rows": int(len(df)),
        "sheet_name": loaded.sheet_name,
        "profile_id": profile.get("id"),
        "profile_name": profile.get("name"),
        "mapping": mapping,
        "emk_variant": variant,
        "emk_variant_label": EMK_VARIANT_LABELS.get(variant, variant),
    }


def emk_analyze(params: dict[str, Any]) -> dict[str, Any]:
    if _EMK["df_full"] is None:
        raise RuntimeError("Сначала загрузите файл ЭМК")
    df_full = _EMK["df_full"]
    all_depts = list_departments(df_full)
    scope, department, departments = _parse_emk_scope(params)
    df, departments_in_scope = _emk_filter_dataframe(df_full, scope, department, departments)
    cfg = load_config()
    variant = str(_EMK.get("emk_variant") or EMK_VARIANT_DISCHARGED)
    as_of = _parse_as_of(params.get("as_of"))
    if as_of is None and isinstance(_EMK.get("as_of"), date):
        as_of = _EMK["as_of"]
    if variant == EMK_VARIANT_CURRENT and as_of is None:
        as_of = date.today()
    result = analyze_lor(df, cfg, emk_variant=variant, as_of=as_of)
    department_label = format_department_scope_label(
        scope,
        department=department,
        departments=departments_in_scope,
        departments_total=len(all_depts),
    )
    _EMK["analysis"] = result
    _EMK["department"] = department_label
    _EMK["scope"] = scope
    _EMK["departments_selected"] = list(departments_in_scope)
    _EMK["as_of"] = as_of
    group_by_department = scope in ("multi", "all")
    long_stay_days = int(cfg.get("long_stay_days", 7))
    payload = _emk_payload(
        result,
        department_label,
        scope=scope,
        departments_in_scope=departments_in_scope,
        departments_total=len(all_depts),
        emk_variant=variant,
        as_of=as_of,
    )
    payload["long_stay_days"] = long_stay_days
    payload["violations_summary"] = format_violations_summary_sections(
        result.violations_df,
        long_stay_days=long_stay_days,
        group_by_department=group_by_department,
        department_order=departments_in_scope if group_by_department else None,
    )
    return payload


def emk_violations_summary(_params: dict[str, Any]) -> dict[str, Any]:
    result = _EMK.get("analysis")
    if result is None:
        raise RuntimeError("Сначала выполните анализ ЭМК")
    cfg = load_config()
    days = int(cfg.get("long_stay_days", 7))
    scope = str(_EMK.get("scope") or "single")
    group_by_department = scope in ("multi", "all")
    dept_order = _EMK.get("departments_selected") if group_by_department else None
    return {
        "long_stay_days": days,
        "sections": format_violations_summary_sections(
            result.violations_df,
            long_stay_days=days,
            group_by_department=group_by_department,
            department_order=dept_order if isinstance(dept_order, list) else None,
        ),
    }


def _assert_excel_path(raw: Any) -> Path:
    path = Path(str(raw or "")).expanduser().resolve()
    if path.suffix.lower() not in {".xlsx", ".xls", ".xlsm"}:
        raise ValueError("Разрешены только файлы Excel (.xlsx / .xls)")
    if not path.is_file():
        raise FileNotFoundError(f"Файл не найден: {path}")
    return path


def _assert_export_path(raw: Any) -> Path:
    path = Path(str(raw or "")).expanduser().resolve()
    if path.suffix.lower() not in {".xlsx", ".txt"}:
        raise ValueError("Разрешены только .xlsx или .txt")
    if not path.parent.is_dir():
        raise FileNotFoundError(f"Папка не найдена: {path.parent}")
    return path


def emk_export(params: dict[str, Any]) -> dict[str, Any]:
    result = _EMK.get("analysis")
    if result is None:
        raise RuntimeError("Сначала выполните анализ ЭМК")
    fmt = str(params.get("format") or "xlsx").lower()
    path = _assert_export_path(params.get("path"))
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
    path = _assert_excel_path(params.get("path"))
    cfg = load_config()
    profile = get_active_profile(cfg, "ksg")
    loaded = load_ksg_excel(str(path), profile=profile, config=cfg)
    df = loaded.dataframe
    ref, status = _ensure_ksg_reference()
    results = analyze_ksg(df, ref, cfg)
    label = short_month_label(path.name, df)
    item = {
        "name": path.name,
        "path": str(path),
        "df": df,
        "results": results,
        "label": label,
        "mapping": loaded.mapping.to_dict() if loaded.mapping else None,
        "profile_id": profile.get("id"),
        "profile_name": profile.get("name"),
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
        "profile_id": profile.get("id"),
        "profile_name": profile.get("name"),
        "mapping": loaded.mapping.to_dict() if loaded.mapping else None,
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
    path = _assert_export_path(params.get("path"))
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
    session = list(_EMK.get("departments") or []) + list(_OPS.get("departments") or [])
    merged: list[str] = []
    for d in session + known:
        if d and d not in merged:
            merged.append(d)
    preferred = cfg.get("preferred_department") or ""
    if preferred and preferred not in merged:
        merged.insert(0, preferred)
    return {"departments": merged, "preferred": preferred}


def _ops_payload(result) -> dict[str, Any]:
    return {
        "file_name": result.file_name or _OPS.get("file_name"),
        "path": _OPS.get("path"),
        "department": result.department or _OPS.get("department") or "",
        "departments": list(_OPS.get("departments") or []),
        "scope": getattr(result, "scope", None) or _OPS.get("scope") or "single",
        "departments_in_scope": list(getattr(result, "departments_in_scope", None) or []),
        "departments_total": int(getattr(result, "departments_total", 0) or 0),
        "total_ops": result.total_ops,
        "long_op_hours": result.long_op_hours,
        "long_count": result.long_count,
        "missing_table_count": result.missing_table_count,
        "long_ops": _json_safe(result.long_ops),
        "missing_table": _json_safe(result.missing_table),
        "violations_summary": _json_safe(
            getattr(result, "violations_summary", None) or []
        ),
    }


def _parse_ops_scope(params: dict[str, Any]) -> tuple[str, str, list[str]]:
    scope = str(params.get("scope") or "single").strip().lower()
    if scope not in ("single", "multi", "all"):
        scope = "single"
    department = str(params.get("department") or "").strip()
    raw_deps = params.get("departments")
    departments: list[str] = []
    if isinstance(raw_deps, list):
        departments = [str(d).strip() for d in raw_deps if str(d).strip()]
    return scope, department, departments


def ops_load(params: dict[str, Any]) -> dict[str, Any]:
    path = _assert_excel_path(params.get("path"))
    cfg = load_config()
    profile = get_active_profile(cfg, "ops")
    loaded = load_ops_excel(str(path), profile=profile, config=cfg)
    df = loaded.dataframe
    departments = list_ops_departments(df)
    preferred = pick_default_department(departments, cfg.get("preferred_department")) or ""
    if not preferred and departments:
        preferred = departments[0]
    # merge into known departments for settings
    known = list(cfg.get("known_departments") or [])
    for d in departments:
        if d and d not in known:
            known.append(d)
    cfg["known_departments"] = known
    result = analyze_ops(
        df,
        cfg,
        file_name=path.name,
        department=preferred or None,
        scope="single",
    )
    _OPS["path"] = str(path)
    _OPS["file_name"] = path.name
    _OPS["df"] = df
    _OPS["departments"] = departments
    _OPS["department"] = preferred
    _OPS["scope"] = "single"
    _OPS["departments_selected"] = []
    _OPS["analysis"] = result
    push_recent_file(cfg, "recent_ops", str(path))
    save_config(cfg)
    payload = _ops_payload(result)
    payload.update(
        {
            "profile_id": profile.get("id"),
            "profile_name": profile.get("name"),
            "mapping": loaded.mapping.to_dict() if loaded.mapping else None,
            "rows": int(len(df)),
            "sheet_name": loaded.sheet_name,
            "preferred_department": preferred,
            "known_departments": known,
        }
    )
    return payload


def ops_analyze(params: dict[str, Any]) -> dict[str, Any]:
    if _OPS.get("df") is None:
        raise RuntimeError("Сначала загрузите файл операций")
    cfg = load_config()
    scope, department, departments = _parse_ops_scope(params)
    if scope == "single":
        if not department:
            department = str(_OPS.get("department") or "").strip()
        if department:
            _OPS["department"] = department
        _OPS["scope"] = "single"
        _OPS["departments_selected"] = []
    elif scope == "multi":
        if not departments:
            raise ValueError("Выберите хотя бы одно отделение")
        _OPS["scope"] = "multi"
        _OPS["departments_selected"] = departments
    else:
        _OPS["scope"] = "all"
        _OPS["departments_selected"] = list(_OPS.get("departments") or [])

    result = analyze_ops(
        _OPS["df"],
        cfg,
        file_name=str(_OPS.get("file_name") or ""),
        department=department or None,
        departments=departments if scope == "multi" else None,
        scope=scope,
    )
    _OPS["analysis"] = result
    return _ops_payload(result)


def ops_export(params: dict[str, Any]) -> dict[str, Any]:
    result = _OPS.get("analysis")
    if result is None:
        raise RuntimeError("Сначала загрузите и проанализируйте файл операций")
    fmt = str(params.get("format") or "xlsx").lower()
    path = _assert_export_path(params.get("path"))
    file_name = str(_OPS.get("file_name") or "")
    if fmt in ("txt", "text"):
        saved = export_ops_txt(path, result, file_name=file_name)
    else:
        saved = export_ops_excel(path, result, file_name=file_name)
    return {"path": saved, "format": "txt" if fmt in ("txt", "text") else "xlsx"}


HANDLERS = {
    "ping": ping,
    "app.version": app_version,
    "app.changelog": app_changelog,
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
    "ops.load": ops_load,
    "ops.analyze": ops_analyze,
    "ops.export": ops_export,
}


def dispatch(method: str | None, params: dict[str, Any]) -> Any:
    if not method or method not in HANDLERS:
        raise ValueError(f"Unknown method: {method}")
    return HANDLERS[method](params)
