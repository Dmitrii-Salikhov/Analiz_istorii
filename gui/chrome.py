"""Общие элементы интерфейса: toast, tooltip, KPI-карточки, сегменты, панель действий."""
from __future__ import annotations

import sys
import tkinter as tk
from typing import Callable, Sequence

import ttkbootstrap as ttkb

ACCENT = "primary"
PRIMARY_PAD = (22, 10)
SECONDARY_PAD = (12, 6)


def hotkey_hint(mac: str, win: str | None = None) -> str:
    if sys.platform == "darwin":
        return mac
    return win or mac.replace("⌘", "Ctrl+")


class ToolTip:
    """Простая подсказка при наведении."""

    def __init__(self, widget, text: str, delay_ms: int = 450):
        self.widget = widget
        self.text = text
        self.delay_ms = delay_ms
        self._after = None
        self._tip: tk.Toplevel | None = None
        widget.bind("<Enter>", self._schedule, add="+")
        widget.bind("<Leave>", self._hide, add="+")
        widget.bind("<ButtonPress>", self._hide, add="+")

    def _schedule(self, _event=None):
        self._hide()
        self._after = self.widget.after(self.delay_ms, self._show)

    def _show(self):
        if self._tip or not self.text:
            return
        x = self.widget.winfo_rootx() + 12
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 6
        self._tip = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(
            tw,
            text=self.text,
            justify=tk.LEFT,
            background="#2C3E50",
            foreground="white",
            relief=tk.SOLID,
            borderwidth=0,
            font=("Segoe UI", 9),
            padx=8,
            pady=4,
        ).pack()

    def _hide(self, _event=None):
        if self._after:
            try:
                self.widget.after_cancel(self._after)
            except Exception:
                pass
            self._after = None
        if self._tip:
            try:
                self._tip.destroy()
            except Exception:
                pass
            self._tip = None


def show_toast(root, message: str, duration_ms: int = 1600) -> None:
    """Короткое уведомление без кнопки OK."""
    if root is None:
        return
    toast = tk.Toplevel(root)
    toast.overrideredirect(True)
    toast.attributes("-topmost", True)
    try:
        root.update_idletasks()
        rw = root.winfo_width()
        rh = root.winfo_height()
        rx = root.winfo_rootx()
        ry = root.winfo_rooty()
    except tk.TclError:
        rw = rh = 400
        rx = ry = 100
    frame = ttkb.Frame(toast, bootstyle="dark", padding=(14, 10))
    frame.pack(fill=tk.BOTH, expand=True)
    ttkb.Label(frame, text=message, bootstyle="inverse-dark", font=("Segoe UI", 10)).pack()
    toast.update_idletasks()
    tw = toast.winfo_reqwidth()
    th = toast.winfo_reqheight()
    x = rx + max(12, (rw - tw) // 2)
    y = ry + rh - th - 28
    toast.geometry(f"+{x}+{y}")

    def _close():
        try:
            toast.destroy()
        except tk.TclError:
            pass

    toast.after(duration_ms, _close)


def notify_copied(host, message: str = "Скопировано") -> None:
    root = host.winfo_toplevel() if hasattr(host, "winfo_toplevel") else host
    show_toast(root, message)


def make_kpi_card(parent, title: str, value: str, on_click=None) -> ttkb.Frame:
    """Карточка показателя с hover и опциональным кликом."""
    card = ttkb.Frame(parent, bootstyle="light", padding=14)
    title_lbl = ttkb.Label(card, text=title, font=("Calibri", 12), bootstyle="secondary")
    title_lbl.pack(anchor=tk.W)
    value_lbl = ttkb.Label(card, text=value, font=("Calibri", 22, "bold"), bootstyle="primary")
    value_lbl.pack(anchor=tk.W, pady=(4, 0))

    def _enter(_e=None):
        try:
            card.configure(bootstyle="info")
        except tk.TclError:
            pass

    def _leave(_e=None):
        try:
            card.configure(bootstyle="light")
        except tk.TclError:
            pass

    targets = [card, title_lbl, value_lbl]
    for w in targets:
        w.bind("<Enter>", _enter, add="+")
        w.bind("<Leave>", _leave, add="+")
        if on_click:
            w.bind("<Button-1>", lambda e, fn=on_click: fn(), add="+")
            try:
                w.configure(cursor="hand2")
            except tk.TclError:
                pass
    return card


class SegmentControl(ttkb.Frame):
    """Горизонтальный переключатель секций вместо вложенного Notebook."""

    def __init__(self, parent, labels: Sequence[str], on_change: Callable[[int], None], **kwargs):
        super().__init__(parent, **kwargs)
        self.on_change = on_change
        self.buttons: list[ttkb.Button] = []
        self._index = 0
        for i, label in enumerate(labels):
            btn = ttkb.Button(
                self,
                text=label,
                bootstyle="primary" if i == 0 else "secondary-outline",
                padding=(12, 6),
                command=lambda idx=i: self.select(idx),
            )
            btn.pack(side=tk.LEFT, padx=3)
            self.buttons.append(btn)

    def select(self, index: int, notify: bool = True) -> None:
        if index < 0 or index >= len(self.buttons):
            return
        self._index = index
        for i, btn in enumerate(self.buttons):
            btn.configure(bootstyle="primary" if i == index else "secondary-outline")
        if notify:
            self.on_change(index)

    @property
    def index(self) -> int:
        return self._index


class SplitSaveButton(ttkb.Frame):
    """Основной клик = Excel; стрелка = меню (Excel / TXT)."""

    def __init__(self, parent, on_excel, on_txt, tooltip: str = "", **kwargs):
        super().__init__(parent, **kwargs)
        self.on_excel = on_excel
        self.on_txt = on_txt
        self.main_btn = ttkb.Button(
            self,
            text="Сохранить Excel",
            command=on_excel,
            bootstyle="success",
            padding=PRIMARY_PAD,
        )
        self.main_btn.pack(side=tk.LEFT)
        self.menu_btn = ttkb.Button(
            self,
            text="▾",
            command=self._open_menu,
            bootstyle="success-outline",
            padding=(10, 10),
            width=3,
        )
        self.menu_btn.pack(side=tk.LEFT, padx=(2, 0))
        self._menu = tk.Menu(self, tearoff=0)
        self._menu.add_command(label="Сохранить Excel…", command=on_excel)
        self._menu.add_command(label="Сохранить TXT…", command=on_txt)
        if tooltip:
            ToolTip(self.main_btn, tooltip)
            ToolTip(self.menu_btn, "Другие форматы")

    def _open_menu(self):
        try:
            self._menu.tk_popup(
                self.menu_btn.winfo_rootx(),
                self.menu_btn.winfo_rooty() + self.menu_btn.winfo_height(),
            )
        finally:
            self._menu.grab_release()

    def set_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        self.main_btn.configure(state=state)
        self.menu_btn.configure(state=state)


def build_context_bar(
    parent,
    titles: Sequence[tuple[str, str]] | None = None,
) -> tuple[ttkb.Frame, dict[str, ttkb.Label]]:
    """Компактная серая строка статуса. titles: [(key, title), ...]."""
    bar = ttkb.Frame(parent, bootstyle="secondary", padding=(10, 6))
    labels: dict[str, ttkb.Label] = {}
    items = list(titles) if titles else [
        ("file", "Файл"),
        ("period", "Период"),
        ("extra", "Контекст"),
        ("stat", "Показатель"),
    ]
    for key, title in items:
        cell = ttkb.Frame(bar)
        cell.pack(side=tk.LEFT, padx=(0, 18))
        ttkb.Label(cell, text=title, font=("Segoe UI", 8), bootstyle="secondary").pack(anchor=tk.W)
        lbl = ttkb.Label(cell, text="—", font=("Consolas", 10, "bold"))
        lbl.pack(anchor=tk.W)
        labels[key] = lbl
    return bar, labels


class MonthChips(ttkb.Frame):
    """Чипы выбора месяцев вместо длинного списка чекбоксов."""

    def __init__(self, parent, labels: Sequence[str], max_selected: int = 12, **kwargs):
        super().__init__(parent, **kwargs)
        self.max_selected = max_selected
        self.vars: list[tk.BooleanVar] = []
        self._buttons: list[ttkb.Checkbutton] = []
        self.set_labels(labels)

    def set_labels(self, labels: Sequence[str]) -> None:
        for w in self.winfo_children():
            w.destroy()
        self.vars = []
        self._buttons = []
        for label in labels:
            var = tk.BooleanVar(value=False)
            self.vars.append(var)
            btn = ttkb.Checkbutton(
                self,
                text=label,
                variable=var,
                bootstyle="primary-toolbutton",
                padding=(10, 5),
                command=self._enforce_limit,
            )
            btn.pack(side=tk.LEFT, padx=3, pady=2)
            self._buttons.append(btn)

    def _enforce_limit(self) -> None:
        selected = [v for v in self.vars if v.get()]
        if len(selected) <= self.max_selected:
            return
        # Снять последний включённый сверх лимита
        for var in reversed(self.vars):
            if var.get() and len([v for v in self.vars if v.get()]) > self.max_selected:
                var.set(False)
                break

    def selected_indices(self) -> list[int]:
        return [i for i, var in enumerate(self.vars) if var.get()]

    def select_all(self) -> None:
        for i, var in enumerate(self.vars):
            var.set(i < self.max_selected)

    def clear(self) -> None:
        for var in self.vars:
            var.set(False)


def export_sections_dialog(parent, sections: dict[str, tk.BooleanVar], title: str = "Параметры экспорта") -> bool:
    """Модальный диалог с чекбоксами секций. True = продолжить сохранение."""
    result = {"ok": False}
    dialog = tk.Toplevel(parent)
    dialog.title(title)
    dialog.transient(parent.winfo_toplevel())
    dialog.grab_set()
    dialog.resizable(False, False)

    ttkb.Label(dialog, text="Включить в отчёт:", font=("Calibri", 12)).pack(
        padx=20, pady=(16, 8), anchor=tk.W
    )
    body = ttkb.Frame(dialog, padding=(20, 0))
    body.pack(fill=tk.X)
    for section, var in sections.items():
        ttkb.Checkbutton(
            body,
            text=section,
            variable=var,
            bootstyle="round-toggle",
        ).pack(anchor=tk.W, pady=2)

    btn_row = ttkb.Frame(dialog)
    btn_row.pack(padx=20, pady=16)

    def ok():
        result["ok"] = True
        dialog.destroy()

    ttkb.Button(btn_row, text="Далее", command=ok, bootstyle="success", padding=SECONDARY_PAD).pack(
        side=tk.LEFT, padx=4
    )
    ttkb.Button(
        btn_row, text="Отмена", command=dialog.destroy, bootstyle="secondary", padding=SECONDARY_PAD
    ).pack(side=tk.LEFT, padx=4)

    dialog.update_idletasks()
    try:
        root = parent.winfo_toplevel()
        x = root.winfo_rootx() + (root.winfo_width() - dialog.winfo_width()) // 2
        y = root.winfo_rooty() + (root.winfo_height() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
    except tk.TclError:
        pass
    dialog.wait_window()
    return result["ok"]
