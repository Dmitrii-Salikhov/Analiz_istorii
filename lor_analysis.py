"""Чистый анализ отчёта по заполнению ЭМК (без UI)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Mapping, Sequence
import re

import pandas as pd


EMK_VARIANT_DISCHARGED = "discharged"
EMK_VARIANT_CURRENT = "current"
ADMISSION_COL = "Дата и время поступления в указанном движении"
MOVEMENT_NUM_COL = "№ движения пациента в рамках госпитализации"
PRIMARY_EXAM_COL = "Наличие заполненного первичного осмотра в указанном движении"


def _is_numeric_code(token: str) -> bool:
    # «022201», «022201/», «№022201»
    return bool(re.fullmatch(r"[№#]?\d+/?", token))


def _is_junk_token(token: str) -> bool:
    """Служебные куски вроде «/», «-», пустые обломки разделителей."""
    t = token.strip()
    if not t:
        return True
    if re.fullmatch(r"[/\\|–—−·•.,;:]+", t):
        return True
    return not re.search(r"[A-Za-zА-Яа-яЁё]", t)


def _is_patronymic(token: str) -> bool:
    w = token.lower().rstrip(".")
    return w.endswith(("вич", "вна", "ична", "инична", "оглы", "кызы"))


def _looks_like_initials(token: str) -> bool:
    letters = re.findall(r"[A-Za-zА-Яа-яЁё]", token)
    if not letters:
        return False
    if "." in token:
        return True
    compact = token.replace(".", "")
    return len(compact) <= 3 and compact.isalpha() and compact.upper() == compact


def _initials_from_parts(parts: list[str]) -> list[str]:
    initials: list[str] = []
    for part in parts:
        letters = re.findall(r"[A-Za-zА-Яа-яЁё]", part)
        if not letters:
            continue
        if _looks_like_initials(part):
            initials.extend(ch.upper() + "." for ch in letters)
        else:
            initials.append(letters[0].upper() + ".")
    return initials


def format_doctor_name(full_name) -> str:
    """Фамилия целиком, имя и отчество — инициалами: «Салихов Д.А.».

    Учитывает табельный номер в начале («022201 …»), разделители «/»,
    и порядок «Имя Отчество Фамилия» / «И.О. Фамилия».
    """
    if pd.isna(full_name) or full_name == "":
        return "неизвестно"
    # «022201 / Фамилия …» → нормализуем разделители в пробелы
    text = str(full_name).strip()
    text = re.sub(r"[/\\|]+", " ", text)
    parts = text.split()
    if not parts:
        return "неизвестно"

    while parts and (_is_numeric_code(parts[0]) or _is_junk_token(parts[0])):
        parts.pop(0)
    # на случай кода/мусора в середине после нормализации
    parts = [p for p in parts if not _is_junk_token(p) and not _is_numeric_code(p)]
    if not parts:
        return "неизвестно"

    # И.О. Фамилия  /  Д.Н. Салихов
    if len(parts) >= 2 and _looks_like_initials(parts[0]):
        surname = parts[-1]
        name_parts = parts[:-1]
    # Имя Отчество Фамилия  /  Дмитрий Николаевич Салихов
    elif len(parts) >= 3 and _is_patronymic(parts[1]):
        surname = parts[-1]
        name_parts = parts[:-1]
    else:
        # Фамилия Имя Отчество  /  Салихов Дмитрий Николаевич
        surname = parts[0]
        name_parts = parts[1:]

    # Если «фамилия» всё ещё похожа на инициалы — берём последнее слово
    if _looks_like_initials(surname) and len(parts) >= 2:
        surname = parts[-1]
        name_parts = parts[:-1]

    initials = _initials_from_parts(name_parts)
    if initials:
        return f"{surname} {''.join(initials)}"
    return surname


def extract_discharge_period(df: pd.DataFrame) -> tuple[date | None, date | None]:
    """Период по дате выписки из стационара."""
    col = "Дата выписки из стационара"
    if col not in df.columns or df.empty:
        return None, None
    dates = pd.to_datetime(df[col], dayfirst=True, errors="coerce").dropna()
    if dates.empty:
        return None, None
    # Placeholder 01.01.1900 in «текущие» reports — not a real discharge period
    dates = dates[dates.dt.year >= 1990]
    if dates.empty:
        return None, None
    return dates.min().date(), dates.max().date()


def extract_admission_period(df: pd.DataFrame) -> tuple[date | None, date | None]:
    if ADMISSION_COL not in df.columns or df.empty:
        return None, None
    dates = pd.to_datetime(df[ADMISSION_COL], dayfirst=True, errors="coerce").dropna()
    if dates.empty:
        return None, None
    return dates.min().date(), dates.max().date()


def emk_report_basename(
    period_start: date | None,
    period_end: date | None,
    *,
    emk_variant: str = EMK_VARIANT_DISCHARGED,
    as_of: date | None = None,
) -> str:
    if emk_variant == EMK_VARIANT_CURRENT:
        day = as_of or date.today()
        return f"Отчет анализа ЭМК (текущие пациенты) на {day.strftime('%d.%m.%Y')}"
    if period_start and period_end:
        return (
            "Отчет анализа ЭМК за период с "
            f"{period_start.strftime('%d.%m.%Y')} по {period_end.strftime('%d.%m.%Y')}"
        )
    return "Отчет анализа ЭМК"


def is_admission_department(name: Any) -> bool:
    text = str(name or "").strip().lower().replace("ё", "е")
    return "приемн" in text


def collapse_current_patients_to_unique_kvs(df: pd.DataFrame) -> pd.DataFrame:
    """
    В отчёте «текущие» у каждого КВС обычно 2 строки (приёмное → коечное).
    Берём последнее движение по номеру; без номера — последнюю не-приёмную строку.
    """
    if df.empty or "Номер КВС" not in df.columns:
        return df.copy()
    work = df.copy()
    if MOVEMENT_NUM_COL in work.columns:
        mov = pd.to_numeric(work[MOVEMENT_NUM_COL], errors="coerce")
        work = work.assign(_mov=mov.fillna(-1))
        # Prefer higher movement number; among ties prefer non-admission
        work = work.assign(
            _adm=work["Отделение"].map(is_admission_department).astype(int)
        )
        work = work.sort_values(
            by=["Номер КВС", "_mov", "_adm"],
            ascending=[True, True, True],
        )
        out = work.groupby("Номер КВС", sort=False).tail(1).copy()
        return out.drop(columns=["_mov", "_adm"], errors="ignore")
    # No movement column: drop admission rows when a bed row exists for the same KVS
    adm = work["Отделение"].map(is_admission_department)
    bed = work.loc[~adm]
    only_adm = work.loc[adm & ~work["Номер КВС"].isin(set(bed["Номер КВС"]))]
    return pd.concat([bed, only_adm], ignore_index=True)

def violation_share_table(violations_df: pd.DataFrame) -> pd.DataFrame:
    """Таблица: тип нарушения → количество и доля % от всех нарушений."""
    if violations_df is None or violations_df.empty:
        return pd.DataFrame(columns=["Тип нарушения", "Количество", "Доля, %"])
    counts = violations_df["тип_нарушения"].value_counts()
    total = int(counts.sum())
    rows = []
    for tip, cnt in counts.items():
        share = round(100.0 * cnt / total, 1) if total else 0.0
        rows.append({"Тип нарушения": tip, "Количество": int(cnt), "Доля, %": share})
    return pd.DataFrame(rows)


EMD_EPICRISIS_PRESENT_COL = 'Наличие ЭМД "Выписной эпикриз"'
EMD_EPICRISIS_STATUS_COL = 'Статус ЭМД "Выписной эпикриз"'
EMD_EPICRISIS_NUMBER_COL = 'Номер ЭМД "Выписной эпикриз"'
EMD_EPICRISIS_TYPE = "ЭМД выписной эпикриз"

SNILS_COL = "Наличие СНИЛС"
SNILS_NOTE = "У пациента нет СНИЛС"
SNILS_MARKED_VIOLATION_TYPES: frozenset[str] = frozenset(
    {
        "Первичный осмотр",
        "Эпикриз",
        "МКСБ",
        "Протоколы операций",
        EMD_EPICRISIS_TYPE,
    }
)


def _has_ids(doc_str) -> bool:
    if pd.isna(doc_str):
        return False
    text = str(doc_str)
    return (
        "83 - Информированное добровольное согласие" in text
        or "ИДС" in text
        or "Информированное добровольное согласие" in text
    )


def _nonempty_cell(val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return ""
    try:
        if pd.isna(val):
            return ""
    except (TypeError, ValueError):
        pass
    text = str(val).strip()
    if not text or text.lower() in ("nan", "none", "-", "nat"):
        return ""
    return text


def snils_column_available(df: pd.DataFrame | None) -> bool:
    return df is not None and SNILS_COL in getattr(df, "columns", [])


def patient_has_snils(val: Any) -> bool:
    """True только при явном «ДА»."""
    text = _nonempty_cell(val).upper().replace("Ё", "Е")
    return text == "ДА"


def snils_note_for_violation(tip: str, has_snils: bool | None) -> str:
    """Пометка в таблице нарушений (рядом с КВС)."""
    if has_snils is None or has_snils:
        return ""
    if tip not in SNILS_MARKED_VIOLATION_TYPES:
        return ""
    return SNILS_NOTE


def violation_share_table_by_snils(violations_df: pd.DataFrame) -> pd.DataFrame:
    """Структура нарушений с разбивкой: С СНИЛС / Без СНИЛС. Доли — % от всех нарушений."""
    cols = [
        "Тип нарушения",
        "С СНИЛС",
        "Без СНИЛС",
        "Всего",
        "Доля с СНИЛС, %",
        "Доля без СНИЛС, %",
    ]
    if violations_df is None or violations_df.empty or "есть_СНИЛС" not in violations_df.columns:
        return pd.DataFrame(columns=cols)
    total = len(violations_df)
    rows: list[dict[str, Any]] = []
    for tip, group in violations_df.groupby("тип_нарушения", sort=False):
        with_s = int((group["есть_СНИЛС"] == "ДА").sum())
        without_s = int((group["есть_СНИЛС"] == "НЕТ").sum())
        unknown = int((group["есть_СНИЛС"] == "").sum())
        with_s += unknown
        tip_total = with_s + without_s
        rows.append(
            {
                "Тип нарушения": tip,
                "С СНИЛС": with_s,
                "Без СНИЛС": without_s,
                "Всего": tip_total,
                "Доля с СНИЛС, %": round(100.0 * with_s / total, 1) if total else 0.0,
                "Доля без СНИЛС, %": round(100.0 * without_s / total, 1) if total else 0.0,
            }
        )
    return pd.DataFrame(rows, columns=cols)


def cases_coverage_by_snils(
    prepared: pd.DataFrame,
    violations_df: pd.DataFrame,
) -> dict[str, Any] | None:
    """
    KPI покрытия с разбивкой по СНИЛС (уникальные КВС) + списки историй для UI.
    """
    if not snils_column_available(prepared) or "Номер КВС" not in prepared.columns:
        return None
    has = prepared[SNILS_COL].map(patient_has_snils)
    kvs = prepared["Номер КВС"].astype(str)
    doctors = (
        prepared["Лечащий врач"]
        if "Лечащий врач" in prepared.columns
        else pd.Series([""] * len(prepared), index=prepared.index)
    )
    if violations_df is not None and not violations_df.empty and "КВС" in violations_df.columns:
        bad = set(violations_df["КВС"].astype(str))
        viol_counts = violations_df["КВС"].astype(str).value_counts().to_dict()
    else:
        bad = set()
        viol_counts = {}

    buckets: dict[str, list[dict[str, Any]]] = {
        "with_violations_snils": [],
        "with_violations_no_snils": [],
        "without_violations_snils": [],
        "without_violations_no_snils": [],
    }
    seen: set[str] = set()
    for k, snils_ok, doc in zip(kvs, has, doctors, strict=False):
        if k in seen:
            continue
        seen.add(k)
        in_bad = k in bad
        note = "" if snils_ok else SNILS_NOTE
        row = {
            "КВС": k,
            "пометка": note,
            "врач": doc,
            "нарушений": int(viol_counts.get(k, 0)),
        }
        if in_bad and snils_ok:
            buckets["with_violations_snils"].append(row)
        elif in_bad and not snils_ok:
            buckets["with_violations_no_snils"].append(row)
        elif (not in_bad) and snils_ok:
            buckets["without_violations_snils"].append(row)
        else:
            buckets["without_violations_no_snils"].append(row)

    return {
        "with_violations_snils": len(buckets["with_violations_snils"]),
        "with_violations_no_snils": len(buckets["with_violations_no_snils"]),
        "without_violations_snils": len(buckets["without_violations_snils"]),
        "without_violations_no_snils": len(buckets["without_violations_no_snils"]),
        "lists": buckets,
    }


def cases_coverage_lists(
    prepared: pd.DataFrame,
    violations_df: pd.DataFrame,
) -> dict[str, list[dict[str, Any]]]:
    """Списки КВС с / без нарушений (без разбивки по СНИЛС)."""
    if prepared is None or prepared.empty or "Номер КВС" not in prepared.columns:
        return {"with_violations": [], "without_violations": []}
    if violations_df is not None and not violations_df.empty and "КВС" in violations_df.columns:
        bad = set(violations_df["КВС"].astype(str))
        viol_counts = violations_df["КВС"].astype(str).value_counts().to_dict()
    else:
        bad = set()
        viol_counts = {}
    snils_known = snils_column_available(prepared)
    with_v: list[dict[str, Any]] = []
    without_v: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _, prow in prepared.iterrows():
        k = str(prow["Номер КВС"])
        if k in seen:
            continue
        seen.add(k)
        note = ""
        if snils_known and not patient_has_snils(prow.get(SNILS_COL)):
            note = SNILS_NOTE
        row = {
            "КВС": k,
            "пометка": note,
            "врач": prow.get("Лечащий врач", ""),
            "нарушений": int(viol_counts.get(k, 0)),
        }
        if k in bad:
            with_v.append(row)
        else:
            without_v.append(row)
    return {"with_violations": with_v, "without_violations": without_v}

def emd_sent_to_storage_mask(df: pd.DataFrame) -> pd.Series:
    """ЭМД выписного эпикриза зарегистрирован или отправлен в хранилище."""
    ok = pd.Series(False, index=df.index)
    if EMD_EPICRISIS_STATUS_COL in df.columns:
        st = (
            df[EMD_EPICRISIS_STATUS_COL]
            .map(_nonempty_cell)
            .str.lower()
            .str.replace("ё", "е", regex=False)
        )
        ok |= st.str.contains("зарегистрирован", na=False)
        ok |= st.str.contains("отправлен", na=False) & ~st.str.contains("ошибка", na=False)
    if EMD_EPICRISIS_NUMBER_COL in df.columns:
        ok |= df[EMD_EPICRISIS_NUMBER_COL].map(_nonempty_cell).ne("")
    return ok


def _emd_violation_text(row) -> str:
    status = _nonempty_cell(row.get(EMD_EPICRISIS_STATUS_COL, ""))
    present = _nonempty_cell(row.get(EMD_EPICRISIS_PRESENT_COL, "")).upper()
    st_norm = status.lower().replace("ё", "е")
    if "ошибка" in st_norm:
        return f"Ошибка регистрации ЭМД в хранилище ({status})"
    if status:
        return f"Выписной эпикриз не отправлен в хранилище (статус: {status})"
    if present == "ДА":
        return "ЭМД выписного эпикриза есть, но не зарегистрирован в хранилище"
    return "ЭМД выписного эпикриза не отправлен в хранилище"


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


def parse_hir_operations(text) -> list[tuple[str, str]]:
    """Разбирает «Хир. активность (операции)» → [(код, наименование), ...]."""
    if pd.isna(text):
        return []
    raw = str(text).strip()
    if not raw or raw.lower() in ("nan", "none", "-"):
        return []
    result: list[tuple[str, str]] = []
    for part in raw.split(";"):
        part = part.strip()
        if not part:
            continue
        tokens = part.split(None, 1)
        code = tokens[0].strip()
        name = tokens[1].strip() if len(tokens) > 1 else ""
        if code:
            result.append((code, name))
    return result


def format_hir_operations_short(text) -> str:
    """Краткая строка кодов/названий для таблицы."""
    ops = parse_hir_operations(text)
    if not ops:
        return "—"
    return "; ".join(code if not name else f"{code} {name}" for code, name in ops)


def build_skp_tables(prepared: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int, int]:
    """
    СКП — стационар краткосрочного пребывания: койко-дни 0 или 1 (сырое значение).
    Возвращает (список случаев, сводка по кодам, count_0, count_1).
    """
    days = prepared["Койко-дни"]
    skp = prepared[days.isin([0, 1])].copy()
    count_0 = int((days == 0).sum())
    count_1 = int((days == 1).sum())

    empty_cases = pd.DataFrame(
        columns=["КВС", "Койко-дни", "Тип", "Врач", "Операции", "Кол-во операций"]
    )
    empty_ops = pd.DataFrame(
        columns=["Код услуги", "Наименование", "Количество случаев СКП"]
    )
    if skp.empty:
        return empty_cases, empty_ops, count_0, count_1

    ops_col = "Хир. активность (операции)"
    cases = pd.DataFrame(
        {
            "КВС": skp["Номер КВС"].astype(str),
            "Койко-дни": skp["Койко-дни"].astype(int),
            "Тип": skp["Тип госпитализации"].astype(str),
            "Врач": skp["Лечащий врач"].map(format_doctor_name),
            "Операции": skp[ops_col].map(format_hir_operations_short),
            "Кол-во операций": skp["Хир_кол"].astype(int),
        }
    ).reset_index(drop=True)

    op_rows: list[dict] = []
    for _, row in skp.iterrows():
        seen: set[str] = set()
        for code, name in parse_hir_operations(row.get(ops_col)):
            if code in seen:
                continue
            seen.add(code)
            op_rows.append(
                {"Код услуги": code, "Наименование": name, "КВС": row["Номер КВС"]}
            )

    if op_rows:
        ops_df = pd.DataFrame(op_rows)
        ops_summary = (
            ops_df.groupby(["Код услуги", "Наименование"], dropna=False)
            .size()
            .reset_index(name="Количество случаев СКП")
            .sort_values(by="Количество случаев СКП", ascending=False)
            .reset_index(drop=True)
        )
    else:
        ops_summary = empty_ops

    return cases, ops_summary, count_0, count_1


# Пары «нужно / оформлено»: (колонка нужно, колонка факт, ключ нужно, ключ факт, обязательна).
# Новые метрики отчёта ЭМК — опциональные: старые выгрузки без них продолжают открываться.
_COUNT_PAIRS: tuple[tuple[str, str, str, str, bool], ...] = (
    (
        "Количество дневниковых записей, которое необходимо было завести в указанном движении",
        "Количество оформленных дневниковых записей в указанном движении",
        "Дневники_необх",
        "Дневники_факт",
        True,
    ),
    (
        "Количество оформленных направлений на лабораторные исследования в указанном движении",
        "Количество проведенных лабораторных исследований в указанном движении",
        "Лаб_напр",
        "Лаб_пров",
        False,
    ),
    (
        "Количество оформленных направлений на инструментальные методы лечения в указанном движении",
        "Количество проведенных инструментальных исследований в указанном движении",
        "Инстр_напр",
        "Инстр_пров",
        False,
    ),
    (
        "Количество оформленных направлений на консультативные услуги в указанном движении",
        "Количество оформленных консультативных услуг в указанном движении",
        "Конс_напр",
        "Конс_факт",
        False,
    ),
    (
        "Количество необходимых реанимационных дневников в указанном движении",
        "Количество оформленных реанимационных дневников в указанном движении",
        "Реан_необх",
        "Реан_факт",
        False,
    ),
)

# ключ нужно, ключ факт, тип нарушения, префикс текста
_COUNT_DEFICIT_SPECS: tuple[tuple[str, str, str, str], ...] = (
    ("Дневники_необх", "Дневники_факт", "Дневниковые записи", "Недостаточно дневников"),
    (
        "Лаб_напр",
        "Лаб_пров",
        "Лабораторные исследования",
        "Недостаточно лабораторных исследований",
    ),
    (
        "Инстр_напр",
        "Инстр_пров",
        "Инструментальные исследования",
        "Недостаточно инструментальных исследований",
    ),
    ("Конс_напр", "Конс_факт", "Консультативные услуги", "Недостаточно консультативных услуг"),
    (
        "Реан_необх",
        "Реан_факт",
        "Реанимационные дневники",
        "Недостаточно реанимационных дневников",
    ),
)

COUNT_DEFICIT_TYPES: frozenset[str] = frozenset(spec[2] for spec in _COUNT_DEFICIT_SPECS)
REFERRAL_INVESTIGATION_TYPES: frozenset[str] = frozenset(
    {"Лабораторные исследования", "Инструментальные исследования"}
)
CONSULTATION_SERVICE_TYPES: frozenset[str] = frozenset({"Консультативные услуги"})


def format_count_deficit_violation(vtype: str, need: int, fact: int, prefix: str) -> str:
    if vtype in REFERRAL_INVESTIGATION_TYPES:
        return f"создано направлений: {need}, выполнено исследований: {fact}"
    if vtype in CONSULTATION_SERVICE_TYPES:
        return f"направлено: {need}, завершено: {fact}"
    return f"{prefix}: нужно {need}, оформлено {fact}"

# Справочные проверки ЭМК (можно отключить в настройках; не влияют на рейтинг врача).
EMK_INFO_CHECK_KEYS: tuple[str, ...] = ("lab", "instr", "cons", "rean", "emd")
EMK_INFO_CHECK_TO_VIOLATION: dict[str, str] = {
    "lab": "Лабораторные исследования",
    "instr": "Инструментальные исследования",
    "cons": "Консультативные услуги",
    "rean": "Реанимационные дневники",
    "emd": EMD_EPICRISIS_TYPE,
}
EMK_INFO_VIOLATION_TYPES: frozenset[str] = frozenset(EMK_INFO_CHECK_TO_VIOLATION.values())
VIOLATION_TYPES_EXCLUDED_FROM_DOCTOR_STATS: frozenset[str] = frozenset(
    {"Длительная госпитализация", *EMK_INFO_VIOLATION_TYPES}
)


def normalize_emk_info_checks(raw: Mapping[str, Any] | None) -> dict[str, bool]:
    defaults = {key: True for key in EMK_INFO_CHECK_KEYS}
    if not isinstance(raw, dict):
        return defaults
    return {key: bool(raw.get(key, defaults[key])) for key in EMK_INFO_CHECK_KEYS}


def emk_info_check_enabled(settings: Mapping[str, Any] | None, key: str) -> bool:
    return normalize_emk_info_checks((settings or {}).get("emk_info_checks")).get(key, True)


def emk_info_check_enabled_for_violation(
    settings: Mapping[str, Any] | None, violation_type: str
) -> bool:
    for check_key, vtype in EMK_INFO_CHECK_TO_VIOLATION.items():
        if vtype == violation_type:
            return emk_info_check_enabled(settings, check_key)
    return True

VIOLATION_CATEGORY_TITLES: dict[str, str] = {
    "МКСБ": "МКСБ (Не подписана)",
    "Протоколы операций": "Протоколы операций (несоответствие)",
    "Эпикриз": "Эпикризы (не оформлены)",
    "Первичный осмотр": "Первичный осмотр (не оформлен)",
    "Лекарственные назначения": "Лекарственные назначения (отсутствуют)",
    "Дневниковые записи": "Дневниковые записи (недостаточно)",
    "Лабораторные исследования": "Лабораторные исследования (не проведены)",
    "Инструментальные исследования": "Инструментальные исследования (не проведены)",
    "Консультативные услуги": "Консультативные услуги (не оформлены)",
    "Реанимационные дневники": "Реанимационные дневники (недостаточно)",
    "ЭМД выписной эпикриз": "ЭМД выписной эпикриз (не в хранилище)",
    "ИДС": "ИДС (отсутствует)",
}


def violation_category_title(vtype: str, *, long_stay_days: int = 7) -> str:
    if vtype == "Длительная госпитализация":
        return f"Длительная госпитализация (>{long_stay_days} дней)"
    return VIOLATION_CATEGORY_TITLES.get(str(vtype), str(vtype))


def _as_count(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(0)


def prepare_lor_dataframe(
    df: pd.DataFrame,
    *,
    emk_variant: str = EMK_VARIANT_DISCHARGED,
    as_of: date | None = None,
) -> pd.DataFrame:
    out = df.copy()
    out["Возраст"] = pd.to_numeric(
        out["Возраст на момент госпитализации в стационар"], errors="coerce"
    )
    if emk_variant == EMK_VARIANT_CURRENT and ADMISSION_COL in out.columns:
        ref = pd.Timestamp(as_of or date.today()).normalize()
        adm = pd.to_datetime(out[ADMISSION_COL], dayfirst=True, errors="coerce")
        days = (ref - adm.dt.normalize()).dt.days
        out["Койко-дни"] = days
        # Fallback if admission missing: ignore negative Excel placeholders
        excel_days = pd.to_numeric(
            out["Всего дней проведено в стационаре (от поступления до исхода в днях)"],
            errors="coerce",
        )
        need_fill = out["Койко-дни"].isna() & excel_days.notna() & (excel_days >= 0)
        out.loc[need_fill, "Койко-дни"] = excel_days.loc[need_fill]
    else:
        out["Койко-дни"] = pd.to_numeric(
            out["Всего дней проведено в стационаре (от поступления до исхода в днях)"],
            errors="coerce",
        )
    out["Койко-дни_скор"] = out["Койко-дни"].apply(
        lambda x: 1 if pd.isna(x) or x <= 0 else x
    )
    out["Хир_кол"] = (
        pd.to_numeric(out["Хир. активность (количество)"], errors="coerce").fillna(0).astype(int)
    )
    out["Хир_прот"] = (
        pd.to_numeric(out["Хир. активность (протоколы)"], errors="coerce").fillna(0).astype(int)
    )
    ops_col = "Хир. активность (операции)"
    if ops_col not in out.columns:
        out[ops_col] = ""
    out["Лекарства"] = pd.to_numeric(
        out["Наличие оформленных лекарственных назначений в указанном движении"],
        errors="coerce",
    ).fillna(0)
    for need_col, fact_col, need_key, fact_key, required in _COUNT_PAIRS:
        if required or (need_col in out.columns and fact_col in out.columns):
            out[need_key] = _as_count(out[need_col])
            out[fact_key] = _as_count(out[fact_col])
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


def filter_by_departments(df: pd.DataFrame, departments: Sequence[str]) -> pd.DataFrame:
    """Строгое совпадение по колонке «Отделение» (для мульти-сводки)."""
    names = {str(d).strip() for d in departments if str(d).strip()}
    if not names:
        return df.iloc[0:0].copy()
    col = df["Отделение"].astype(str).str.strip()
    return df[col.isin(names)].copy()


def format_department_scope_label(
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
    period_start: date | None = None
    period_end: date | None = None
    skp_count: int = 0
    skp_days_0: int = 0
    skp_days_1: int = 0
    skp_cases: pd.DataFrame | None = None
    skp_operations: pd.DataFrame | None = None

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
            "period_start": self.period_start,
            "period_end": self.period_end,
            "skp_count": self.skp_count,
            "skp_days_0": self.skp_days_0,
            "skp_days_1": self.skp_days_1,
            "skp_cases": self.skp_cases,
            "skp_operations": self.skp_operations,
        }


def analyze_lor(
    df: pd.DataFrame,
    settings: Mapping[str, Any] | None = None,
    *,
    emk_variant: str = EMK_VARIANT_DISCHARGED,
    as_of: date | None = None,
) -> LorAnalysisResult:
    settings = settings or {}
    long_stay_days = int(settings.get("long_stay_days", 7))
    if long_stay_days < 1:
        long_stay_days = 1
    as_of_day = as_of or date.today()
    is_current = emk_variant == EMK_VARIANT_CURRENT

    source = collapse_current_patients_to_unique_kvs(df) if is_current else df
    prepared = prepare_lor_dataframe(source, emk_variant=emk_variant, as_of=as_of_day)
    if is_current:
        period_start, period_end = extract_admission_period(prepared)
        if period_start is None:
            period_start = as_of_day
        period_end = as_of_day
    else:
        period_start, period_end = extract_discharge_period(prepared)
    total = len(prepared)
    empty_viol = pd.DataFrame(
        columns=[
            "КВС",
            "пометка",
            "есть_СНИЛС",
            "возраст",
            "тип госпитализации",
            "врач",
            "отделение",
            "тип_нарушения",
            "нарушение",
        ]
    )
    if total == 0:
        empty_skp_cases, empty_skp_ops, _, _ = build_skp_tables(prepared)
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
            period_start=period_start,
            period_end=period_end,
            skp_count=0,
            skp_days_0=0,
            skp_days_1=0,
            skp_cases=empty_skp_cases,
            skp_operations=empty_skp_ops,
        )

    avg_beddays = float(prepared["Койко-дни_скор"].sum() / total)
    type_lower = prepared["Тип госпитализации"].astype(str).str.lower()
    urgent = int(type_lower.str.contains("экстрен", na=False).sum())
    planned = int(type_lower.str.contains("планов", na=False).sum())

    prepared["Возрастная группа"] = prepared["Возраст"].apply(age_group)
    age_dist = prepared["Возрастная группа"].value_counts()

    snils_known = snils_column_available(prepared)
    if snils_known:
        prepared["_has_snils"] = prepared[SNILS_COL].map(patient_has_snils)

    violations: list[dict] = []
    empty_viol_cols = [
        "КВС",
        "пометка",
        "есть_СНИЛС",
        "возраст",
        "тип госпитализации",
        "врач",
        "отделение",
        "тип_нарушения",
        "нарушение",
    ]

    def _row_has_snils(row) -> bool | None:
        if not snils_known:
            return None
        return bool(row.get("_has_snils"))

    def _snils_flag(has: bool | None) -> str:
        if has is None:
            return ""
        return "ДА" if has else "НЕТ"

    def add_rows(subset: pd.DataFrame, tip: str, text_fn):
        for _, row in subset.iterrows():
            has = _row_has_snils(row)
            violations.append(
                {
                    "КВС": row["Номер КВС"],
                    "пометка": snils_note_for_violation(tip, has),
                    "есть_СНИЛС": _snils_flag(has),
                    "возраст": row["Возраст"],
                    "тип госпитализации": row["Тип госпитализации"],
                    "врач": row["Лечащий врач"],
                    "отделение": row.get("Отделение", ""),
                    "тип_нарушения": tip,
                    "нарушение": text_fn(row),
                }
            )

    primary_col = PRIMARY_EXAM_COL
    primary_bad = prepared[primary_col] != "ДА"
    if is_current:
        # В приёмном пустой первичный осмотр не считается нарушением
        primary_bad = primary_bad & ~prepared["Отделение"].map(is_admission_department)
    add_rows(
        prepared[primary_bad],
        "Первичный осмотр",
        lambda r: "Отсутствует первичный осмотр (не 'ДА')",
    )

    epicrisis_col = "Наличие оформленного эпикриза в указанном движении"
    if not is_current:
        add_rows(
            prepared[prepared[epicrisis_col] != "ДА"],
            "Эпикриз",
            lambda r: "Отсутствует эпикриз (не 'ДА')",
        )
        emd_cols_present = (
            EMD_EPICRISIS_PRESENT_COL in prepared.columns
            or EMD_EPICRISIS_STATUS_COL in prepared.columns
            or EMD_EPICRISIS_NUMBER_COL in prepared.columns
        )
        if emd_cols_present and emk_info_check_enabled(settings, "emd"):
            local_epicrisis_ok = prepared[epicrisis_col] == "ДА"
            in_storage = emd_sent_to_storage_mask(prepared)
            add_rows(
                prepared[local_epicrisis_ok & ~in_storage],
                EMD_EPICRISIS_TYPE,
                _emd_violation_text,
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
    for need_key, fact_key, tip, prefix in _COUNT_DEFICIT_SPECS:
        if not emk_info_check_enabled_for_violation(settings, tip):
            continue
        if need_key not in prepared.columns or fact_key not in prepared.columns:
            continue
        add_rows(
            prepared[prepared[fact_key] < prepared[need_key]],
            tip,
            lambda r, nk=need_key, fk=fact_key, p=prefix, t=tip: format_count_deficit_violation(
                t, int(r[nk]), int(r[fk]), p
            ),
        )
    docs_col = "Другие связанные документы"
    if not is_current and docs_col in prepared.columns:
        add_rows(
            prepared[~prepared[docs_col].apply(_has_ids)],
            "ИДС",
            lambda r: "Отсутствует ИДС",
        )

    long_stay = prepared[prepared["Койко-дни_скор"] > long_stay_days]
    add_rows(
        long_stay,
        "Длительная госпитализация",
        lambda r: f"Койко-день >{long_stay_days} дней ({int(r['Койко-дни_скор'])})",
    )

    surg = prepared[prepared["Хир_кол"] > 0]
    for _, row in surg.iterrows():
        op = int(row["Хир_кол"])
        prot = int(row["Хир_прот"])
        if prot < op or prot > op:
            has = _row_has_snils(row)
            tip = "Протоколы операций"
            if prot < op:
                text = f"Несоответствие протоколов: операций {op}, протоколов {prot}"
            else:
                text = f"Избыток протоколов: операций {op}, протоколов {prot}"
            violations.append(
                {
                    "КВС": row["Номер КВС"],
                    "пометка": snils_note_for_violation(tip, has),
                    "есть_СНИЛС": _snils_flag(has),
                    "возраст": row["Возраст"],
                    "тип госпитализации": row["Тип госпитализации"],
                    "врач": row["Лечащий врач"],
                    "отделение": row.get("Отделение", ""),
                    "тип_нарушения": tip,
                    "нарушение": text,
                }
            )

    violations_df = pd.DataFrame(violations) if violations else pd.DataFrame(columns=empty_viol_cols)
    col_order = [c for c in empty_viol_cols if c in violations_df.columns]
    extra = [c for c in violations_df.columns if c not in col_order]
    violations_df = violations_df[col_order + extra]
    if "_has_snils" in prepared.columns:
        prepared = prepared.drop(columns=["_has_snils"])
    violations_for_doctor = violations_df[
        ~violations_df["тип_нарушения"].isin(VIOLATION_TYPES_EXCLUDED_FROM_DOCTOR_STATS)
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

    skp_cases, skp_operations, skp_days_0, skp_days_1 = build_skp_tables(prepared)

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
        period_start=period_start,
        period_end=period_end,
        skp_count=skp_days_0 + skp_days_1,
        skp_days_0=skp_days_0,
        skp_days_1=skp_days_1,
        skp_cases=skp_cases,
        skp_operations=skp_operations,
    )


def _snils_note_short(note: Any) -> str:
    """Краткая пометка для сводки: «нет СНИЛС»."""
    text = str(note or "").strip()
    if not text:
        return ""
    if "снилс" in text.lower():
        return "нет СНИЛС"
    return text


def _violation_bullet_line(row: pd.Series, vtype: str) -> str:
    doctor_short = format_doctor_name(row["врач"])
    snils = _snils_note_short(row.get("пометка"))
    kvs = row["КВС"]
    if snils:
        head = f"• {kvs} - {snils} (Врач: {doctor_short})"
    else:
        head = f"• {kvs} (Врач: {doctor_short})"

    if vtype == "Протоколы операций":
        match = re.search(r"операций (\d+), протоколов (\d+)", str(row["нарушение"]))
        if match:
            return f"{head}: {match.group(1)} операции / {match.group(2)} протоколов"
        return f"{head}: {row['нарушение']}"
    if vtype in COUNT_DEFICIT_TYPES:
        text = str(row["нарушение"])
        match = re.search(r"нужно (\d+), оформлено (\d+)", text)
        if match:
            return f"{head}: нужно {match.group(1)}, оформлено {match.group(2)}"
        return f"{head}: {text}"
    if vtype == "МКСБ":
        age_str = f"{int(row['возраст'])}г" if pd.notna(row["возраст"]) else "?г"
        if snils:
            return f"• {kvs} - {snils} ({age_str}, Врач: {doctor_short})"
        return f"• {kvs} ({age_str}) — {doctor_short}"
    if vtype == "Длительная госпитализация":
        match = re.search(r"\((\d+)\)", str(row["нарушение"]))
        days = match.group(1) if match else "?"
        return f"{head} — {days} дн."
    if vtype == EMD_EPICRISIS_TYPE:
        return f"{head}: {row['нарушение']}"
    return head


def _violation_group_lines(
    group: pd.DataFrame,
    vtype: str,
    *,
    group_by_department: bool = False,
    department_order: Sequence[str] | None = None,
) -> list[str]:
    lines: list[str] = []
    dept_col = "отделение"
    if group_by_department and dept_col in group.columns:
        present = group[dept_col].fillna("").astype(str).str.strip()
        present = present.replace("", "—")
        order = list(department_order or [])
        seen = set(order)
        for name in sorted(present.unique(), key=str.lower):
            if name not in seen:
                order.append(name)
                seen.add(name)
        for dept_name in order:
            sub = group[present == dept_name]
            if sub.empty:
                continue
            lines.append(f"[{dept_name}]")
            for _, row in sub.iterrows():
                lines.append(_violation_bullet_line(row, vtype))
        return lines
    for _, row in group.iterrows():
        lines.append(_violation_bullet_line(row, vtype))
    return lines


def format_violations_summary_sections(
    violations_df: pd.DataFrame,
    *,
    long_stay_days: int = 7,
    group_by_department: bool = False,
    department_order: Sequence[str] | None = None,
) -> list[dict[str, Any]]:
    """
    Сводные блоки нарушений для копирования (как во вкладке «Все нарушения»).
    Каждый элемент: {id, title, count, text}.
    """
    if violations_df is None or violations_df.empty:
        return []

    sections: list[dict[str, Any]] = []
    for vtype, group in violations_df.groupby("тип_нарушения", sort=False):
        title = violation_category_title(str(vtype), long_stay_days=long_stay_days)
        lines = [f"{title}:"]
        lines.extend(
            _violation_group_lines(
                group,
                str(vtype),
                group_by_department=group_by_department,
                department_order=department_order,
            )
        )
        lines.append("-" * 50)
        sections.append(
            {
                "id": str(vtype),
                "title": title,
                "count": int(len(group)),
                "text": "\n".join(lines),
            }
        )
    return sections
