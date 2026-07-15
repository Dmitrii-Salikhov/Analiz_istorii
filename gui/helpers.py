"""Вспомогательные UI-утилиты (экспорт, папки, Excel)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tkinter import messagebox

import pandas as pd


def auto_adjust_excel_columns(writer, sheet_name: str, df: pd.DataFrame, index: bool = False) -> None:
    worksheet = writer.sheets[sheet_name]
    start_col = 2 if index else 1
    if index:
        max_len = len(str(df.index.name or "")) + 2
        for val in df.index:
            max_len = max(max_len, len(str(val)) + 2)
        worksheet.column_dimensions["A"].width = min(max_len, 40)

    for i, col in enumerate(df.columns):
        max_len = len(str(col)) + 2
        for val in df[col]:
            max_len = max(max_len, len(str(val)) + 2)
        letter = worksheet.cell(row=1, column=i + start_col).column_letter
        worksheet.column_dimensions[letter].width = min(max_len, 60)


def offer_open_folder(file_path: str, title: str = "Сохранено") -> None:
    path = Path(file_path).resolve()
    folder = str(path.parent)
    open_it = messagebox.askyesno(
        title,
        f"Файл сохранён:\n{path}\n\nОткрыть папку?",
    )
    if not open_it:
        return
    try:
        if sys.platform == "darwin":
            subprocess.run(["open", folder], check=False)
        elif sys.platform == "win32":
            os.startfile(folder)  # type: ignore[attr-defined]
        else:
            subprocess.run(["xdg-open", folder], check=False)
    except OSError as e:
        messagebox.showwarning("Папка", f"Не удалось открыть папку:\n{e}")


def build_empty_state(parent, title: str, steps: list[str], load_text: str, on_load) -> object:
    """Пустой экран с шагами и кнопкой загрузки. Возвращает фрейм."""
    import tkinter as tk
    import ttkbootstrap as ttkb

    wrap = ttkb.Frame(parent, padding=24)
    card = ttkb.Labelframe(wrap, text=title, padding=20, bootstyle="info")
    card.pack(expand=True, fill=tk.BOTH, padx=40, pady=30)
    ttkb.Label(
        card,
        text="Перетащите Excel-файл в окно или нажмите кнопку ниже",
        font=("Calibri", 14),
    ).pack(pady=(0, 12))
    for i, step in enumerate(steps, start=1):
        ttkb.Label(card, text=f"{i}. {step}", font=("Calibri", 12)).pack(anchor=tk.W, pady=2)
    ttkb.Button(card, text=load_text, command=on_load, bootstyle="info", padding=(24, 8)).pack(
        pady=18
    )
    return wrap
