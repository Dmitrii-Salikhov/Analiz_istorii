"""Надёжное чтение Excel-отчётов с понятными ошибками."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Iterable, Sequence

import pandas as pd


class ExcelParseError(Exception):
    """Базовая ошибка разбора Excel."""


class HeaderNotFoundError(ExcelParseError):
    pass


class MissingColumnsError(ExcelParseError):
    def __init__(self, missing: Sequence[str], found: Sequence[str] | None = None):
        self.missing = list(missing)
        self.found = list(found or [])
        lines = ["В файле отсутствуют обязательные столбцы:"]
        for col in self.missing:
            lines.append(f"  • {col}")
        if self.found:
            preview = ", ".join(self.found[:12])
            more = f" (+ ещё {len(self.found) - 12})" if len(self.found) > 12 else ""
            lines.append("")
            lines.append(f"Найденные столбцы: {preview}{more}")
        super().__init__("\n".join(lines))


@dataclass(frozen=True)
class ExcelLoadResult:
    dataframe: pd.DataFrame
    sheet_name: str
    header_row: int
    file_path: str


def clean_column_name(col) -> str:
    return re.sub(r"\s+", " ", str(col)).strip()


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


def load_excel_with_header(
    file_path: str,
    required_fragments: Sequence[str],
    required_columns: Sequence[str],
    progress: Callable[[str, float], None] | None = None,
    max_scan_rows: int = 80,
) -> ExcelLoadResult:
    """
    Ищет строку заголовков по ключевым словам на каждом листе,
    загружает таблицу и проверяет обязательные столбцы.
    progress(message, fraction 0..1) — опциональный колбэк прогресса.
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

    sheet_used = None
    header_row_idx = None
    for idx, sheet in enumerate(sheets):
        report(f"Поиск заголовков: «{sheet}»…", 0.1 + 0.4 * (idx / max(len(sheets), 1)))
        try:
            raw_df = pd.read_excel(file_path, sheet_name=sheet, header=None, dtype=str)
        except Exception:
            continue
        header_row_idx = find_header_row(raw_df, required_fragments, max_scan_rows=max_scan_rows)
        if header_row_idx is not None:
            sheet_used = sheet
            break

    if sheet_used is None or header_row_idx is None:
        keys = ", ".join(f"«{k}»" for k in required_fragments)
        raise HeaderNotFoundError(
            f"Не найдена строка заголовков ни на одном листе.\n"
            f"Ожидались ключевые слова: {keys}"
        )

    report(f"Чтение листа «{sheet_used}»…", 0.7)
    try:
        df = pd.read_excel(file_path, sheet_name=sheet_used, header=header_row_idx, dtype=str)
    except Exception as e:
        raise ExcelParseError(f"Ошибка чтения листа «{sheet_used}»:\n{e}") from e

    df.columns = [clean_column_name(c) for c in df.columns]
    # Убираем полностью пустые строки
    df = df.dropna(how="all").copy()

    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise MissingColumnsError(missing, found=list(df.columns))

    report("Готово", 1.0)
    return ExcelLoadResult(
        dataframe=df,
        sheet_name=sheet_used,
        header_row=int(header_row_idx),
        file_path=str(file_path),
    )


LOR_HEADER_FRAGMENTS = ("Номер КВС", "Возраст на момент госпитализации")
LOR_REQUIRED_COLUMNS = (
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

KSG_HEADER_FRAGMENTS = ("№ талона", "Код услуги")
KSG_REQUIRED_COLUMNS = (
    "№ талона",
    "Врач",
    "Код услуги",
    "Сумма к оплате",
    "Дата рождения",
    "КСЛП итоговый",
    "КЗ",
)


def load_lor_excel(file_path: str, progress=None) -> ExcelLoadResult:
    return load_excel_with_header(
        file_path,
        required_fragments=LOR_HEADER_FRAGMENTS,
        required_columns=LOR_REQUIRED_COLUMNS,
        progress=progress,
    )


def load_ksg_excel(file_path: str, progress=None) -> pd.DataFrame:
    result = load_excel_with_header(
        file_path,
        required_fragments=KSG_HEADER_FRAGMENTS,
        required_columns=KSG_REQUIRED_COLUMNS,
        progress=progress,
    )
    df = result.dataframe
    if "Поступление" not in df.columns and "Выписка" not in df.columns:
        raise MissingColumnsError(
            ["Поступление или Выписка"],
            found=list(df.columns),
        )
    return df


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
    deps = list(departments)
    if not deps:
        return None
    if preferred:
        preferred_l = preferred.lower()
        for d in deps:
            if preferred_l in d.lower() or d.lower() in preferred_l:
                return d
        for d in deps:
            if "оторинолар" in d.lower() or "лор" in d.lower():
                return d
    return deps[0]
