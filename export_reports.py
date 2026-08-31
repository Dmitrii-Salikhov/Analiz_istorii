"""Экспорт отчётов ЭМК/КСГ в Excel и TXT (без UI)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from gui.helpers import auto_adjust_excel_columns
from lor_analysis import LorAnalysisResult, format_doctor_name, violation_share_table

EMK_SECTIONS = (
    "Основные показатели",
    "Возрастные группы",
    "Нарушения (все)",
    "Сводка по врачам",
    "ИДС по врачам",
    "Длительные госпитализации",
    "СКП",
    "Метаданные",
)


def _section_on(sections: Mapping[str, Any] | None, name: str) -> bool:
    if not sections:
        return True
    return bool(sections.get(name, True))


def export_emk_txt(
    path: str | Path,
    result: LorAnalysisResult,
    *,
    file_name: str,
    department: str,
    sections: Mapping[str, Any] | None = None,
) -> str:
    out = Path(path)
    r = result
    with out.open("w", encoding="utf-8") as f:
        if _section_on(sections, "Метаданные"):
            f.write(f"Отчёт сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
            f.write(f"Исходный файл: {file_name}\n")
            f.write(f"Отделение: {department}\n")
            if r.period_start and r.period_end:
                f.write(
                    f"Период: {r.period_start.strftime('%d.%m.%Y')} — "
                    f"{r.period_end.strftime('%d.%m.%Y')}\n"
                )
            f.write("\n")
        if _section_on(sections, "Основные показатели"):
            f.write("ОСНОВНЫЕ ПОКАЗАТЕЛИ\n")
            f.write(f"Всего пациентов: {r.total_patients}\n")
            f.write(f"Средний койко-день: {r.avg_beddays:.2f}\n")
            f.write(f"Экстренные: {r.urgent}, Плановые: {r.planned}\n")
            f.write(
                f"СКП (0–1 к/д): {r.skp_count} "
                f"(0 дн.: {r.skp_days_0}, 1 дн.: {r.skp_days_1})\n"
            )
            share_df = violation_share_table(r.violations_df)
            if not share_df.empty:
                f.write("\nСтруктура нарушений:\n")
                for _, row in share_df.iterrows():
                    f.write(
                        f"  {row['Тип нарушения']}: {row['Количество']} ({row['Доля, %']}%)\n"
                    )
            f.write("\n")
        if _section_on(sections, "Возрастные группы"):
            f.write("ВОЗРАСТНЫЕ ГРУППЫ\n")
            for grp, cnt in r.age_dist.items():
                f.write(f"  {grp}: {cnt}\n")
            f.write("\n")
        if _section_on(sections, "Нарушения (все)"):
            f.write("НАРУШЕНИЯ\n")
            for _, row in r.violations_df.iterrows():
                f.write(f"{row['КВС']} | {row['врач']} | {row['нарушение']}\n")
            f.write("\n")
        if _section_on(sections, "Сводка по врачам"):
            f.write("СВОДКА ПО ВРАЧАМ (без учёта длительных госпитализаций и справочных проверок)\n")
            for _, row in r.doctor_stats.iterrows():
                f.write(f"{row['врач']}: {row['количество нарушений']} нарушений\n")
            f.write("\n")
        if _section_on(sections, "ИДС по врачам") and not r.ids_stats.empty:
            f.write("НАРУШЕНИЯ ПО ИДС\n")
            for _, row in r.ids_stats.iterrows():
                f.write(f"{row['врач']}: {row['нарушения по ИДС']} нарушений\n")
            f.write("\n")
        if _section_on(sections, "Длительные госпитализации") and not r.long_stay.empty:
            f.write(f"Длительные госпитализации (>7 дней): {len(r.long_stay)} случаев\n")
            for _, row in r.long_stay.iterrows():
                doctor = format_doctor_name(row.get("Лечащий врач"))
                days = int(row.get("Койко-дни_скор", 0))
                f.write(f"  • {row['Номер КВС']} ({doctor}) — {days} дн.\n")
        if _section_on(sections, "СКП") and r.skp_count:
            f.write(
                f"\nСКП (0–1 койко-день): {r.skp_count} "
                f"(0 дн.: {r.skp_days_0}, 1 дн.: {r.skp_days_1})\n"
            )
            if r.skp_cases is not None and not r.skp_cases.empty:
                f.write(r.skp_cases.to_string(index=False) + "\n")
            if r.skp_operations is not None and not r.skp_operations.empty:
                f.write("\nКоды услуг / операции по СКП:\n")
                f.write(r.skp_operations.to_string(index=False) + "\n")
    return str(out.resolve())


def export_emk_excel(
    path: str | Path,
    result: LorAnalysisResult,
    *,
    file_name: str,
    department: str,
    sections: Mapping[str, Any] | None = None,
) -> str:
    out = Path(path)
    r = result
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        if _section_on(sections, "Метаданные"):
            meta_rows = {
                "Параметр": ["Дата формирования", "Исходный файл", "Отделение"],
                "Значение": [
                    datetime.now().strftime("%d.%m.%Y %H:%M"),
                    file_name,
                    department,
                ],
            }
            if r.period_start and r.period_end:
                meta_rows["Параметр"].append("Период")
                meta_rows["Значение"].append(
                    f"{r.period_start.strftime('%d.%m.%Y')} — {r.period_end.strftime('%d.%m.%Y')}"
                )
            meta = pd.DataFrame(meta_rows)
            meta.to_excel(writer, sheet_name="Метаданные", index=False)
            auto_adjust_excel_columns(writer, "Метаданные", meta)
        if _section_on(sections, "Основные показатели"):
            summary = pd.DataFrame(
                {
                    "Показатель": [
                        "Всего пациентов",
                        "Средний койко-день",
                        "Экстренные",
                        "Плановые",
                        "СКП всего (0–1 к/д)",
                        "СКП 0 койко-дней",
                        "СКП 1 койко-день",
                    ],
                    "Значение": [
                        r.total_patients,
                        f"{r.avg_beddays:.2f}",
                        r.urgent,
                        r.planned,
                        r.skp_count,
                        r.skp_days_0,
                        r.skp_days_1,
                    ],
                }
            )
            summary.to_excel(writer, sheet_name="Основные показатели", index=False)
            auto_adjust_excel_columns(writer, "Основные показатели", summary)
            share_df = violation_share_table(r.violations_df)
            if not share_df.empty:
                share_df.to_excel(writer, sheet_name="Структура нарушений", index=False)
                auto_adjust_excel_columns(writer, "Структура нарушений", share_df)
        if _section_on(sections, "Возрастные группы"):
            age_df = r.age_dist.reset_index()
            age_df.columns = ["Возрастная группа", "Количество"]
            age_df.to_excel(writer, sheet_name="Возрастные группы", index=False)
            auto_adjust_excel_columns(writer, "Возрастные группы", age_df)
        if _section_on(sections, "Нарушения (все)"):
            r.violations_df.to_excel(writer, sheet_name="Нарушения", index=False)
            auto_adjust_excel_columns(writer, "Нарушения", r.violations_df)
        if _section_on(sections, "Сводка по врачам"):
            r.doctor_stats.to_excel(writer, sheet_name="Сводка по врачам", index=False)
            auto_adjust_excel_columns(writer, "Сводка по врачам", r.doctor_stats)
        if _section_on(sections, "ИДС по врачам") and not r.ids_stats.empty:
            r.ids_stats.to_excel(writer, sheet_name="ИДС по врачам", index=False)
            auto_adjust_excel_columns(writer, "ИДС по врачам", r.ids_stats)
        if _section_on(sections, "Длительные госпитализации") and not r.long_stay.empty:
            long_df = r.long_stay[
                ["Номер КВС", "Возраст", "Койко-дни_скор", "Лечащий врач"]
            ].copy()
            long_df.columns = ["КВС", "Возраст", "Койко-дни", "Врач"]
            long_df.to_excel(writer, sheet_name="Длительные госпитализации", index=False)
            auto_adjust_excel_columns(writer, "Длительные госпитализации", long_df)
        if _section_on(sections, "СКП") and r.skp_count:
            if r.skp_cases is not None and not r.skp_cases.empty:
                r.skp_cases.to_excel(writer, sheet_name="СКП истории", index=False)
                auto_adjust_excel_columns(writer, "СКП истории", r.skp_cases)
            if r.skp_operations is not None and not r.skp_operations.empty:
                r.skp_operations.to_excel(writer, sheet_name="СКП операции", index=False)
                auto_adjust_excel_columns(writer, "СКП операции", r.skp_operations)
    return str(out.resolve())


def export_ksg_txt(
    path: str | Path,
    results: dict[str, Any],
    *,
    file_name: str,
    settings: Mapping[str, Any] | None = None,
    department: str = "",
    period_label: str = "",
) -> str:
    out = Path(path)
    r = results
    settings = settings or {}
    with out.open("w", encoding="utf-8") as f:
        f.write(f"Отчёт сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
        f.write(f"Исходный файл: {file_name}\n")
        if department:
            f.write(f"Отделение: {department}\n")
        if period_label:
            f.write(f"Период: {period_label}\n")
        f.write("\n")
        f.write(f"Общее количество пациентов: {r['total_patients']}\n")
        f.write("Пациенты по врачам:\n")
        f.write(r["patient_counts"].to_string(index=False) + "\n\n")
        f.write("Операции:\n")
        f.write(r["ops_pivot"].to_string() + "\n\n")
        f.write(f"Общая сумма: {r['total_sum']:,.2f}\n\n")
        f.write("Сумма по врачам:\n")
        f.write(r["sum_by_doctor"].to_string(index=False) + "\n\n")
        if not r["low_money"].empty:
            f.write(f"Случаи с суммой < {settings.get('ksg_threshold_low', '')}:\n")
            f.write(r["low_money"].to_string(index=False) + "\n\n")
        if not r["high_money"].empty:
            f.write(f"Случаи с суммой > {settings.get('ksg_threshold_high', '')}:\n")
            f.write(r["high_money"].to_string(index=False) + "\n\n")
        if not r["kslp_issues"].empty:
            f.write("Нарушения КСЛП:\n")
            f.write(r["kslp_issues"].to_string(index=False) + "\n\n")
        if not r.get("policy_issues", pd.DataFrame()).empty:
            f.write("Полис / СМО:\n")
            f.write(r["policy_issues"].to_string(index=False) + "\n\n")
        f.write("Средний КЗ:\n")
        f.write(r["avg_kz_doctor"].to_string(index=False) + "\n")
        f.write(f"Средний по отделению: {r['avg_kz_total']}\n")
    return str(out.resolve())


def export_ksg_excel(
    path: str | Path,
    results: dict[str, Any],
    *,
    file_name: str,
    department: str = "",
    period_label: str = "",
) -> str:
    out = Path(path)
    r = results
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        meta_rows = [
            ("Дата", datetime.now().strftime("%d.%m.%Y %H:%M")),
            ("Файл", file_name),
        ]
        if department:
            meta_rows.append(("Отделение", department))
        if period_label:
            meta_rows.append(("Период", period_label))
        meta = pd.DataFrame({"Параметр": [x[0] for x in meta_rows], "Значение": [x[1] for x in meta_rows]})
        meta.to_excel(writer, sheet_name="Метаданные", index=False)
        auto_adjust_excel_columns(writer, "Метаданные", meta)
        r["patient_counts"].to_excel(writer, sheet_name="Пациенты по врачам", index=False)
        auto_adjust_excel_columns(writer, "Пациенты по врачам", r["patient_counts"])
        if not r["ops_pivot"].empty:
            r["ops_pivot"].to_excel(writer, sheet_name="Операции")
            auto_adjust_excel_columns(writer, "Операции", r["ops_pivot"].reset_index())
        pd.DataFrame({"Общая сумма": [r["total_sum"]]}).to_excel(writer, sheet_name="Сумма", index=False)
        r["sum_by_doctor"].to_excel(writer, sheet_name="Сумма по врачам", index=False)
        auto_adjust_excel_columns(writer, "Сумма по врачам", r["sum_by_doctor"])
        if not r["low_money"].empty:
            r["low_money"].to_excel(writer, sheet_name="Дешёвые случаи", index=False)
            auto_adjust_excel_columns(writer, "Дешёвые случаи", r["low_money"])
        if not r["high_money"].empty:
            r["high_money"].to_excel(writer, sheet_name="Дорогие случаи", index=False)
            auto_adjust_excel_columns(writer, "Дорогие случаи", r["high_money"])
        if not r["kslp_issues"].empty:
            r["kslp_issues"].to_excel(writer, sheet_name="КСЛП нарушения", index=False)
            auto_adjust_excel_columns(writer, "КСЛП нарушения", r["kslp_issues"])
        policy_issues = r.get("policy_issues")
        if policy_issues is not None and isinstance(policy_issues, pd.DataFrame) and not policy_issues.empty:
            policy_issues.to_excel(writer, sheet_name="Полис и СМО", index=False)
            auto_adjust_excel_columns(writer, "Полис и СМО", policy_issues)
        r["avg_kz_doctor"].to_excel(writer, sheet_name="Средний КЗ", index=False)
        auto_adjust_excel_columns(writer, "Средний КЗ", r["avg_kz_doctor"])
        by_dep = r.get("by_department")
        if by_dep is not None and isinstance(by_dep, pd.DataFrame) and not by_dep.empty:
            by_dep.to_excel(writer, sheet_name="По отделениям", index=False)
            auto_adjust_excel_columns(writer, "По отделениям", by_dep)
    return str(out.resolve())


OPS_SECTIONS = (
    "Сводка",
    "Длительные",
    "Без_стола",
)


def export_ops_txt(
    path: str | Path,
    result: Any,
    *,
    file_name: str,
) -> str:
    out = Path(path)
    with out.open("w", encoding="utf-8") as f:
        f.write(f"Отчёт сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
        f.write(f"Исходный файл: {file_name}\n")
        if getattr(result, "department", None):
            f.write(f"Отделение: {result.department}\n")
        f.write(f"Порог длительной операции: > {result.long_op_hours:g} ч\n\n")
        f.write(f"Всего операций: {result.total_ops}\n")
        f.write(f"Длительных: {result.long_count}\n")
        f.write(f"Без опер.стола: {result.missing_table_count}\n\n")
        f.write("ДЛИТЕЛЬНЫЕ ОПЕРАЦИИ\n")
        for row in result.long_ops:
            f.write(
                f"{row.get('КВС')} | {row.get('Пациент')} | {row.get('Хирург')} | "
                f"{row.get('Услуга')} | {row.get('Длительность')} | {row.get('Причина')}\n"
            )
        f.write("\nБЕЗ ОПЕР.СТОЛА\n")
        for row in result.missing_table:
            f.write(
                f"{row.get('КВС')} | {row.get('Пациент')} | {row.get('Хирург')} | "
                f"{row.get('Услуга')} | {row.get('Причина')}\n"
            )
    return str(out.resolve())


def export_ops_excel(
    path: str | Path,
    result: Any,
    *,
    file_name: str,
) -> str:
    out = Path(path)
    long_df = pd.DataFrame(result.long_ops)
    miss_df = pd.DataFrame(result.missing_table)
    with pd.ExcelWriter(out, engine="openpyxl") as writer:
        meta = pd.DataFrame(
            {
                "Параметр": [
                    "Дата",
                    "Файл",
                    "Отделение",
                    "Порог длительности, ч",
                    "Всего операций",
                    "Длительных",
                    "Без опер.стола",
                ],
                "Значение": [
                    datetime.now().strftime("%d.%m.%Y %H:%M"),
                    file_name,
                    getattr(result, "department", "") or "",
                    result.long_op_hours,
                    result.total_ops,
                    result.long_count,
                    result.missing_table_count,
                ],
            }
        )
        meta.to_excel(writer, sheet_name="Сводка", index=False)
        auto_adjust_excel_columns(writer, "Сводка", meta)
        cols = ["КВС", "Пациент", "Хирург", "Услуга", "Длительность", "Причина", "Опер.стол", "Отделение"]
        if long_df.empty:
            long_df = pd.DataFrame(columns=cols)
        else:
            long_df = long_df.reindex(columns=[c for c in cols if c in long_df.columns])
        long_df.to_excel(writer, sheet_name="Длительные", index=False)
        auto_adjust_excel_columns(writer, "Длительные", long_df)
        if miss_df.empty:
            miss_df = pd.DataFrame(columns=cols)
        else:
            miss_df = miss_df.reindex(columns=[c for c in cols if c in miss_df.columns])
        miss_df.to_excel(writer, sheet_name="Без_стола", index=False)
        auto_adjust_excel_columns(writer, "Без_стола", miss_df)
    return str(out.resolve())
