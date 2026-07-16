"""Главное окно приложения."""
from __future__ import annotations

import logging
import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

import ttkbootstrap as ttkb

from config_store import load_config, save_config
from gui.ksg_frame import KsgReportFrame
from gui.lor_frame import LorReportFrame
from gui.settings_dialog import SettingsDialog
from gui.ui_theme import LIGHT_THEME, is_dark_theme, toggle_theme_name
from gui.widgets import ScrollableFrame, wheel_steps
from paths import get_base_dir
from updater import check_for_updates, read_current_version

LOG_FILE = "errors.log"


class App(ttkb.Window):
    def __init__(self):
        self.app_settings = load_config()
        self.current_version = read_current_version()
        theme = self.app_settings.get("theme") or LIGHT_THEME
        super().__init__(
            themename=theme,
            title=f"Анализ работы отделения — v{self.current_version}",
        )
        self.geometry(self.app_settings.get("window_geometry", "1400x850+100+100"))
        self.minsize(960, 640)
        self.resizable(True, True)

        style = ttkb.Style()
        style.configure("Treeview", rowheight=26)

        header = ttkb.Frame(self)
        header.pack(fill=tk.X, padx=12, pady=(10, 6))

        lbl_title = ttkb.Label(
            header,
            text="Анализ работы отделения",
            font=("Calibri", 18, "bold"),
            bootstyle="primary",
        )
        lbl_title.pack(side=tk.LEFT)

        right = ttkb.Frame(header)
        right.pack(side=tk.RIGHT)

        self.version_var = tk.StringVar(value=f"Версия {self.current_version}")
        ttkb.Label(
            right,
            textvariable=self.version_var,
            font=("Calibri", 11),
            bootstyle="secondary",
        ).pack(side=tk.LEFT, padx=(0, 8))

        self.theme_btn = ttkb.Button(
            right,
            text=self._theme_button_label(),
            command=self.toggle_theme,
            bootstyle="secondary-outline",
            padding=(10, 4),
        )
        self.theme_btn.pack(side=tk.LEFT, padx=(0, 8))

        ttkb.Button(
            right,
            text="Обновления",
            command=self.check_updates,
            bootstyle="info-outline",
            padding=(10, 4),
        ).pack(side=tk.LEFT)

        self.notebook = ttkb.Notebook(self, bootstyle="primary")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 0))

        self.lor_frame = LorReportFrame(self.notebook, self)
        self.ksg_frame = KsgReportFrame(self.notebook, self)

        self.notebook.add(self.lor_frame, text="Анализ ЭМК")
        self.notebook.add(self.ksg_frame, text="Анализ КСГ")

        last_tab = int(self.app_settings.get("last_main_tab", 0) or 0)
        try:
            tabs = self.notebook.tabs()
            if 0 <= last_tab < len(tabs):
                self.notebook.select(last_tab)
        except Exception:
            pass
        self.notebook.bind("<<NotebookTabChanged>>", self._on_main_tab_changed)

        self.status_var = tk.StringVar(
            value=f"v{self.current_version}  |  {self.ksg_frame.reference_status}"
        )
        status_bar = ttkb.Label(
            self, textvariable=self.status_var, bootstyle="secondary", anchor=tk.W
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)

        self._create_menu()
        self._bind_hotkeys()
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.bind_all("<MouseWheel>", self._global_mousewheel, add="+")
        self.bind_all("<Shift-MouseWheel>", self._global_shift_mousewheel, add="+")
        self.bind_all("<Button-4>", self._global_mousewheel, add="+")
        self.bind_all("<Button-5>", self._global_mousewheel, add="+")

        if self.app_settings.get("check_updates_on_start", True):
            repo = self.app_settings.get("github_repo", "")
            if repo:
                threading.Thread(
                    target=self._silent_update_check,
                    args=(repo,),
                    daemon=True,
                ).start()

    def _theme_button_label(self) -> str:
        return "Светлая тема" if is_dark_theme(self.app_settings.get("theme", "")) else "Тёмная тема"

    def toggle_theme(self) -> None:
        new_theme = toggle_theme_name(self.app_settings.get("theme", LIGHT_THEME))
        self.app_settings["theme"] = new_theme
        save_config(self.app_settings)
        try:
            self.style.theme_use(new_theme)
        except Exception:
            messagebox.showinfo(
                "Тема",
                f"Тема «{new_theme}» сохранена. Перезапустите приложение для полного применения.",
            )
            return
        self.theme_btn.configure(text=self._theme_button_label())

    def _active_work_frame(self):
        try:
            current = self.notebook.select()
            return self.nametowidget(current)
        except Exception:
            return self.lor_frame

    def _bind_hotkeys(self) -> None:
        for seq, handler in (
            ("<Command-o>", self._hotkey_open),
            ("<Control-o>", self._hotkey_open),
            ("<Command-s>", self._hotkey_save),
            ("<Control-s>", self._hotkey_save),
            ("<Command-Shift-c>", self._hotkey_copy),
            ("<Control-Shift-c>", self._hotkey_copy),
        ):
            self.bind_all(seq, handler)

    def _hotkey_open(self, _event=None):
        frame = self._active_work_frame()
        if hasattr(frame, "hotkey_open"):
            frame.hotkey_open()
        return "break"

    def _hotkey_save(self, _event=None):
        frame = self._active_work_frame()
        if hasattr(frame, "hotkey_save"):
            frame.hotkey_save()
        return "break"

    def _hotkey_copy(self, _event=None):
        frame = self._active_work_frame()
        if hasattr(frame, "hotkey_copy"):
            frame.hotkey_copy()
        return "break"

    def _silent_update_check(self, repo: str) -> None:
        from updater import fetch_latest_release, parse_version, perform_update

        version = read_current_version()
        try:
            release = fetch_latest_release(repo)
            if not release:
                return
            latest_tag = release.get("tag_name")
            if parse_version(latest_tag) <= parse_version(version):
                return

            def ask():
                answer = messagebox.askyesno(
                    "Доступно обновление",
                    f"Вышла новая версия {latest_tag}!\n"
                    f"Текущая версия: v{version}\n\n"
                    "Скачать и установить сейчас?\n(проверка SHA-256)",
                )
                if answer:
                    perform_update(repo, release=release)

            self.after(0, ask)
        except Exception as e:
            logging.error("Фоновая проверка обновлений: %s", e)

    def _create_menu(self) -> None:
        menubar = tk.Menu(self)
        self.configure(menu=menubar)
        self._menubar = menubar

        self.file_menu = tk.Menu(menubar, tearoff=0)
        self.file_menu.add_command(
            label="Открыть…",
            command=self._hotkey_open,
            accelerator="⌘O" if sys.platform == "darwin" else "Ctrl+O",
        )
        self.file_menu.add_command(
            label="Сохранить отчёт…",
            command=self._hotkey_save,
            accelerator="⌘S" if sys.platform == "darwin" else "Ctrl+S",
        )
        self.file_menu.add_separator()
        self.recent_emk_menu = tk.Menu(self.file_menu, tearoff=0)
        self.recent_ksg_menu = tk.Menu(self.file_menu, tearoff=0)
        self.file_menu.add_cascade(label="Недавние ЭМК", menu=self.recent_emk_menu)
        self.file_menu.add_cascade(label="Недавние КСГ", menu=self.recent_ksg_menu)
        self._rebuild_recent_menus()
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Открыть лог ошибок", command=self.open_log)
        self.file_menu.add_command(label="Проверить обновления", command=self.check_updates)
        self.file_menu.add_separator()
        self.file_menu.add_command(label="Выход", command=self.on_close)
        menubar.add_cascade(label="Файл", menu=self.file_menu)

        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Все настройки…", command=self.open_settings)
        settings_menu.add_command(label="Переключить тему", command=self.toggle_theme)
        settings_menu.add_separator()
        self.date_format_var = tk.StringVar(
            value=self.app_settings.get("date_format", "dayfirst")
        )
        settings_menu.add_radiobutton(
            label="Дата: ДД.ММ.ГГГГ",
            variable=self.date_format_var,
            value="dayfirst",
            command=self.on_date_format_change,
        )
        settings_menu.add_radiobutton(
            label="Дата: ММ.ДД.ГГГГ",
            variable=self.date_format_var,
            value="monthfirst",
            command=self.on_date_format_change,
        )
        menubar.add_cascade(label="Настройки", menu=settings_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="О программе", command=self.show_about)
        menubar.add_cascade(label="Справка", menu=help_menu)

    def _rebuild_recent_menus(self) -> None:
        self.recent_emk_menu.delete(0, tk.END)
        self.recent_ksg_menu.delete(0, tk.END)

        emk = [p for p in self.app_settings.get("recent_emk") or [] if Path(p).exists()]
        ksg = [p for p in self.app_settings.get("recent_ksg") or [] if Path(p).exists()]

        if not emk:
            self.recent_emk_menu.add_command(label="(пусто)", state=tk.DISABLED)
        else:
            for path in emk:
                self.recent_emk_menu.add_command(
                    label=Path(path).name,
                    command=lambda p=path: self.lor_frame.open_path(p),
                )

        if not ksg:
            self.recent_ksg_menu.add_command(label="(пусто)", state=tk.DISABLED)
        else:
            for path in ksg:
                self.recent_ksg_menu.add_command(
                    label=Path(path).name,
                    command=lambda p=path: self._open_recent_ksg(p),
                )

    def refresh_recent_menus(self) -> None:
        """Вызывается фреймами после успешной загрузки файла."""
        self._rebuild_recent_menus()

    def _open_recent_ksg(self, path: str) -> None:
        self.notebook.select(self.ksg_frame)
        self.ksg_frame.open_path(path)

    def open_settings(self) -> None:
        SettingsDialog(self, self)

    def open_log(self) -> None:
        log_path = get_base_dir() / LOG_FILE
        if log_path.exists():
            if sys.platform == "darwin":
                os.system(f'open "{log_path}"')
            elif sys.platform == "win32":
                os.startfile(str(log_path))  # type: ignore[attr-defined]
            else:
                os.system(f'xdg-open "{log_path}"')
        else:
            messagebox.showinfo("Лог", "Файл лога ещё не создан.")

    def check_updates(self) -> None:
        repo = self.app_settings.get("github_repo", "")
        if not repo:
            messagebox.showwarning(
                "Обновления",
                "Укажите репозиторий GitHub в настройках (owner/repo).",
            )
            return
        version = read_current_version()
        check_for_updates(repo, version, silent_if_updated=False)

    def on_date_format_change(self) -> None:
        self.app_settings["date_format"] = self.date_format_var.get()
        save_config(self.app_settings)
        messagebox.showinfo(
            "Настройки",
            "Формат даты изменён. Перезагрузите данные для применения.",
        )

    def show_about(self) -> None:
        version = read_current_version()
        messagebox.showinfo(
            "О программе",
            "Анализ работы отделения\n\n"
            "ЭМК и КСГ: отчёты, нарушения, сравнение месяцев\n"
            f"Версия {version}\n"
            "Горячие клавиши: ⌘/Ctrl+O открыть, ⌘/Ctrl+S сохранить,\n"
            "⌘/Ctrl+Shift+C копировать сводку\n"
            "© 2026",
        )

    def _on_main_tab_changed(self, _event=None) -> None:
        try:
            idx = self.notebook.index(self.notebook.select())
            self.app_settings["last_main_tab"] = int(idx)
        except Exception:
            pass

    def on_close(self) -> None:
        self.app_settings["window_geometry"] = self.geometry()
        try:
            self.app_settings["last_main_tab"] = int(self.notebook.index(self.notebook.select()))
        except Exception:
            pass
        save_config(self.app_settings)
        self.destroy()

    def _widget_under_pointer(self, event):
        try:
            return self.winfo_containing(event.x_root, event.y_root)
        except tk.TclError:
            return None

    def _find_ancestor(self, widget, pred):
        parent = widget
        while parent is not None:
            if pred(parent):
                return parent
            p = parent.winfo_parent()
            if not p:
                break
            try:
                parent = parent.nametowidget(p)
            except KeyError:
                break
        return None

    def _scroll_target_y(self, widget, steps: int) -> bool:
        if widget is None or not steps:
            return False
        cls = widget.winfo_class()
        if cls in ("Treeview", "Text", "Listbox", "Canvas"):
            try:
                widget.yview_scroll(steps, "units")
                return True
            except tk.TclError:
                pass
        sf = self._find_ancestor(widget, lambda w: isinstance(w, ScrollableFrame))
        if sf is not None:
            sf.scroll_y(steps)
            return True
        return False

    def _scroll_target_x(self, widget, steps: int) -> bool:
        if widget is None or not steps:
            return False
        cls = widget.winfo_class()
        if cls in ("Treeview", "Text", "Listbox", "Canvas"):
            try:
                widget.xview_scroll(steps, "units")
                return True
            except tk.TclError:
                pass
        sf = self._find_ancestor(widget, lambda w: isinstance(w, ScrollableFrame))
        if sf is not None:
            sf.scroll_x(steps)
            return True
        return False

    def _global_mousewheel(self, event) -> None:
        steps = wheel_steps(event)
        if not steps:
            return
        widget = self._widget_under_pointer(event)
        self._scroll_target_y(widget, steps)

    def _global_shift_mousewheel(self, event) -> None:
        steps = wheel_steps(event)
        if not steps:
            return
        widget = self._widget_under_pointer(event)
        self._scroll_target_x(widget, steps)
