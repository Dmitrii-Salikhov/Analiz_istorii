"""Профили проверки КСЛП для отделений КСГ."""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from ksg_departments import is_lor_department, parse_ksg_department

BUILTIN_LOR = "lor"
BUILTIN_STANDARD = "standard"
BUILTIN_NONE = "none"

DEFAULT_KSG_KSLP_PROFILES: dict[str, dict[str, Any]] = {
    BUILTIN_LOR: {
        "id": BUILTIN_LOR,
        "name": "ЛОР",
        "builtin": True,
        "mode": "rules",
        "age_min": 0,
        "age_max": 4,
        "senior_age": 75,
        "rules": [],
    },
    BUILTIN_STANDARD: {
        "id": BUILTIN_STANDARD,
        "name": "Стандарт",
        "builtin": True,
        "mode": "age_only",
        "age_min": 0,
        "age_max": 4,
        "senior_age": 75,
        "rules": [],
    },
    BUILTIN_NONE: {
        "id": BUILTIN_NONE,
        "name": "Без проверок",
        "builtin": True,
        "mode": "none",
        "age_min": 0,
        "age_max": 4,
        "senior_age": 75,
        "rules": [],
    },
}


def _normalize_rules(raw: Any) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return rules
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        codes = [str(c).strip() for c in (item.get("codes") or []) if str(c).strip()]
        if not codes:
            continue
        rid = str(item.get("id") or f"rule-{i + 1}")
        name = str(item.get("name") or f"Правило {i + 1}").strip() or f"Правило {i + 1}"
        rules.append({"id": rid, "name": name, "codes": codes})
    return rules


def normalize_ksg_kslp_profiles(cfg: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    profiles: dict[str, dict[str, Any]] = deepcopy(DEFAULT_KSG_KSLP_PROFILES)
    raw = cfg.get("ksg_kslp_profiles")
    if isinstance(raw, dict):
        for pid, item in raw.items():
            if not isinstance(item, dict):
                continue
            key = str(item.get("id") or pid).strip()
            if not key:
                continue
            base = deepcopy(profiles.get(key, {}))
            base.update(item)
            base["id"] = key
            base["name"] = str(base.get("name") or key).strip() or key
            base["rules"] = _normalize_rules(base.get("rules"))
            profiles[key] = base

    lor = profiles[BUILTIN_LOR]
    if not lor.get("rules"):
        legacy_rules = cfg.get("kslp_rules")
        if isinstance(legacy_rules, list) and legacy_rules:
            lor["rules"] = _normalize_rules(legacy_rules)
        else:
            legacy_codes = cfg.get("kslp_operations_codes") or []
            codes = [str(c).strip() for c in legacy_codes if str(c).strip()]
            if codes:
                lor["rules"] = [{"id": "lor-default", "name": "Операции ЛОР", "codes": codes}]
    profiles[BUILTIN_LOR] = lor
    return profiles


def default_profile_for_department(name: str, code: str | None = None) -> str:
    if is_lor_department(name, code):
        return BUILTIN_LOR
    return BUILTIN_STANDARD


def normalize_department_profile_map(
    cfg: Mapping[str, Any],
    departments: list[str],
    df_department_meta: Mapping[str, tuple[str | None, str]] | None = None,
) -> dict[str, str]:
    """Ключ — нормализованное имя отделения; значение — id профиля."""
    stored = cfg.get("ksg_department_profiles")
    mapping: dict[str, str] = {}
    if isinstance(stored, dict):
        for key, val in stored.items():
            dep_key = str(key).strip()
            pid = str(val or "").strip()
            if dep_key and pid:
                mapping[dep_key] = pid

    meta = df_department_meta or {}
    for dep in departments:
        dep = str(dep).strip()
        if not dep or dep in mapping:
            continue
        code, name, _ = parse_ksg_department(dep)
        norm = name or dep
        if norm in mapping:
            continue
        code_hint = code
        if dep in meta:
            code_hint = meta[dep][0]
            norm = meta[dep][1] or norm
        mapping[norm] = default_profile_for_department(norm, code_hint)
    return mapping


def profile_settings(profile: Mapping[str, Any]) -> dict[str, Any]:
    mode = str(profile.get("mode") or "age_only").strip().lower()
    return {
        "mode": mode,
        "age_min": int(profile.get("age_min", 0)),
        "age_max": int(profile.get("age_max", 4)),
        "senior_age": int(profile.get("senior_age", 75)),
        "rules": list(profile.get("rules") or []),
        "check_kslp": mode != "none",
        "use_rules": mode == "rules",
    }


def resolve_row_kslp_settings(
    department: Any,
    department_code: Any,
    profiles: Mapping[str, dict[str, Any]],
    department_profile_map: Mapping[str, str],
) -> dict[str, Any]:
    code, name, _ = parse_ksg_department(department)
    if department_code is not None and str(department_code).strip():
        code = str(department_code).strip()
    dep_key = name or str(department or "").strip()
    profile_id = department_profile_map.get(dep_key)
    if not profile_id:
        profile_id = default_profile_for_department(dep_key, code)
    profile = profiles.get(profile_id) or profiles.get(BUILTIN_STANDARD) or {}
    settings = profile_settings(profile)
    settings["profile_id"] = profile_id
    settings["profile_name"] = str(profile.get("name") or profile_id)
    return settings
