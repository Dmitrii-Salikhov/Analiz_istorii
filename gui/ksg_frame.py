"""Вкладка анализа КСГ."""
from __future__ import annotations

import logging
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import numpy as np
import pandas as pd
import ttkbootstrap as ttkb
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from config_store import push_recent_file, save_config
from excel_io import ExcelParseError, MissingColumnsError, load_ksg_excel
from gui.helpers import build_empty_state
from gui.ui_theme import short_month_label
from gui.widgets import ScrollableFrame, enable_file_drop, make_filtered_tree, run_with_progress
from ksg_analysis import (
    analyze_ksg,
    build_month_comparison,
    load_reference,
    sort_ksg_files_chronologically,
)


class KsgReportFrame(ttkb.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.app_settings = app.app_settings
        self.reference, self._reference_status = load_reference()
        self.loaded_files: list[dict] = []
        self.active_file_index = -1
        self.df = None
        self.results: dict = {}
        self.file_name = ""
        self._build_ui()
        enable_file_drop(self, self._on_dropped_files, extensions=(".xlsx",))

    @property
    def reference_status(self) -> str:
        return self._reference_status

    def _build_ui(self) -> None:
        ctrl_frame = ttkb.Frame(self)
        ctrl_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        self.btn_load = ttkb.Button(
            ctrl_frame,
            text="Загрузить файлы КСГ",
            command=self.load_files,
            bootstyle="info",
            padding=(20, 5),
        )
        self.btn_load.pack(side=tk.LEFT, padx=5)

        self.btn_remove = ttkb.Button(
            ctrl_frame,
            text="Удалить выбранный",
            command=self.remove_file,
            bootstyle="danger",
            state=tk.DISABLED,
            padding=(20, 5),
        )
        self.btn_remove.pack(side=tk.LEFT, padx=5)

        ttkb.Label(ctrl_frame, text="Активный файл:", font=("Calibri", 11)).pack(
            side=tk.LEFT, padx=(20, 5)
        )
        self.file_combobox = ttkb.Combobox(ctrl_frame, state="readonly", width=50)
        self.file_combobox.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.file_combobox.bind("<<ComboboxSelected>>", self.on_file_selected)

        self.btn_copy_all = ttkb.Button(
            ctrl_frame,
            text="Копировать всё",
            command=self.copy_all_tabs,
            bootstyle="info",
            state=tk.DISABLED,
        )
        self.btn_copy_all.pack(side=tk.RIGHT, padx=5)

        self.context_frame = ttkb.Frame(self, bootstyle="secondary", padding=(8, 4))
        self.context_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 4))

        self.lbl_context_file = ttkb.Label(self.context_frame, text="Файл: —", font=("Calibri", 10))
        self.lbl_context_file.pack(side=tk.LEFT, padx=(0, 16))
        self.lbl_context_month = ttkb.Label(self.context_frame, text="Период: —", font=("Calibri", 10))
        self.lbl_context_month.pack(side=tk.LEFT, padx=(0, 16))
        self.lbl_context_patients = ttkb.Label(self.context_frame, text="Пациентов: —", font=("Calibri", 10))
        self.lbl_context_patients.pack(side=tk.LEFT, padx=(0, 16))
        self.lbl_context_sum = ttkb.Label(self.context_frame, text="Сумма: —", font=("Calibri", 10))
        self.lbl_context_sum.pack(side=tk.LEFT)

        self.work_area = ttkb.Frame(self)
        self.work_area.pack(fill=tk.BOTH, expand=True)

        self.empty_wrap = build_empty_state(
            self.work_area,
            title="Анализ КСГ",
            steps=[
                "Загрузите один или несколько файлов КСГ",
                "Просмотрите сводку по пациентам и суммам",
                "Сравните месяцы и сохраните отчёт",
            ],
            load_text="Загрузить файлы КСГ",
            on_load=self.load_files,
        )
        self.empty_wrap.pack(fill=tk.BOTH, expand=True)

        self.outer_notebook = ttkb.Notebook(self.work_area, bootstyle="primary")

        summary_outer = ttkb.Frame(self.outer_notebook)
        cases_outer = ttkb.Frame(self.outer_notebook)
        compare_outer = ttkb.Frame(self.outer_notebook)
        export_outer = ttkb.Frame(self.outer_notebook)

        self.outer_notebook.add(summary_outer, text="Сводка")
        self.outer_notebook.add(cases_outer, text="Случаи и КСЛП")
        self.outer_notebook.add(compare_outer, text="Сравнение")
        self.outer_notebook.add(export_outer, text="Экспорт")

        self.summary_notebook = ttkb.Notebook(summary_outer, bootstyle="info")
        self.summary_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.cases_notebook = ttkb.Notebook(cases_outer, bootstyle="warning")
        self.cases_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.tab_frames: dict[str, ttkb.Frame] = {}

        summary_tabs = [
            ("patients", "Пациенты"),
            ("operations", "Операции"),
            ("money", "Сумма"),
            ("age_groups", "Возраст"),
            ("kz", "КЗ"),
        ]
        for key, title in summary_tabs:
            frame = ttkb.Frame(self.summary_notebook)
            self.summary_notebook.add(frame, text=title)
            self.tab_frames[key] = frame

        cases_tabs = [
            ("analysis", "Анализ случаев"),
            ("kslp", "КСЛП"),
        ]
        for key, title in cases_tabs:
            frame = ttkb.Frame(self.cases_notebook)
            self.cases_notebook.add(frame, text=title)
            self.tab_frames[key] = frame

        self.tab_frames["compare"] = compare_outer
        self.tab_frames["export"] = export_outer

        self._update_context_bar()

    def _show_work_content(self, has_files: bool) -> None:
        if has_files:
            self.empty_wrap.pack_forget()
            self.outer_notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        else:
            self.outer_notebook.pack_forget()
            self.empty_wrap.pack(fill=tk.BOTH, expand=True)

    def _file_label(self, f: dict) -> str:
        return short_month_label(f["name"], f.get("df"))

    def _on_dropped_files(self, paths: list[str]) -> None:
        pending = [fp for fp in paths if fp not in {f["path"] for f in self.loaded_files}]
        if pending:
            self._load_paths_batch(pending)

    def load_files(self) -> None:
        file_paths = filedialog.askopenfilenames(filetypes=[("Excel files", "*.xlsx")])
        if not file_paths:
            return
        pending = [fp for fp in file_paths if fp not in {f["path"] for f in self.loaded_files}]
        if not pending:
            return
        self._load_paths_batch(pending)

    def open_path(self, path: str) -> None:
        self.open_paths([path])

    def open_paths(self, paths: list[str]) -> None:
        pending = [fp for fp in paths if fp not in {f["path"] for f in self.loaded_files}]
        if pending:
            self._load_paths_batch(pending)

    def hotkey_open(self) -> None:
        self.load_files()

    def hotkey_save(self) -> None:
        if self.results:
            self.save_report_excel()

    def hotkey_copy(self) -> None:
        self.copy_all_tabs()

    def _load_paths_batch(self, paths: list[str]) -> None:
        queue = list(paths)

        def load_next():
            if not queue:
                if self.loaded_files:
                    if not (0 <= self.active_file_index < len(self.loaded_files)):
                        self.active_file_index = len(self.loaded_files) - 1
                    self._activate_file(self.active_file_index)
                return
            fp = queue.pop(0)

            def work(progress):
                return load_ksg_excel(fp, progress=progress)

            def on_success(df):
                name = Path(fp).name
                results = analyze_ksg(df, self.reference, self.app.app_settings)
                self.loaded_files.append(
                    {"name": name, "path": fp, "df": df, "results": results}
                )
                push_recent_file(self.app.app_settings, "recent_ksg", fp)
                if hasattr(self.app, "refresh_recent_menus"):
                    self.app.refresh_recent_menus()
                self._sort_loaded_files(active_path=fp)
                load_next()

            def on_error(exc: BaseException):
                logging.error("Ошибка загрузки %s: %s", fp, exc)
                if isinstance(exc, (MissingColumnsError, ExcelParseError)):
                    messagebox.showerror("Ошибка", str(exc))
                else:
                    messagebox.showerror("Ошибка", f"Не удалось загрузить файл:\n{fp}\n{exc}")
                load_next()

            run_with_progress(self, f"Загрузка КСГ: {Path(fp).name}", work, on_success, on_error)

        load_next()

    def _add_file(self, file_path: str) -> None:
        if file_path in {f["path"] for f in self.loaded_files}:
            return

        def work(progress):
            return load_ksg_excel(file_path, progress=progress)

        def on_success(df):
            name = Path(file_path).name
            results = analyze_ksg(df, self.reference, self.app.app_settings)
            self.loaded_files.append(
                {"name": name, "path": file_path, "df": df, "results": results}
            )
            push_recent_file(self.app.app_settings, "recent_ksg", file_path)
            if hasattr(self.app, "refresh_recent_menus"):
                self.app.refresh_recent_menus()
            self._sort_loaded_files(active_path=file_path)
            if self.loaded_files:
                self._activate_file(self.active_file_index)

        def on_error(exc: BaseException):
            logging.error("Ошибка загрузки %s: %s", file_path, exc)
            if isinstance(exc, (MissingColumnsError, ExcelParseError)):
                messagebox.showerror("Ошибка", str(exc))
            else:
                messagebox.showerror("Ошибка", f"Не удалось загрузить файл:\n{file_path}\n{exc}")

        run_with_progress(self, "Загрузка КСГ", work, on_success, on_error)

    def _sort_loaded_files(self, active_path: str | None = None) -> None:
        """Держит загруженные месяцы в хронологическом порядке."""
        if active_path is None and 0 <= self.active_file_index < len(self.loaded_files):
            active_path = self.loaded_files[self.active_file_index]["path"]
        self.loaded_files = sort_ksg_files_chronologically(self.loaded_files)
        if active_path:
            for i, f in enumerate(self.loaded_files):
                if f["path"] == active_path:
                    self.active_file_index = i
                    break
        elif self.loaded_files:
            self.active_file_index = len(self.loaded_files) - 1

    def remove_file(self) -> None:
        idx = self.file_combobox.current()
        if idx < 0 or idx >= len(self.loaded_files):
            return
        del self.loaded_files[idx]
        if not self.loaded_files:
            self.active_file_index = -1
            self.df = None
            self.results = {}
            self.file_name = ""
            self._update_file_list()
            self._clear_all_tabs()
            self.btn_remove.configure(state=tk.DISABLED)
            self.btn_copy_all.configure(state=tk.DISABLED)
            self._show_work_content(False)
            self._update_context_bar()
        else:
            new_idx = min(idx, len(self.loaded_files) - 1)
            self.active_file_index = new_idx
            self._activate_file(new_idx)

    def on_file_selected(self, _event=None) -> None:
        idx = self.file_combobox.current()
        if 0 <= idx < len(self.loaded_files):
            self.active_file_index = idx
            self._activate_file(idx)

    def _activate_file(self, idx: int) -> None:
        f = self.loaded_files[idx]
        self.df = f["df"]
        self.results = f["results"]
        self.file_name = f["name"]
        self._update_file_list()
        self.display_all()
        self.btn_remove.configure(state=tk.NORMAL)
        self.btn_copy_all.configure(state=tk.NORMAL)
        self._show_work_content(True)
        self._update_context_bar()

    def _update_file_list(self) -> None:
        labels = [self._file_label(f) for f in self.loaded_files]
        self.file_combobox["values"] = labels
        if self.active_file_index >= 0:
            self.file_combobox.current(self.active_file_index)

    def _update_context_bar(self) -> None:
        if self.results and self.active_file_index >= 0:
            f = self.loaded_files[self.active_file_index]
            month = self._file_label(f)
            self.lbl_context_file.configure(text=f"Файл: {self.file_name}")
            self.lbl_context_month.configure(text=f"Период: {month}")
            self.lbl_context_patients.configure(text=f"Пациентов: {self.results['total_patients']}")
            self.lbl_context_sum.configure(
                text=f"Сумма: {self.results['total_sum']:,.2f} руб."
            )
        else:
            self.lbl_context_file.configure(text="Файл: —")
            self.lbl_context_month.configure(text="Период: —")
            self.lbl_context_patients.configure(text="Пациентов: —")
            self.lbl_context_sum.configure(text="Сумма: —")

    def _clear_all_tabs(self) -> None:
        for key in self.tab_frames:
            for w in self.tab_frames[key].winfo_children():
                w.destroy()

    def _reanalyze_current(self) -> None:
        if self.df is None or self.active_file_index < 0:
            return
        self.results = analyze_ksg(self.df, self.reference, self.app.app_settings)
        self.loaded_files[self.active_file_index]["results"] = self.results
        self._update_context_bar()

    def display_all(self) -> None:
        self._clear_all_tabs()
        if self.df is None:
            return
        self._tab_patients()
        self._tab_operations()
        self._tab_money()
        self._tab_analysis()
        self._tab_kslp()
        self._tab_age_groups()
        self._tab_kz()
        self._tab_compare()
        self._tab_export()

    def _tab_patients(self) -> None:
        frame = self.tab_frames["patients"]
        r = self.results
        ttkb.Label(
            frame,
            text=f"Общее количество пациентов: {r['total_patients']}",
            font=("Calibri", 14, "bold"),
        ).pack(anchor="w")
        columns = ("Врач", "Количество пациентов")
        data = [tuple(x) for x in r["patient_counts"].to_numpy()]
        make_filtered_tree(
            frame,
            columns,
            data,
            {"Врач": "Врач", "Количество пациентов": "Количество пациентов"},
            clipboard_host=self,
            copy_df=r["patient_counts"],
            on_copy_df=self._copy_df_as_text,
        )

    def _tab_operations(self) -> None:
        frame = self.tab_frames["operations"]
        r = self.results
        if not r["ops_pivot"].empty:
            ops_flat = r["ops_pivot"].reset_index()
            cols = list(ops_flat.columns)
            data = [tuple(x) for x in ops_flat.to_numpy()]
            make_filtered_tree(
                frame,
                cols,
                data,
                {c: c for c in cols},
                clipboard_host=self,
                copy_df=ops_flat,
                on_copy_df=self._copy_df_as_text,
            )
        else:
            ttkb.Label(frame, text="Нет данных об операциях").pack()
        if r["unknown_codes"]:
            txt = tk.Text(frame, height=5, font=("Calibri", 11))
            txt.insert(tk.END, "Нераспознанные коды услуг:\n" + "\n".join(r["unknown_codes"]))
            txt.configure(state=tk.DISABLED)
            txt.pack(fill=tk.X, pady=10)

    def _tab_money(self) -> None:
        frame = self.tab_frames["money"]
        r = self.results
        ttkb.Label(
            frame,
            text=f"Общая сумма по отделению: {r['total_sum']:,.2f} руб.",
            font=("Calibri", 14, "bold"),
        ).pack(anchor="w")
        columns = ("Врач", "Сумма")
        data = [
            (row["Врач"], f"{row['Сумма к оплате']:,.2f}")
            for _, row in r["sum_by_doctor"].iterrows()
        ]
        make_filtered_tree(
            frame,
            columns,
            data,
            {"Врач": "Врач", "Сумма": "Сумма к оплате, руб."},
            clipboard_host=self,
            copy_df=r["sum_by_doctor"],
            on_copy_df=self._copy_df_as_text,
        )

        fig = Figure(figsize=(5, 4), dpi=100)
        ax = fig.add_subplot(111)
        ax.pie(
            r["sum_by_doctor"]["Сумма к оплате"],
            labels=r["sum_by_doctor"]["Врач"],
            autopct="%1.1f%%",
        )
        ax.set_title("Распределение сумм по врачам")
        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(pady=10)
        ttkb.Button(
            frame,
            text="Сохранить график",
            command=lambda: self._save_graph(fig),
            bootstyle="secondary",
        ).pack()

    def _tab_analysis(self) -> None:
        outer = self.tab_frames["analysis"]
        scroll = ScrollableFrame(outer)
        scroll.pack(fill=tk.BOTH, expand=True)
        frame = scroll.scrollable_frame
        r = self.results
        settings = self.app.app_settings
        thresholds = r.get("thresholds", {})

        ttkb.Label(frame, text="Порог для «дешёвых» случаев (<):", font=("Calibri", 11)).pack(
            anchor="w", padx=10
        )
        low_entry = ttkb.Entry(frame, bootstyle="info")
        low_entry.insert(0, str(thresholds.get("low", settings.get("ksg_threshold_low", 20000))))
        low_entry.pack(padx=10, pady=2)

        ttkb.Label(frame, text="Порог для «дорогих» случаев (>):", font=("Calibri", 11)).pack(
            anchor="w", padx=10
        )
        high_entry = ttkb.Entry(frame, bootstyle="info")
        high_entry.insert(0, str(thresholds.get("high", settings.get("ksg_threshold_high", 100000))))
        high_entry.pack(padx=10, pady=2)

        kslp = r.get("kslp_settings", {})
        info = (
            f"КСЛП: возраст {kslp.get('age_min', 0)}–{kslp.get('age_max', 4)} лет, "
            f"старший ≥{kslp.get('senior_age', 75)}, коды: {', '.join(kslp.get('codes', []))}"
        )
        ttkb.Label(frame, text=info, font=("Calibri", 10), bootstyle="secondary").pack(
            anchor="w", padx=10, pady=4
        )

        def apply_thresholds():
            try:
                self.app.app_settings["ksg_threshold_low"] = float(
                    low_entry.get().replace(",", ".").strip()
                )
                self.app.app_settings["ksg_threshold_high"] = float(
                    high_entry.get().replace(",", ".").strip()
                )
                save_config(self.app.app_settings)
                self.app_settings = self.app.app_settings
                self._reanalyze_current()
                self.display_all()
            except ValueError:
                messagebox.showerror("Ошибка", "Введите числовые значения порогов.")

        ttkb.Button(frame, text="Применить пороги", command=apply_thresholds, bootstyle="warning").pack(
            pady=5
        )

        note = ttkb.Notebook(frame, bootstyle="warning")
        note.pack(fill=tk.BOTH, expand=True, pady=10)

        for name, df_data in [
            ("Дешёвые", r["low_money"]),
            ("Дорогие", r["high_money"]),
            ("Без кода услуги", r["no_service"]),
        ]:
            tab = ttkb.Frame(note)
            note.add(tab, text=name)
            if not df_data.empty:
                cols = list(df_data.columns)
                data = [tuple(x) for x in df_data.to_numpy()]
                make_filtered_tree(
                    tab,
                    cols,
                    data,
                    {c: c for c in cols},
                    clipboard_host=self,
                    copy_df=df_data,
                    on_copy_df=self._copy_df_as_text,
                )
            else:
                ttkb.Label(tab, text="Случаев не найдено").pack()

        def copy_cases():
            text = ""
            for name, df_data in [
                ("Дешёвые (<)", r["low_money"]),
                ("Дорогие (>)", r["high_money"]),
                ("Без кода услуги", r["no_service"]),
            ]:
                text += f"\n{name}:\n"
                text += df_data.to_string(index=False) + "\n"
            self.clipboard_clear()
            self.clipboard_append(text)
            messagebox.showinfo("Скопировано", "Сводка скопирована в буфер обмена")

        ttkb.Button(
            frame,
            text="Скопировать сводку всех случаев",
            command=copy_cases,
            bootstyle="info",
        ).pack(pady=5)

    def _tab_kslp(self) -> None:
        frame = self.tab_frames["kslp"]
        r = self.results
        scroll = ScrollableFrame(frame)
        scroll.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        if not r["kslp_issues"].empty:
            cols = list(r["kslp_issues"].columns)
            data = [tuple(x) for x in r["kslp_issues"].to_numpy()]
            make_filtered_tree(
                scroll.scrollable_frame,
                cols,
                data,
                {c: c for c in cols},
                clipboard_host=self,
                copy_df=r["kslp_issues"],
                on_copy_df=self._copy_df_as_text,
            )
            ttkb.Button(
                scroll.scrollable_frame,
                text="Копировать список нарушений КСЛП",
                command=lambda: self._copy_df_as_text(r["kslp_issues"]),
                bootstyle="info",
            ).pack(pady=5)
        else:
            ttkb.Label(
                scroll.scrollable_frame,
                text="Нарушений КСЛП не обнаружено",
                bootstyle="success",
                font=("Calibri", 14),
            ).pack(pady=50)

        other = r.get("other_violations", {})
        if other:
            ttkb.Label(
                scroll.scrollable_frame,
                text="Другие нарушения:",
                font=("Calibri", 13, "bold"),
            ).pack(anchor=tk.W, pady=(15, 5))
            for cat, cnt in other.items():
                ttkb.Label(scroll.scrollable_frame, text=f"• {cat}: {cnt}").pack(anchor=tk.W)
        else:
            ttkb.Label(
                scroll.scrollable_frame,
                text="Нарушений в других категориях не найдено",
                font=("Calibri", 12),
                bootstyle="secondary",
            ).pack(pady=(15, 5))

    def _tab_age_groups(self) -> None:
        frame = self.tab_frames["age_groups"]
        r = self.results
        age_df = pd.DataFrame(
            {
                "Группа": r["age_dist"].index,
                "Пациенты": r["age_dist"].values,
                "Сумма": r["age_sum"].reindex(r["age_dist"].index, fill_value=0).values,
                "Средний КЗ": r["age_kz"].reindex(r["age_dist"].index, fill_value=0).values,
            }
        )
        cols = list(age_df.columns)
        data = [tuple(x) for x in age_df.to_numpy()]
        make_filtered_tree(
            frame,
            cols,
            data,
            {c: c for c in cols},
            clipboard_host=self,
            copy_df=age_df,
            on_copy_df=self._copy_df_as_text,
        )

    def _tab_kz(self) -> None:
        frame = self.tab_frames["kz"]
        r = self.results
        ttkb.Label(
            frame,
            text=f"Средний КЗ по отделению: {r['avg_kz_total']}",
            font=("Calibri", 14, "bold"),
        ).pack(anchor="w")
        cols = ("Врач", "Средний КЗ")
        data = [(row["Врач"], row["Средний КЗ"]) for _, row in r["avg_kz_doctor"].iterrows()]
        make_filtered_tree(
            frame,
            cols,
            data,
            {"Врач": "Врач", "Средний КЗ": "Средний КЗ"},
            clipboard_host=self,
            copy_df=r["avg_kz_doctor"],
            on_copy_df=self._copy_df_as_text,
        )

    def _tab_compare(self) -> None:
        frame = self.tab_frames["compare"]
        if len(self.loaded_files) < 2:
            ttkb.Label(
                frame,
                text="Загрузите минимум 2 файла для сравнения.",
                font=("Calibri", 14),
            ).pack(pady=20)
            return

        ttkb.Label(
            frame,
            text="Выберите файлы для сравнения (до 12):",
            font=("Calibri", 14, "bold"),
        ).pack(pady=10)

        sel_frame = ttkb.Frame(frame)
        sel_frame.pack(fill=tk.X, padx=10, pady=5)

        self.compare_vars: list[tk.BooleanVar] = []
        for f in self.loaded_files:
            var = tk.BooleanVar(value=False)
            self.compare_vars.append(var)
            ttkb.Checkbutton(
                sel_frame,
                text=self._file_label(f),
                variable=var,
                bootstyle="round-toggle",
            ).pack(anchor=tk.W)

        btn_frame = ttkb.Frame(frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        def select_all():
            for var in self.compare_vars:
                var.set(True)

        ttkb.Button(btn_frame, text="Анализировать все", command=select_all, bootstyle="secondary").pack(
            side=tk.LEFT, padx=5
        )

        def do_compare():
            selected_indices = [i for i, var in enumerate(self.compare_vars) if var.get()]
            if len(selected_indices) < 2:
                messagebox.showwarning("Сравнение", "Выберите минимум 2 файла.")
                return
            if len(selected_indices) > 12:
                messagebox.showwarning("Сравнение", "Можно выбрать не более 12 файлов.")
                return
            self._show_comparison(selected_indices)

        ttkb.Button(
            btn_frame,
            text="Построить сравнение",
            command=do_compare,
            bootstyle="success",
        ).pack(side=tk.LEFT, padx=5)

        self.compare_result_frame = ScrollableFrame(frame)
        self.compare_result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    def _show_comparison(self, indices: list[int]) -> None:
        for w in self.compare_result_frame.scrollable_frame.winfo_children():
            w.destroy()

        files = sort_ksg_files_chronologically([self.loaded_files[i] for i in indices])
        summary = build_month_comparison(files)
        labels = [self._file_label(f) for f in files]
        results = [f["results"] for f in summary.get("files", files)]

        total_patients_sum = sum(summary["total_patients"])
        total_sum_sum = sum(summary["total_sum"])
        total_kslp_issues = sum(summary["kslp_issues"])
        avg_kz_overall = float(np.mean(summary["avg_kz"]))

        table_frame1 = ttkb.Labelframe(
            self.compare_result_frame.scrollable_frame, text="Общие показатели", padding=10
        )
        table_frame1.pack(fill=tk.X, pady=5, padx=5)

        tbl_data1: dict = {
            "Показатель": ["Количество пациентов", "Общая сумма, руб.", "Средний КЗ", "Нарушений КСЛП"]
        }
        for label, r in zip(labels, results):
            tbl_data1[label] = [
                r["total_patients"],
                f"{r['total_sum']:,.2f}",
                f"{r['avg_kz_total']:.3f}",
                r["total_kslp_issues"],
            ]
        tbl_data1["Итого"] = [
            total_patients_sum,
            f"{total_sum_sum:,.2f}",
            f"{avg_kz_overall:.3f}",
            total_kslp_issues,
        ]
        df_tbl1 = pd.DataFrame(tbl_data1)

        cols1 = list(df_tbl1.columns)
        tree1 = ttkb.Treeview(table_frame1, columns=cols1, show="headings", height=len(df_tbl1) + 1)
        for col in cols1:
            tree1.heading(col, text=col)
            tree1.column(col, width=150 if col != "Показатель" else 200)
        for _, row in df_tbl1.iterrows():
            tree1.insert("", tk.END, values=list(row))
        tree1.pack(fill=tk.X, pady=5)

        def copy_table1():
            self.clipboard_clear()
            self.clipboard_append(df_tbl1.to_string(index=False))
            messagebox.showinfo("Скопировано", "Таблица общих показателей скопирована в буфер обмена")

        ttkb.Button(
            table_frame1, text="Копировать таблицу", command=copy_table1, bootstyle="secondary"
        ).pack(pady=2)

        all_doctors = summary["doctors"]
        if all_doctors:
            table_frame2 = ttkb.Labelframe(
                self.compare_result_frame.scrollable_frame,
                text="Суммы к оплате по врачам",
                padding=10,
            )
            table_frame2.pack(fill=tk.X, pady=5, padx=5)

            tbl_data2: dict = {"Врач": all_doctors}
            total_by_doctor = {doc: 0.0 for doc in all_doctors}
            for label, r in zip(labels, results):
                sums = r["doctor_sums"].set_index("Врач")["Сумма к оплате"]
                vals = []
                for doc in all_doctors:
                    val = float(sums.get(doc, 0) or 0)
                    total_by_doctor[doc] += val
                    vals.append(f"{val:,.2f}")
                tbl_data2[label] = vals
            tbl_data2["Итого"] = [f"{total_by_doctor[doc]:,.2f}" for doc in all_doctors]
            df_tbl2 = pd.DataFrame(tbl_data2)

            cols2 = list(df_tbl2.columns)
            tree2 = ttkb.Treeview(
                table_frame2, columns=cols2, show="headings", height=min(len(df_tbl2) + 1, 15)
            )
            for col in cols2:
                tree2.heading(col, text=col)
                tree2.column(col, width=150 if col != "Врач" else 250)
            for _, row in df_tbl2.iterrows():
                tree2.insert("", tk.END, values=list(row))
            tree2.pack(fill=tk.X, pady=5)

            def copy_table2():
                self.clipboard_clear()
                self.clipboard_append(df_tbl2.to_string(index=False))
                messagebox.showinfo("Скопировано", "Таблица по врачам скопирована в буфер обмена")

            ttkb.Button(
                table_frame2, text="Копировать таблицу", command=copy_table2, bootstyle="secondary"
            ).pack(pady=2)

        graph_frame = ttkb.Labelframe(
            self.compare_result_frame.scrollable_frame, text="Динамика показателей", padding=10
        )
        graph_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)

        fig = Figure(figsize=(10, 6), dpi=100)
        ax1 = fig.add_subplot(111)
        x = range(len(files))
        width = 0.35

        patients = summary["total_patients"]
        sums = summary["total_sum"]
        kz = summary["avg_kz"]

        bars = ax1.bar([i - width / 2 for i in x], patients, width, label="Пациенты", color="#8DB4E2")
        for bar, val in zip(bars, patients):
            ax1.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                str(val),
                ha="center",
                va="bottom",
            )

        ax1.set_ylabel("Количество пациентов")
        ax1.set_xticks(list(x))
        ax1.set_xticklabels(labels, rotation=45, ha="right")

        ax2 = ax1.twinx()
        line_sum, = ax2.plot(x, sums, "r^-", label="Сумма за месяц", linewidth=2, markersize=8)
        for i, val in enumerate(sums):
            ax2.annotate(
                f"{val:,.0f}",
                (x[i], sums[i]),
                textcoords="offset points",
                xytext=(0, 10),
                ha="center",
                fontsize=8,
                color="red",
            )
        ax2.set_ylabel("Сумма за месяц, руб.", color="red")
        ax2.tick_params(axis="y", labelcolor="red")

        ax3 = ax1.twinx()
        ax3.spines["right"].set_position(("outward", 60))
        line_kz, = ax3.plot(x, kz, "ko--", label="Средний КЗ", linewidth=2, markersize=8)
        for i, val in enumerate(kz):
            ax3.annotate(
                f"{val:.3f}",
                (x[i], kz[i]),
                textcoords="offset points",
                xytext=(0, -15),
                ha="center",
                fontsize=8,
                color="black",
            )
        ax3.set_ylabel("Средний КЗ", color="black")
        ax3.tick_params(axis="y", labelcolor="black")

        lines = [bars, line_sum, line_kz]
        legend_labels = [line.get_label() for line in lines]
        ax1.legend(lines, legend_labels, loc="upper left")
        ax1.set_title("Сравнение файлов")
        fig.tight_layout()

        canvas = FigureCanvasTkAgg(fig, master=graph_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, pady=5)

        ttkb.Button(
            graph_frame,
            text="Сохранить график",
            command=lambda: self._save_graph(fig),
            bootstyle="secondary",
        ).pack(pady=5)

    def _tab_export(self) -> None:
        frame = self.tab_frames["export"]
        ttkb.Label(frame, text="Экспорт отчёта КСГ", font=("Calibri", 14, "bold")).pack(pady=10)
        ttkb.Button(frame, text="Сохранить TXT", command=self.save_report_txt, bootstyle="success").pack(
            pady=5
        )
        ttkb.Button(
            frame, text="Сохранить Excel", command=self.save_report_excel, bootstyle="warning"
        ).pack(pady=5)

    def _copy_df_as_text(self, df: pd.DataFrame) -> None:
        text = df.to_string(index=False)
        self.clipboard_clear()
        self.clipboard_append(text)
        messagebox.showinfo("Скопировано", "Таблица скопирована в буфер обмена")

    def copy_all_tabs(self) -> None:
        if not self.results:
            messagebox.showwarning("Нет данных", "Сначала загрузите и проанализируйте файл КСГ.")
            return
        r = self.results
        parts = [
            "=== ПАЦИЕНТЫ ПО ВРАЧАМ ===",
            r["patient_counts"].to_string(index=False),
            "\n=== ОПЕРАЦИИ ===",
            r["ops_pivot"].to_string() if not r["ops_pivot"].empty else "Нет данных",
            "\n=== СУММА К ОПЛАТЕ ===",
            r["sum_by_doctor"].to_string(index=False),
            f"\nОбщая сумма: {r['total_sum']:,.2f}",
        ]
        if not r["low_money"].empty:
            parts.extend(["\n=== ДЕШЁВЫЕ СЛУЧАИ ===", r["low_money"].to_string(index=False)])
        if not r["high_money"].empty:
            parts.extend(["\n=== ДОРОГИЕ СЛУЧАИ ===", r["high_money"].to_string(index=False)])
        if not r["no_service"].empty:
            parts.extend(["\n=== БЕЗ КОДА УСЛУГИ ===", r["no_service"].to_string(index=False)])
        if not r["kslp_issues"].empty:
            parts.extend(["\n=== НАРУШЕНИЯ КСЛП ===", r["kslp_issues"].to_string(index=False)])
        parts.extend(
            [
                "\n=== СРЕДНИЙ КЗ ===",
                r["avg_kz_doctor"].to_string(index=False),
                f"\nСредний КЗ по отделению: {r['avg_kz_total']}",
            ]
        )
        self.clipboard_clear()
        self.clipboard_append("\n".join(parts))
        messagebox.showinfo("Скопировано", "Все данные КСГ скопированы в буфер обмена.")

    def _auto_adjust_excel_columns(self, writer, sheet_name: str, df: pd.DataFrame, index: bool = False) -> None:
        worksheet = writer.sheets[sheet_name]
        for i, col in enumerate(df.columns):
            max_len = len(str(col)) + 2
            for val in df[col]:
                max_len = max(max_len, len(str(val)) + 2)
            col_letter = worksheet.cell(row=1, column=i + 1).column_letter
            worksheet.column_dimensions[col_letter].width = min(max_len, 50)
        if index:
            max_len = len(str(df.index.name or "")) + 2
            for val in df.index:
                max_len = max(max_len, len(str(val)) + 2)
            worksheet.column_dimensions["A"].width = min(max_len, 10)

    def _save_graph(self, figure) -> None:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG files", "*.png")]
        )
        if file_path:
            figure.savefig(file_path, dpi=150)
            messagebox.showinfo("График сохранён", f"График сохранён в {file_path}")

    def save_report_txt(self) -> None:
        if not self.results:
            messagebox.showwarning("Нет данных", "Сначала загрузите и проанализируйте файл.")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt", filetypes=[("Text files", "*.txt")]
        )
        if not file_path:
            return
        r = self.results
        settings = self.app.app_settings
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(f"Отчёт сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
            f.write(f"Исходный файл: {self.file_name}\n\n")
            f.write(f"Общее количество пациентов: {r['total_patients']}\n")
            f.write("Пациенты по врачам:\n")
            f.write(r["patient_counts"].to_string(index=False) + "\n\n")
            f.write("Операции:\n")
            f.write(r["ops_pivot"].to_string() + "\n\n")
            f.write(f"Общая сумма: {r['total_sum']:,.2f}\n\n")
            f.write("Сумма по врачам:\n")
            f.write(r["sum_by_doctor"].to_string(index=False) + "\n\n")
            if not r["low_money"].empty:
                f.write(f"Случаи с суммой < {settings['ksg_threshold_low']}:\n")
                f.write(r["low_money"].to_string(index=False) + "\n\n")
            if not r["high_money"].empty:
                f.write(f"Случаи с суммой > {settings['ksg_threshold_high']}:\n")
                f.write(r["high_money"].to_string(index=False) + "\n\n")
            if not r["kslp_issues"].empty:
                f.write("Нарушения КСЛП:\n")
                f.write(r["kslp_issues"].to_string(index=False) + "\n\n")
            f.write("Средний КЗ:\n")
            f.write(r["avg_kz_doctor"].to_string(index=False) + "\n")
            f.write(f"Средний по отделению: {r['avg_kz_total']}\n")
        messagebox.showinfo("Сохранено", f"Отчёт сохранён в {file_path}")

    def save_report_excel(self) -> None:
        if not self.results:
            messagebox.showwarning("Нет данных", "Сначала загрузите и проанализируйте файл.")
            return
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")]
        )
        if not file_path:
            return
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            r = self.results
            meta = pd.DataFrame(
                {
                    "Параметр": ["Дата", "Файл"],
                    "Значение": [datetime.now().strftime("%d.%m.%Y %H:%M"), self.file_name],
                }
            )
            meta.to_excel(writer, sheet_name="Метаданные", index=False)
            self._auto_adjust_excel_columns(writer, "Метаданные", meta)
            r["patient_counts"].to_excel(writer, sheet_name="Пациенты по врачам", index=False)
            self._auto_adjust_excel_columns(writer, "Пациенты по врачам", r["patient_counts"])
            if not r["ops_pivot"].empty:
                r["ops_pivot"].to_excel(writer, sheet_name="Операции")
                self._auto_adjust_excel_columns(writer, "Операции", r["ops_pivot"].reset_index())
            pd.DataFrame({"Общая сумма": [r["total_sum"]]}).to_excel(writer, sheet_name="Сумма", index=False)
            r["sum_by_doctor"].to_excel(writer, sheet_name="Сумма по врачам", index=False)
            self._auto_adjust_excel_columns(writer, "Сумма по врачам", r["sum_by_doctor"])
            if not r["low_money"].empty:
                r["low_money"].to_excel(writer, sheet_name="Дешёвые случаи", index=False)
                self._auto_adjust_excel_columns(writer, "Дешёвые случаи", r["low_money"])
            if not r["high_money"].empty:
                r["high_money"].to_excel(writer, sheet_name="Дорогие случаи", index=False)
                self._auto_adjust_excel_columns(writer, "Дорогие случаи", r["high_money"])
            if not r["kslp_issues"].empty:
                r["kslp_issues"].to_excel(writer, sheet_name="КСЛП нарушения", index=False)
                self._auto_adjust_excel_columns(writer, "КСЛП нарушения", r["kslp_issues"])
            r["avg_kz_doctor"].to_excel(writer, sheet_name="Средний КЗ", index=False)
            self._auto_adjust_excel_columns(writer, "Средний КЗ", r["avg_kz_doctor"])
        messagebox.showinfo("Сохранено", f"Отчёт сохранён в {file_path}")
