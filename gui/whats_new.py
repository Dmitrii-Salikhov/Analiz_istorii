"""Диалог «Что нового» после обновления."""
from __future__ import annotations

import tkinter as tk

import ttkbootstrap as ttkb

from changelog import format_notes, notes_between
from gui.chrome import PRIMARY_PAD


def show_whats_new(
    parent,
    current_version: str,
    previous_version: str | None,
    *,
    force: bool = False,
) -> bool:
    """
    Показывает окно с описанием изменений.
    Возвращает True, если диалог был показан.
    """
    entries = notes_between(previous_version, current_version)
    if not entries and not force:
        return False
    if force and not entries:
        entries = notes_between(None, current_version)[:1] or [
            {
                "version": current_version,
                "title": f"Версия {current_version}",
                "items": ["Описание изменений для этой версии пока не заполнено."],
            }
        ]

    dialog = tk.Toplevel(parent)
    dialog.title(f"Что нового — v{current_version}")
    dialog.transient(parent)
    dialog.grab_set()
    dialog.minsize(480, 360)
    dialog.geometry("560x420")

    header = ttkb.Frame(dialog, padding=(16, 14))
    header.pack(fill=tk.X)
    ttkb.Label(
        header,
        text=f"Обновление до версии {current_version}",
        font=("Calibri", 16, "bold"),
        bootstyle="primary",
    ).pack(anchor=tk.W)
    if previous_version:
        ttkb.Label(
            header,
            text=f"Предыдущая версия: {previous_version}",
            font=("Calibri", 11),
            bootstyle="secondary",
        ).pack(anchor=tk.W, pady=(4, 0))

    body = ttkb.Frame(dialog, padding=(16, 0))
    body.pack(fill=tk.BOTH, expand=True)

    text = tk.Text(
        body,
        wrap=tk.WORD,
        font=("Segoe UI", 11),
        height=14,
        padx=8,
        pady=8,
        relief=tk.FLAT,
    )
    scroll = ttkb.Scrollbar(body, orient=tk.VERTICAL, command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    scroll.pack(side=tk.RIGHT, fill=tk.Y)

    text.insert(tk.END, format_notes(entries))
    text.configure(state=tk.DISABLED)

    footer = ttkb.Frame(dialog, padding=(16, 12))
    footer.pack(fill=tk.X)

    def close():
        try:
            dialog.grab_release()
        except tk.TclError:
            pass
        dialog.destroy()

    ttkb.Button(
        footer,
        text="Понятно",
        command=close,
        bootstyle="success",
        padding=PRIMARY_PAD,
    ).pack(side=tk.RIGHT)

    dialog.protocol("WM_DELETE_WINDOW", close)
    dialog.bind("<Return>", lambda _e: close())
    dialog.bind("<Escape>", lambda _e: close())

    try:
        parent.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() - 560) // 2
        y = parent.winfo_rooty() + (parent.winfo_height() - 420) // 2
        dialog.geometry(f"+{max(40, x)}+{max(40, y)}")
    except tk.TclError:
        pass

    dialog.wait_window()
    return True
