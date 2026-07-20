"""Описания изменений по версиям (показываются после обновления)."""
from __future__ import annotations

from updater import parse_version

# Новые версии — в начале списка.
CHANGELOG: list[dict] = [
    {
        "version": "1.0.7",
        "title": "Что нового в версии 1.0.7",
        "items": [
            "После обновления показывается окно с описанием новых функций.",
            "Копирование данных в буфер обмена через ⌘C / Ctrl+C "
            "(выделенные строки таблиц и текст).",
            "⌘⇧C / Ctrl+Shift+C — копировать сводку показателей.",
            "Подсказки с горячими клавишами на кнопках, в меню «Правка» "
            "и в контекстном меню таблиц.",
            "В меню «Справка» можно снова открыть «Что нового».",
        ],
    },
    {
        "version": "1.0.6",
        "title": "Что нового в версии 1.0.6",
        "items": [
            "Кнопки «Копировать всё» и «Копировать выбранные» на вкладке "
            "нарушений ЭМК больше не уезжают за край окна.",
            "Категории нарушений отображаются сеткой в несколько колонок.",
        ],
    },
    {
        "version": "1.0.5",
        "title": "Что нового в версии 1.0.5",
        "items": [
            "Единая панель действий: загрузка слева, сохранение и копирование справа.",
            "Сохранение Excel по умолчанию, TXT — через меню ▾.",
            "Параметры экспорта ЭМК перенесены в диалог сохранения.",
            "KPI-карточки показателей, компактная строка статуса.",
            "Уведомление «Скопировано» без лишнего окна OK.",
            "В КСГ: сегменты сводки и чипы выбора месяцев для сравнения.",
            "Запоминается последняя открытая вкладка (ЭМК / КСГ).",
        ],
    },
]


def notes_between(from_version: str | None, to_version: str) -> list[dict]:
    """Записи changelog для версий (from_version; to_version]."""
    to_v = parse_version(to_version)
    from_v = parse_version(from_version) if from_version else (0, 0, 0)
    selected = []
    for entry in CHANGELOG:
        ver = parse_version(entry["version"])
        if from_v < ver <= to_v:
            selected.append(entry)
    # Показывать от новой к старой
    selected.sort(key=lambda e: parse_version(e["version"]), reverse=True)
    return selected


def format_notes(entries: list[dict]) -> str:
    if not entries:
        return "В этой версии исправления и улучшения стабильности."
    blocks: list[str] = []
    for entry in entries:
        lines = [entry.get("title") or f"Версия {entry['version']}", ""]
        for item in entry.get("items") or []:
            lines.append(f"• {item}")
        blocks.append("\n".join(lines))
    return "\n\n".join(blocks)
