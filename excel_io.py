"""Надёжное чтение Excel-отчётов с понятными ошибками и синонимами колонок."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Iterable, Mapping, Sequence

import pandas as pd

from report_profiles import (
    DEFAULT_EMK_PROFILE,
    DEFAULT_KSG_PROFILE,
    DEFAULT_OPS_PROFILE,
    EMK_REQUIRED_COLUMNS,
    KSG_REQUIRED_COLUMNS,
    get_active_profile,
)


class ExcelParseError(Exception):
    """Базовая ошибка разбора Excel."""


class HeaderNotFoundError(ExcelParseError):
    pass


class ColumnMappingConflictError(ExcelParseError):
    pass


class MissingColumnsError(ExcelParseError):
    def __init__(
        self,
        missing: Sequence[str],
        found: Sequence[str] | None = None,
        unmatched: Sequence[str] | None = None,
    ):
        self.missing = list(missing)
        self.found = list(found or [])
        self.unmatched = list(unmatched or [])
        lines = ["В файле отсутствуют обязательные столбцы:"]
        for col in self.missing:
            lines.append(f"  • {col}")
        if self.found:
            preview = ", ".join(self.found[:12])
            more = f" (+ ещё {len(self.found) - 12})" if len(self.found) > 12 else ""
            lines.append("")
            lines.append(f"Найденные столбцы: {preview}{more}")
        if self.unmatched:
            preview = ", ".join(self.unmatched[:12])
            more = f" (+ ещё {len(self.unmatched) - 12})" if len(self.unmatched) - 12 > 0 else ""
            lines.append(f"Не сопоставлены (после алиасов): {preview}{more}")
        super().__init__("\n".join(lines))


@dataclass
class MappingReport:
    matched: list[dict[str, str]] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    unused_headers: list[str] = field(default_factory=list)
    profile_id: str = "default"
    profile_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExcelLoadResult:
    dataframe: pd.DataFrame
    sheet_name: str
    header_row: int
    file_path: str
    mapping: MappingReport | None = None
    emk_variant: str | None = None  # "discharged" | "current" for EMK loads


@dataclass(frozen=True)
class KsgWorkbookLoadResult:
    ksg: ExcelLoadResult
    other_services: ExcelLoadResult | None = None


def clean_column_name(col) -> str:
    return re.sub(r"\s+", " ", str(col)).strip()


def normalize_header(s: str) -> str:
    """Нормализация для сравнения синонимов."""
    t = clean_column_name(s).lower().replace("ё", "е")
    t = t.replace("№", "n").replace("#", "n")
    t = re.sub(r"[\"'`]", "", t)
    t = re.sub(r"[^\w\s.+()/-]", " ", t, flags=re.UNICODE)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def _row_text(row: pd.Series) -> str:
    return row.astype(str).str.cat(sep=" ")


def find_header_row(
    raw_df: pd.DataFrame,
    required_fragments: Sequence[str],
    max_scan_rows: int = 80,
) -> int | None:
    limit = min(len(raw_df), max_scan_rows)
    lowered = [f.lower() for f in required_fragments]
    for i in range(limit):
        text = _row_text(raw_df.iloc[i]).lower()
        if all(frag in text for frag in lowered):
            return i
    return None


def build_rename_map(
    found_columns: Sequence[str],
    aliases: Mapping[str, Sequence[str]],
) -> tuple[dict[str, str], MappingReport]:
    """
    Строит rename: file_col -> canonical.
    При нескольких file-колонках на один канон — ColumnMappingConflictError.
    """
    # alias_norm -> canonical (first wins for same alias text across canons — rare)
    alias_to_canon: dict[str, str] = {}
    for canon, syns in aliases.items():
        for syn in syns or []:
            key = normalize_header(str(syn))
            if not key:
                continue
            alias_to_canon.setdefault(key, str(canon))
        # always map canonical to itself
        alias_to_canon.setdefault(normalize_header(str(canon)), str(canon))

    rename: dict[str, str] = {}
    canon_sources: dict[str, list[str]] = {}
    matched: list[dict[str, str]] = []
    unused: list[str] = []

    for col in found_columns:
        key = normalize_header(col)
        canon = alias_to_canon.get(key)
        if not canon:
            unused.append(str(col))
            continue
        rename[str(col)] = canon
        canon_sources.setdefault(canon, []).append(str(col))

    # Несколько колонок → один канон: предпочитаем точное совпадение имени, иначе — ошибка.
    for canon, srcs in list(canon_sources.items()):
        if len(srcs) <= 1:
            continue
        exact = [s for s in srcs if clean_column_name(s) == canon]
        if len(exact) == 1:
            winner = exact[0]
            for s in srcs:
                if s != winner:
                    rename.pop(s, None)
                    unused.append(s)
            canon_sources[canon] = [winner]
            continue
        if len(exact) > 1:
            parts = [f"«{canon}» ← {', '.join(exact)}"]
            raise ColumnMappingConflictError(
                "Несколько столбцов файла соответствуют одному полю:\n  • "
                + "\n  • ".join(parts)
            )
        parts = [f"«{canon}» ← {', '.join(srcs)}"]
        raise ColumnMappingConflictError(
            "Несколько столбцов файла соответствуют одному полю:\n  • "
            + "\n  • ".join(parts)
        )

    for col, canon in rename.items():
        matched.append({"file": col, "canonical": canon})

    report = MappingReport(matched=matched, unused_headers=unused)
    return rename, report


def apply_column_aliases(
    df: pd.DataFrame,
    aliases: Mapping[str, Sequence[str]],
    required_columns: Sequence[str],
    profile_id: str = "default",
    profile_name: str = "",
) -> tuple[pd.DataFrame, MappingReport]:
    rename, report = build_rename_map(list(df.columns), aliases)
    report.profile_id = profile_id
    report.profile_name = profile_name
    out = df.rename(columns=rename)
    # drop duplicate canonical columns if rename created any (shouldn't after conflict check)
    out = out.loc[:, ~out.columns.duplicated()].copy()
    missing = [c for c in required_columns if c not in out.columns]
    report.missing = missing
    if missing:
        raise MissingColumnsError(
            missing,
            found=list(df.columns),
            unmatched=report.unused_headers,
        )
    return out, report


def load_excel_with_header(
    file_path: str,
    required_fragments: Sequence[str],
    required_columns: Sequence[str],
    aliases: Mapping[str, Sequence[str]] | None = None,
    profile_id: str = "default",
    profile_name: str = "",
    progress: Callable[[str, float], None] | None = None,
    max_scan_rows: int = 80,
    preferred_sheets: Sequence[str] | None = None,
    strict_preferred_sheets: bool = False,
) -> ExcelLoadResult:
    """
    Ищет строку заголовков по ключевым словам на каждом листе,
    загружает таблицу, применяет синонимы и проверяет обязательные столбцы.
    """

    def report(msg: str, frac: float) -> None:
        if progress:
            progress(msg, max(0.0, min(1.0, frac)))

    report("Открытие книги…", 0.05)
    try:
        xls = pd.ExcelFile(file_path)
    except Exception as e:
        raise ExcelParseError(f"Не удалось открыть файл:\n{file_path}\n{e}") from e

    sheets = list(xls.sheet_names)
    if not sheets:
        raise ExcelParseError("В книге нет листов.")
    if preferred_sheets:
        ordered = [s for s in preferred_sheets if s in sheets]
        if strict_preferred_sheets:
            if not ordered:
                keys = ", ".join(f"«{k}»" for k in preferred_sheets)
                raise HeaderNotFoundError(f"Не найден лист из списка: {keys}.")
        else:
            ordered.extend(s for s in sheets if s not in ordered)
        sheets = ordered

    # Expand fragments with alias synonyms for header search
    search_frags = list(required_fragments)
    if aliases:
        for frag in list(required_fragments):
            for canon, syns in aliases.items():
                if normalize_header(frag) == normalize_header(canon) or any(
                    normalize_header(frag) == normalize_header(s) for s in (syns or [])
                ):
                    # use first synonym variants that appear as short fragments
                    for s in syns or []:
                        if s and s not in search_frags:
                            search_frags.append(str(s))
                    break

    sheet_used = None
    header_row_idx = None
    for idx, sheet in enumerate(sheets):
        report(f"Поиск заголовков: «{sheet}»…", 0.1 + 0.4 * (idx / max(len(sheets), 1)))
        try:
            raw_df = pd.read_excel(file_path, sheet_name=sheet, header=None, dtype=str)
        except Exception:
            continue
        # try original fragments first, then each pair from search
        header_row_idx = find_header_row(raw_df, required_fragments, max_scan_rows=max_scan_rows)
        if header_row_idx is None and len(search_frags) >= 2:
            # try first two search fragments as fallback
            header_row_idx = find_header_row(
                raw_df, search_frags[:2], max_scan_rows=max_scan_rows
            )
        if header_row_idx is not None:
            sheet_used = sheet
            break

    if sheet_used is None or header_row_idx is None:
        keys = ", ".join(f"«{k}»" for k in required_fragments)
        raise HeaderNotFoundError(
            f"Не найдена строка заголовков ни на одном листе.\n"
            f"Ожидались ключевые слова: {keys}."
        )

    report(f"Чтение листа «{sheet_used}»…", 0.7)
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_used, header=header_row_idx, dtype=str)
    except Exception as e:
        raise ExcelParseError(f"Ошибка чтения листа «{sheet_used}»:\n{e}") from e

    df.columns = [clean_column_name(c) for c in df.columns]
    df = df.dropna(how="all").copy()

    mapping: MappingReport | None = None
    if aliases:
        df, mapping = apply_column_aliases(
            df,
            aliases,
            required_columns,
            profile_id=profile_id,
            profile_name=profile_name,
        )
    else:
        missing = [col for col in required_columns if col not in df.columns]
        if missing:
            raise MissingColumnsError(missing, found=list(df.columns))
        mapping = MappingReport(
            matched=[{"file": c, "canonical": c} for c in required_columns if c in df.columns],
            unused_headers=[c for c in df.columns if c not in required_columns],
            profile_id=profile_id,
            profile_name=profile_name,
        )

    report("Готово", 1.0)
    return ExcelLoadResult(
        dataframe=df,
        sheet_name=sheet_used,
        header_row=int(header_row_idx),
        file_path=str(file_path),
        mapping=mapping,
    )


def deepcopy_profile(p: Mapping[str, Any]) -> dict[str, Any]:
    from copy import deepcopy

    return deepcopy(dict(p))


# Back-compat exports
LOR_HEADER_FRAGMENTS = tuple(DEFAULT_EMK_PROFILE["header_fragments"])
LOR_REQUIRED_COLUMNS = EMK_REQUIRED_COLUMNS
KSG_HEADER_FRAGMENTS = tuple(DEFAULT_KSG_PROFILE["header_fragments"])
# KSG_REQUIRED_COLUMNS imported from report_profiles

REPORT_KIND_LABELS: dict[str, str] = {
    "emk": "отчёт по заполнению ЭМК (вкладка «Анализ ЭМК»)",
    "ksg": "отчёт по КСГ (вкладка «Анализ КСГ»)",
    "ops": "отчёт по операциям (вкладка «Операции»)",
}

EMK_VARIANT_LABELS: dict[str, str] = {
    "discharged": "Выписанные",
    "current": "Текущие пациенты",
}


def detect_emk_variant(file_path: str, *, max_scan_rows: int = 12) -> str:
    """
    «current» — отчёт по пациентам в стационаре сейчас;
    «discharged» — суммарный отчёт по выписанным.
    """
    try:
        xls = pd.ExcelFile(file_path)
    except Exception:
        return "discharged"
    title_bits: list[str] = []
    for sheet in xls.sheet_names[:3]:
        try:
            raw = pd.read_excel(
                file_path, sheet_name=sheet, header=None, dtype=str, nrows=max_scan_rows
            )
        except Exception:
            continue
        for i in range(min(len(raw), max_scan_rows)):
            text = _row_text(raw.iloc[i]).lower().replace("ё", "е")
            title_bits.append(text)
            if "текущ" in text:
                return "current"
    # Fallback: no IDS column + placeholder discharge dates often mark current reports
    joined = " ".join(title_bits)
    if "выпис" in joined and "текущ" not in joined:
        return "discharged"
    return "discharged"


def emk_required_columns_for_variant(variant: str, base: Sequence[str] | None = None) -> list[str]:
    from report_profiles import EMK_CURRENT_OPTIONAL_REQUIRED

    cols = list(base or EMK_REQUIRED_COLUMNS)
    if variant == "current":
        return [c for c in cols if c not in EMK_CURRENT_OPTIONAL_REQUIRED]
    return cols


_REPORT_KIND_FRAGMENTS: dict[str, tuple[str, ...]] = {
    "emk": tuple(DEFAULT_EMK_PROFILE["header_fragments"]),
    "ksg": tuple(DEFAULT_KSG_PROFILE["header_fragments"]),
    "ops": tuple(DEFAULT_OPS_PROFILE["header_fragments"]),
}


def workbook_has_header_fragments(
    file_path: str,
    fragments: Sequence[str],
    *,
    max_scan_rows: int = 80,
) -> bool:
    """True, если на каком-либо листе есть строка со всеми ключевыми словами."""
    if not fragments:
        return False
    try:
        xls = pd.ExcelFile(file_path)
    except Exception:
        return False
    for sheet in xls.sheet_names:
        try:
            raw_df = pd.read_excel(file_path, sheet_name=sheet, header=None, dtype=str)
        except Exception:
            continue
        if find_header_row(raw_df, fragments, max_scan_rows=max_scan_rows) is not None:
            return True
    return False


def detect_report_kinds(file_path: str) -> list[str]:
    """Какие стандартные типы отчётов узнаются по заголовкам файла."""
    found: list[str] = []
    for kind, frags in _REPORT_KIND_FRAGMENTS.items():
        if workbook_has_header_fragments(file_path, frags):
            found.append(kind)
    return found


def format_wrong_report_hint(expected_kind: str, file_path: str) -> str:
    """Подсказка: загружен другой тип отчёта / неизвестный формат."""
    expected = REPORT_KIND_LABELS.get(expected_kind, "ожидаемый тип отчёта")
    others = [k for k in detect_report_kinds(file_path) if k != expected_kind]
    if others:
        looks_like = "; ".join(REPORT_KIND_LABELS[k] for k in others if k in REPORT_KIND_LABELS)
        return (
            f"\n\nПохоже, загружен не тот отчёт.\n"
            f"Сейчас ожидается: {expected}.\n"
            f"Этот файл больше похож на: {looks_like}."
        )
    return (
        f"\n\nВозможно, загружен не тот тип отчёта.\n"
        f"Сейчас ожидается: {expected}.\n"
        f"Проверьте файл или профиль формата в настройках."
    )


def _enrich_parse_error(
    exc: ExcelParseError,
    *,
    expected_kind: str,
    file_path: str,
) -> ExcelParseError:
    hint = format_wrong_report_hint(expected_kind, file_path)
    msg = f"{exc}{hint}"
    if isinstance(exc, MissingColumnsError):
        neo = MissingColumnsError(exc.missing, found=exc.found, unmatched=exc.unmatched)
        neo.args = (msg,)
        return neo
    return type(exc)(msg)


def _load_typed_excel(
    file_path: str,
    *,
    expected_kind: str,
    progress=None,
    profile: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | None = None,
    default_profile: Mapping[str, Any],
    kind_key: str,
    after_load: Callable[[ExcelLoadResult], ExcelLoadResult] | None = None,
    preferred_sheets: Sequence[str] | None = None,
    strict_preferred_sheets: bool = False,
) -> ExcelLoadResult:
    prof = dict(profile) if profile else (
        get_active_profile(dict(config or {}), kind_key)
        if config is not None
        else deepcopy_profile(default_profile)
    )
    try:
        result = load_excel_with_header(
            file_path,
            required_fragments=list(
                prof.get("header_fragments") or default_profile["header_fragments"]
            ),
            required_columns=list(
                prof.get("required_columns") or default_profile["required_columns"]
            ),
            aliases=prof.get("aliases") or {},
            profile_id=str(prof.get("id") or "default"),
            profile_name=str(prof.get("name") or ""),
            progress=progress,
            preferred_sheets=preferred_sheets,
            strict_preferred_sheets=strict_preferred_sheets,
        )
        if after_load is not None:
            result = after_load(result)
        return result
    except (HeaderNotFoundError, MissingColumnsError) as e:
        raise _enrich_parse_error(e, expected_kind=expected_kind, file_path=file_path) from e


def load_lor_excel(
    file_path: str,
    progress=None,
    profile: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | None = None,
) -> ExcelLoadResult:
    from report_profiles import EMK_REQUIRED_COLUMNS, get_active_profile

    variant = detect_emk_variant(file_path)
    prof = dict(profile) if profile else (
        get_active_profile(dict(config or {}), "emk")
        if config is not None
        else deepcopy_profile(DEFAULT_EMK_PROFILE)
    )
    base_required = list(prof.get("required_columns") or EMK_REQUIRED_COLUMNS)
    prof = dict(prof)
    prof["required_columns"] = emk_required_columns_for_variant(variant, base_required)
    # Ensure aliases know about admission / movement columns
    aliases = dict(prof.get("aliases") or {})
    from report_profiles import _default_emk_aliases

    defaults = _default_emk_aliases()
    for key in (
        "Дата и время поступления в указанном движении",
        "№ движения пациента в рамках госпитализации",
    ):
        if key not in aliases and key in defaults:
            aliases[key] = defaults[key]
    # Soft-required columns still map if present
    for key in EMK_REQUIRED_COLUMNS:
        if key not in aliases and key in defaults:
            aliases[key] = defaults[key]
    prof["aliases"] = aliases

    result = _load_typed_excel(
        file_path,
        expected_kind="emk",
        progress=progress,
        profile=prof,
        config=None,
        default_profile=DEFAULT_EMK_PROFILE,
        kind_key="emk",
    )
    return ExcelLoadResult(
        dataframe=result.dataframe,
        sheet_name=result.sheet_name,
        header_row=result.header_row,
        file_path=result.file_path,
        mapping=result.mapping,
        emk_variant=variant,
    )


def load_ksg_excel(
    file_path: str,
    progress=None,
    profile: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | None = None,
    *,
    preferred_sheets: Sequence[str] | None = None,
    strict_preferred_sheets: bool = False,
) -> ExcelLoadResult:
    from ksg_departments import normalize_ksg_departments

    def _require_dates(result: ExcelLoadResult) -> ExcelLoadResult:
        df = normalize_ksg_departments(result.dataframe)
        if "Поступление" not in df.columns and "Выписка" not in df.columns:
            raise MissingColumnsError(
                ["Поступление или Выписка"],
                found=list(df.columns),
                unmatched=(result.mapping.unused_headers if result.mapping else []),
            )
        return ExcelLoadResult(
            dataframe=df,
            sheet_name=result.sheet_name,
            header_row=result.header_row,
            file_path=result.file_path,
            mapping=result.mapping,
        )

    prof = dict(profile) if profile else (
        get_active_profile(dict(config or {}), "ksg")
        if config is not None
        else deepcopy_profile(DEFAULT_KSG_PROFILE)
    )

    def _load_with_profile(
        sheets: Sequence[str] | None,
        *,
        strict: bool = False,
    ) -> ExcelLoadResult:
        return _load_typed_excel(
            file_path,
            expected_kind="ksg",
            progress=progress,
            profile=prof,
            config=config,
            default_profile=DEFAULT_KSG_PROFILE,
            kind_key="ksg",
            after_load=_require_dates,
            preferred_sheets=sheets,
            strict_preferred_sheets=strict,
        )

    try:
        return _load_with_profile(preferred_sheets, strict=strict_preferred_sheets)
    except ExcelParseError:
        if preferred_sheets and not strict_preferred_sheets:
            return _load_with_profile(None)
        raise


OTHER_SERVICE_SHEET_NAMES: tuple[str, ...] = (
    "Др. услуги",
    "Др услуги",
    "Другие услуги",
)


def load_ksg_workbook(
    file_path: str,
    progress=None,
    profile: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | None = None,
) -> KsgWorkbookLoadResult:
    ksg = load_ksg_excel(
        file_path,
        progress=progress,
        profile=profile,
        config=config,
        preferred_sheets=("КСГ",),
    )
    other: ExcelLoadResult | None = None
    try:
        sheet_names = set(pd.ExcelFile(file_path).sheet_names)
    except Exception:
        sheet_names = set()
    other_sheet_candidates = [name for name in OTHER_SERVICE_SHEET_NAMES if name in sheet_names]
    if other_sheet_candidates:
        try:
            other = load_ksg_excel(
                file_path,
                progress=progress,
                profile=profile,
                config=config,
                preferred_sheets=tuple(other_sheet_candidates),
                strict_preferred_sheets=True,
            )
        except ExcelParseError:
            other = None
    return KsgWorkbookLoadResult(ksg=ksg, other_services=other)


def load_ops_excel(
    file_path: str,
    progress=None,
    profile: Mapping[str, Any] | None = None,
    config: Mapping[str, Any] | None = None,
) -> ExcelLoadResult:
    return _load_typed_excel(
        file_path,
        expected_kind="ops",
        progress=progress,
        profile=profile,
        config=config,
        default_profile=DEFAULT_OPS_PROFILE,
        kind_key="ops",
    )


def list_departments(df: pd.DataFrame, column: str = "Отделение") -> list[str]:
    if column not in df.columns:
        return []
    values = (
        df[column]
        .fillna("")
        .astype(str)
        .map(lambda x: clean_column_name(x))
        .loc[lambda s: s.str.len() > 0]
        .unique()
        .tolist()
    )
    return sorted(values, key=lambda s: s.lower())


def pick_default_department(
    departments: Iterable[str],
    preferred: str | None = None,
) -> str | None:
    """Выбор отделения: точное совпадение с preferred, иначе ближайшее по имени.

    Важно: «Терапевтическое отделение» не должно матчиться на
    «Второе терапевтическое отделение Молоково» раньше точного совпадения
    (раньше бралось первое substring-совпадение в алфавитном списке).
    """
    deps = list(departments)
    if not deps:
        return None
    preferred_s = (preferred or "").strip()
    if preferred_s:
        preferred_l = preferred_s.lower()
        # 1) точное совпадение (без учёта регистра)
        for d in deps:
            if str(d).strip().lower() == preferred_l:
                return d
        # 2) частичное: предпочитаем имя ближе всего к preferred по длине
        candidates: list[str] = []
        for d in deps:
            dl = str(d).strip().lower()
            if preferred_l in dl or dl in preferred_l:
                candidates.append(d)
        if candidates:
            candidates.sort(
                key=lambda d: (
                    abs(len(str(d).strip()) - len(preferred_s)),
                    len(str(d).strip()),
                    str(d).lower(),
                )
            )
            return candidates[0]
        # 3) запасной вариант для ЛОР, если preferred не найден в файле
        for d in deps:
            dl = str(d).lower()
            if "оторинолар" in dl or "лор" in dl:
                return d
    return deps[0]
