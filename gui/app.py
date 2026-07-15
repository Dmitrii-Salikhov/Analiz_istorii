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
from gui.widgets import ScrollableFrame
from paths import get_base_dir
from updater import check_for_updates, read_current_version

LOG_FILE = "errors.log"


class App(ttkb.Window):
    def __init__(self):
        self.app_settings = load_config()
        super().__init__(
            themename=self.app_settings.get("theme", "cosmo"),
            title="Анализ работы отделения",
        )
        self.geometry(self.app_settings.get("window_geometry", "1400x850+100+100"))

        style = ttkb.Style()
        style.configure("Treeview", rowheight=25)

        lbl_title = ttkb.Label(
            self,
            text="Анализ работы отделения",
            font=("Calibri", 20, "bold"),
            bootstyle="warning",
        )
        lbl_title.pack(pady=10)

        self.notebook = ttkb.Notebook(self, bootstyle="primary")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=(10, 0))

        self.lor_frame = LorReportFrame(self.notebook, self)
        self.ksg_frame = KsgReportFrame(self.notebook, self)

        self.notebook.add(self.lor_frame, text="📊 Анализ работы отделения")
        self.notebook.add(self.ksg_frame, text="💰 Анализ КСГ")

        self.status_var = tk.StringVar(value=self.ksg_frame.reference_status)
        status_bar = ttkb.Label(
            self, textvariable=self.status_var, bootstyle="secondary", anchor=tk.W
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X, padx=10, pady=5)

        self._create_menu()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.bind_all("<MouseWheel>", self._global_mousewheel)

        if self.app_settings.get("check_updates_on_start", True):
            repo = self.app_settings.get("github_repo", "")
            if repo:
                threading.Thread(
                    target=self._silent_update_check,
                    args=(repo,),
                    daemon=True,
                ).start()

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

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Открыть лог ошибок", command=self.open_log)
        file_menu.add_command(label="Проверить обновления", command=self.check_updates)
        file_menu.add_separator()
        file_menu.add_command(label="Выход", command=self.on_close)
        menubar.add_cascade(label="Файл", menu=file_menu)

        settings_menu = tk.Menu(menubar, tearoff=0)
        settings_menu.add_command(label="Все настройки…", command=self.open_settings)
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
            "Анализ работы ЛОР-отделения\n\n"
            "Инструмент для анализа медицинских данных\n"
            f"Версия {version}\n"
            "© 2026",
        )

    def on_close(self) -> None:
        self.app_settings["window_geometry"] = self.geometry()
        save_config(self.app_settings)
        self.destroy()

    def _find_scrollable_frame(self, widget):
        parent = widget
        while parent is not None:
            if isinstance(parent, ScrollableFrame):
                return parent
            p = parent.winfo_parent()
            if not p:
                break
            try:
                parent = parent.nametowidget(p)
            except KeyError:
                break
        return None

    def _global_mousewheel(self, event) -> None:
        widget = event.widget.winfo_containing(event.x_root, event.y_root)
        if widget is None:
            return
        sf = self._find_scrollable_frame(widget)
        if sf is not None:
            sf.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
