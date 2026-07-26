"""Профили форматов отчётов ЭМК/КСГ: синонимы колонок → канонические имена."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

# Канонические имена = то, что ждут lor_analysis / ksg_analysis.

EMK_REQUIRED_COLUMNS: tuple[str, ...] = (
    "Отделение",
    "Номер КВС",
    "Возраст на момент госпитализации в стационар",
    "Тип госпитализации",
    "Всего дней проведено в стационаре (от поступления до исхода в днях)",
    "Лечащий врач",
    "Наличие заполненного первичного осмотра в указанном движении",
    "Наличие оформленного эпикриза в указанном движении",
    "Статус МКСБ",
    "Наличие оформленных лекарственных назначений в указанном движении",
    "Количество дневниковых записей, которое необходимо было завести в указанном движении",
    "Количество оформленных дневниковых записей в указанном движении",
    "Другие связанные документы",
    "Хир. активность (количество)",
    "Хир. активность (протоколы)",
)

EMK_OPTIONAL_COLUMNS: tuple[str, ...] = (
    "Хир. активность (операции)",
    "Дата выписки из стационара",
)

KSG_REQUIRED_COLUMNS: tuple[str, ...] = (
    "№ талона",
    "Врач",
    "Код услуги",
    "Сумма к оплате",
    "Дата рождения",
    "КСЛП итоговый",
    "КЗ",
)

KSG_OPTIONAL_COLUMNS: tuple[str, ...] = (
    "Поступление",
    "Выписка",
)


def _self_aliases(*names: str) -> dict[str, list[str]]:
    """Канон → [канон, ...синонимы]."""
    return {n: [n] for n in names}


def _default_emk_aliases() -> dict[str, list[str]]:
    aliases = _self_aliases(*EMK_REQUIRED_COLUMNS, *EMK_OPTIONAL_COLUMNS)
    aliases["Номер КВС"] = ["Номер КВС", "№ КВС", "КВС", "Номер истории", "№ истории"]
    aliases["Отделение"] = ["Отделение", "Подразделение", "Отд."]
    aliases["Лечащий врач"] = ["Лечащий врач", "Врач", "ФИО врача", "Врач лечащий"]
    aliases["Тип госпитализации"] = ["Тип госпитализации", "Вид госпитализации", "Тип"]
    aliases["Возраст на момент госпитализации в стационар"] = [
        "Возраст на момент госпитализации в стационар",
        "Возраст на момент госпитализации",
        "Возраст",
    ]
    aliases["Всего дней проведено в стационаре (от поступления до исхода в днях)"] = [
        "Всего дней проведено в стационаре (от поступления до исхода в днях)",
        "Койко-дни",
        "Койко дни",
        "Дней в стационаре",
    ]
    aliases["Хир. активность (количество)"] = [
        "Хир. активность (количество)",
        "Хирургическая активность (количество)",
        "Кол-во операций",
    ]
    aliases["Хир. активность (протоколы)"] = [
        "Хир. активность (протоколы)",
        "Хирургическая активность (протоколы)",
        "Кол-во протоколов",
    ]
    aliases["Хир. активность (операции)"] = [
        "Хир. активность (операции)",
        "Хирургическая активность (операции)",
        "Операции",
        "Коды операций",
    ]
    aliases["Дата выписки из стационара"] = [
        "Дата выписки из стационара",
        "Дата выписки",
        "Выписка",
    ]
    aliases["Наличие заполненного первичного осмотра в указанном движении"] = [
        "Наличие заполненного первичного осмотра в указанном движении",
        "Первичный осмотр",
    ]
    aliases["Наличие оформленного эпикриза в указанном движении"] = [
        "Наличие оформленного эпикриза в указанном движении",
        "Эпикриз",
    ]
    aliases["Статус МКСБ"] = ["Статус МКСБ", "МКСБ"]
    return aliases


def _default_ksg_aliases() -> dict[str, list[str]]:
    aliases = _self_aliases(*KSG_REQUIRED_COLUMNS, *KSG_OPTIONAL_COLUMNS)
    aliases["№ талона"] = ["№ талона", "Номер талона", "Талон", "№ случая"]
    aliases["Врач"] = ["Врач", "Лечащий врач", "ФИО врача"]
    aliases["Код услуги"] = [
        "Код услуги",
        "Код мед. услуги",
        "Код медицинской услуги",
        "Коды услуг",
        "Услуга",
    ]
    aliases["Сумма к оплате"] = ["Сумма к оплате", "Сумма", "Сумма оплаты"]
    aliases["Дата рождения"] = ["Дата рождения", "ДР", "Дата рожд."]
    aliases["КСЛП итоговый"] = ["КСЛП итоговый", "КСЛП", "КСЛП итог"]
    aliases["КЗ"] = ["КЗ", "Коэффициент затратоемкости"]
    aliases["Поступление"] = ["Поступление", "Дата поступления"]
    aliases["Выписка"] = ["Выписка", "Дата выписки"]
    return aliases


DEFAULT_EMK_PROFILE: dict[str, Any] = {
    "id": "default",
    "name": "ЭМК стандарт",
    "header_fragments": ["Номер КВС", "Возраст на момент госпитализации"],
    "required_columns": list(EMK_REQUIRED_COLUMNS),
    "aliases": _default_emk_aliases(),
}

DEFAULT_KSG_PROFILE: dict[str, Any] = {
    "id": "default",
    "name": "КСГ стандарт",
    "header_fragments": ["№ талона", "Код услуги"],
    "required_columns": list(KSG_REQUIRED_COLUMNS),
    "aliases": _default_ksg_aliases(),
}

DEFAULT_REPORT_PROFILES: dict[str, Any] = {
    "emk_active": "default",
    "ksg_active": "default",
    "emk": {"default": deepcopy(DEFAULT_EMK_PROFILE)},
    "ksg": {"default": deepcopy(DEFAULT_KSG_PROFILE)},
}


def _merge_profile(base: dict[str, Any], overlay: dict[str, Any] | None) -> dict[str, Any]:
    out = deepcopy(base)
    if not isinstance(overlay, dict):
        return out
    for key in ("id", "name"):
        if overlay.get(key):
            out[key] = overlay[key]
    if isinstance(overlay.get("header_fragments"), list) and overlay["header_fragments"]:
        out["header_fragments"] = [str(x) for x in overlay["header_fragments"] if str(x).strip()]
    if isinstance(overlay.get("required_columns"), list) and overlay["required_columns"]:
        out["required_columns"] = [str(x) for x in overlay["required_columns"] if str(x).strip()]
    base_aliases = out.get("aliases") if isinstance(out.get("aliases"), dict) else {}
    over_aliases = overlay.get("aliases") if isinstance(overlay.get("aliases"), dict) else {}
    merged_aliases: dict[str, list[str]] = deepcopy(base_aliases)
    for canon, aliases in over_aliases.items():
        if not isinstance(aliases, list):
            continue
        cleaned = [str(a).strip() for a in aliases if str(a).strip()]
        if cleaned:
            merged_aliases[str(canon)] = cleaned
    out["aliases"] = merged_aliases
    return out


def normalize_report_profiles(raw: Any) -> dict[str, Any]:
    """Merge user report_profiles onto built-in defaults."""
    result = deepcopy(DEFAULT_REPORT_PROFILES)
    if not isinstance(raw, dict):
        return result

    for kind in ("emk", "ksg"):
        default_prof = (
            deepcopy(DEFAULT_EMK_PROFILE) if kind == "emk" else deepcopy(DEFAULT_KSG_PROFILE)
        )
        user_kind = raw.get(kind) if isinstance(raw.get(kind), dict) else {}
        merged_kind: dict[str, Any] = {}
        # always keep default
        merged_kind["default"] = _merge_profile(default_prof, user_kind.get("default"))
        for pid, prof in user_kind.items():
            if pid == "default" or not isinstance(prof, dict):
                continue
            seed = deepcopy(default_prof)
            seed["id"] = str(pid)
            merged_kind[str(pid)] = _merge_profile(seed, prof)
            merged_kind[str(pid)]["id"] = str(pid)
        result[kind] = merged_kind

    emk_active = str(raw.get("emk_active") or "default")
    ksg_active = str(raw.get("ksg_active") or "default")
    if emk_active not in result["emk"]:
        emk_active = "default"
    if ksg_active not in result["ksg"]:
        ksg_active = "default"
    result["emk_active"] = emk_active
    result["ksg_active"] = ksg_active
    return result


def get_active_profile(cfg: dict[str, Any], kind: str) -> dict[str, Any]:
    """kind: 'emk' | 'ksg'."""
    profiles = normalize_report_profiles(cfg.get("report_profiles"))
    active_key = "emk_active" if kind == "emk" else "ksg_active"
    bucket = "emk" if kind == "emk" else "ksg"
    pid = profiles.get(active_key) or "default"
    prof = profiles.get(bucket, {}).get(pid) or profiles[bucket]["default"]
    return deepcopy(prof)
