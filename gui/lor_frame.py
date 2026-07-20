"""Вкладка анализа ЛОР-отделения."""
from __future__ import annotations

import logging
import re
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox

import pandas as pd
import ttkbootstrap as ttkb
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from config_store import push_recent_file
from excel_io import (
    ExcelParseError,
    MissingColumnsError,
    list_departments,
    load_lor_excel,
    pick_default_department,
)
from gui.chrome import (
    PRIMARY_PAD,
    SECONDARY_PAD,
    SplitSaveButton,
    ToolTip,
    build_context_bar,
    copy_button_tooltip,
    copy_selection_hint,
    export_sections_dialog,
    hotkey_hint,
    make_kpi_card,
    notify_copied,
)
from gui.helpers import auto_adjust_excel_columns, build_empty_state, offer_open_folder
from gui.ui_theme import VIOLATION_TREE_TAGS, chart_color_for_violation
from gui.widgets import ScrollableFrame, enable_file_drop, make_filtered_tree, run_with_progress
from lor_analysis import (
    LorAnalysisResult,
    analyze_lor,
    emk_report_basename,
    filter_by_department,
    format_doctor_name,
    violation_share_table,
)


class LorReportFrame(ttkb.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.file_path: str | None = None
        self.file_name = ""
        self.df_full: pd.DataFrame | None = None
        self.department_var = tk.StringVar()
        self.analysis: LorAnalysisResult | None = None

        self.export_sections = {
            "Основные показатели": tk.BooleanVar(value=True),
            "Возрастные группы": tk.BooleanVar(value=True),
            "Нарушения (все)": tk.BooleanVar(value=True),
            "Сводка по врачам": tk.BooleanVar(value=True),
            "ИДС по врачам": tk.BooleanVar(value=True),
            "Длительные госпитализации": tk.BooleanVar(value=True),
            "Метаданные": tk.BooleanVar(value=True),
        }

        self._build_ui()
        enable_file_drop(self, self._on_dropped_files, extensions=(".xlsx",))

    def _build_ui(self) -> None:
        toolbar = ttkb.Frame(self, padding=(8, 6))
        toolbar.pack(side=tk.TOP, fill=tk.X)

        left = ttkb.Frame(toolbar)
        left.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.btn_load = ttkb.Button(
            left,
            text="Загрузить Excel",
            command=self.load_file,
            bootstyle="primary",
            padding=PRIMARY_PAD,
        )
        self.btn_load.pack(side=tk.LEFT, padx=(0, 8))
        ToolTip(self.btn_load, f"Открыть файл ЭМК ({hotkey_hint('⌘O', 'Ctrl+O')})")

        ttkb.Label(left, text="Отделение:", font=("Calibri", 11)).pack(side=tk.LEFT, padx=(4, 4))
        self.dept_combo = ttkb.Combobox(
            left,
            textvariable=self.department_var,
            state="readonly",
            width=40,
        )
        self.dept_combo.pack(side=tk.LEFT, padx=4)
        self.dept_combo.bind("<<ComboboxSelected>>", self._on_department_changed)

        right = ttkb.Frame(toolbar)
        right.pack(side=tk.RIGHT)
        self.btn_copy = ttkb.Button(
            right,
            text="Копировать",
            command=self._copy_main_metrics,
            state=tk.DISABLED,
            bootstyle="secondary-outline",
            padding=SECONDARY_PAD,
        )
        self.btn_copy.pack(side=tk.LEFT, padx=(0, 6))
        ToolTip(self.btn_copy, copy_button_tooltip())

        self.save_split = SplitSaveButton(
            right,
            on_excel=self._save_excel_with_options,
            on_txt=self._save_txt_with_options,
            tooltip=f"Сохранить Excel ({hotkey_hint('⌘S', 'Ctrl+S')})",
        )
        self.save_split.pack(side=tk.LEFT)
        self.save_split.set_enabled(False)

        self.context_frame, self.context_labels = build_context_bar(
            self,
            [
                ("file", "Файл"),
                ("period", "Период"),
                ("extra", "Отделение"),
                ("stat", "Пациентов"),
            ],
        )
        self.context_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=(0, 4))

        self.work_area = ttkb.Frame(self)
        self.work_area.pack(fill=tk.BOTH, expand=True)

        self.empty_wrap = build_empty_state(
            self.work_area,
            title="Анализ работы отделения",
            steps=[
                "Загрузите отчёт ЭМК",
                "Выберите отделение",
                "Смотрите нарушения и сохраните отчёт",
            ],
            load_text="Загрузить Excel",
            on_load=self.load_file,
        )
        self.empty_wrap.pack(fill=tk.BOTH, expand=True)

        self.notebook = ttkb.Notebook(self.work_area, bootstyle="primary")

        self.main_tab = ttkb.Frame(self.notebook)
        self.viol_main_tab = ttkb.Frame(self.notebook)
        self.doctors_tab = ttkb.Frame(self.notebook)

        self.notebook.add(self.main_tab, text="Основные показатели")
        self.notebook.add(self.viol_main_tab, text="Нарушения")
        self.notebook.add(self.doctors_tab, text="Сводка по врачам")

        self.viol_notebook = ttkb.Notebook(self.viol_main_tab, bootstyle="primary")
        self.viol_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.viol_cat_tab = ttkb.Frame(self.viol_notebook)
        self.viol_all_tab = ttkb.Frame(self.viol_notebook)
        self.viol_notebook.add(self.viol_cat_tab, text="По категориям")
        self.viol_notebook.add(self.viol_all_tab, text="Все нарушения")

        self._update_status()

    def _show_work_content(self, has_analysis: bool) -> None:
        if has_analysis:
            self.empty_wrap.pack_forget()
            self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        else:
            self.notebook.pack_forget()
            self.empty_wrap.pack(fill=tk.BOTH, expand=True)

    def _bind_click_nav(self, widget, tab_index: int) -> None:
        widget.bind("<Button-1>", lambda _e: self.notebook.select(tab_index))
        try:
            widget.configure(cursor="hand2")
        except tk.TclError:
            pass

    def _on_dropped_files(self, paths: list[str]) -> None:
        if paths:
            self._load_path(paths[0])

    def load_file(self) -> None:
        file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
        if file_path:
            self._load_path(file_path)

    def open_path(self, path: str) -> None:
        self._load_path(path)

    def hotkey_open(self) -> None:
        self.load_file()

    def hotkey_save(self) -> None:
        self._save_excel_with_options()

    def hotkey_copy(self) -> None:
        if self.analysis:
            self._copy_main_metrics()

    def _set_actions_enabled(self, enabled: bool) -> None:
        state = tk.NORMAL if enabled else tk.DISABLED
        self.btn_copy.configure(state=state)
        self.save_split.set_enabled(enabled)

    def _load_path(self, file_path: str) -> None:
        self.file_path = file_path
        self.file_name = Path(file_path).name
        self._clear_all_tabs()
        self._set_actions_enabled(False)
        self._show_work_content(False)

        def work(progress):
            return load_lor_excel(file_path, progress=progress)

        def on_success(result):
            self.df_full = result.dataframe
            departments = list_departments(self.df_full)
            preferred = self.app.app_settings.get("preferred_department")
            default = pick_default_department(departments, preferred)
            self.dept_combo["values"] = departments
            if default:
                self.department_var.set(default)
            elif departments:
                self.department_var.set(departments[0])
            else:
                self.department_var.set("")
            push_recent_file(self.app.app_settings, "recent_emk", file_path)
            if hasattr(self.app, "refresh_recent_menus"):
                self.app.refresh_recent_menus()
            self._run_analysis_and_display()

        def on_error(exc: BaseException):
            logging.error("Ошибка загрузки файла %s: %s", file_path, exc)
            if isinstance(exc, (MissingColumnsError, ExcelParseError)):
                messagebox.showerror("Ошибка", str(exc))
            else:
                messagebox.showerror("Ошибка", f"Не удалось обработать файл:\n{exc}")

        run_with_progress(self, "Загрузка ЛОР", work, on_success, on_error)

    def _on_department_changed(self, _event=None) -> None:
        if self.df_full is not None:
            self._run_analysis_and_display()

    def _run_analysis_and_display(self) -> None:
        if self.df_full is None:
            self._show_work_content(False)
            return
        dept = self.department_var.get().strip()
        filtered = filter_by_department(self.df_full, dept or None)
        if filtered.empty:
            messagebox.showwarning("Предупреждение", f"Нет данных по отделению «{dept}»")
            self.analysis = None
            self._update_status()
            self._clear_all_tabs()
            self._set_actions_enabled(False)
            self._show_work_content(False)
            return
        self.analysis = analyze_lor(filtered)
        self._update_status()
        self.display_results()
        self._set_actions_enabled(True)
        self._show_work_content(True)

    def _update_status(self) -> None:
        dept = self.department_var.get() or "—"
        count = str(self.analysis.total_patients) if self.analysis else "—"
        name = self.file_name or "—"
        period = "—"
        if self.analysis and self.analysis.period_start and self.analysis.period_end:
            period = (
                f"{self.analysis.period_start.strftime('%d.%m.%Y')} — "
                f"{self.analysis.period_end.strftime('%d.%m.%Y')}"
            )
        self.context_labels["file"].configure(text=name)
        self.context_labels["period"].configure(text=period)
        self.context_labels["extra"].configure(text=dept)
        self.context_labels["stat"].configure(text=count)

    def _clear_all_tabs(self) -> None:
        for tab in [self.main_tab, self.viol_cat_tab, self.viol_all_tab, self.doctors_tab]:
            for widget in tab.winfo_children():
                widget.destroy()

    def display_results(self) -> None:
        self._create_main_tab()
        self._create_violations_tabs()
        self._create_doctors_tab()

    def _create_main_tab(self) -> None:
        for w in self.main_tab.winfo_children():
            w.destroy()
        if not self.analysis:
            return
        r = self.analysis
        scroll = ScrollableFrame(self.main_tab)
        scroll.pack(fill=tk.BOTH, expand=True)
        main_frame = ttkb.Frame(scroll.scrollable_frame)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        metrics_bar = ttkb.Frame(main_frame)
        metrics_bar.pack(fill=tk.X, pady=(0, 4))
        btn_metrics = ttkb.Button(
            metrics_bar,
            text="Копировать показатели",
            command=self._copy_main_metrics,
            bootstyle="secondary-outline",
            padding=SECONDARY_PAD,
        )
        btn_metrics.pack(side=tk.RIGHT)
        ToolTip(btn_metrics, copy_button_tooltip())

        metrics_frame = ttkb.Frame(main_frame)
        metrics_frame.pack(fill=tk.X, pady=5)
        viol_tab = 1
        for i, (label, value, tab_index) in enumerate(
            [
                ("Всего пациентов", str(r.total_patients), 0),
                ("Средний койко-день", f"{r.avg_beddays:.2f}", viol_tab),
                ("Экстренные госпитализации", str(r.urgent), viol_tab),
                ("Плановые госпитализации", str(r.planned), viol_tab),
            ]
        ):
            card = make_kpi_card(
                metrics_frame,
                label,
                value,
                on_click=lambda idx=tab_index: self.notebook.select(idx),
            )
            card.grid(row=0, column=i, padx=8, pady=5, sticky="nsew")
            metrics_frame.columnconfigure(i, weight=1)

        share_df = violation_share_table(r.violations_df)
        if not share_df.empty:
            chips_frame = ttkb.Frame(main_frame)
            chips_frame.pack(fill=tk.X, pady=(0, 6))
            ttkb.Label(chips_frame, text="Нарушения:", font=("Calibri", 11)).pack(
                side=tk.LEFT, padx=(0, 8)
            )
            for _, row in share_df.iterrows():
                chip = ttkb.Label(
                    chips_frame,
                    text=f"{row['Тип нарушения']}: {row['Количество']} ({row['Доля, %']}%)",
                    bootstyle="info",
                    padding=(8, 4),
                )
                chip.pack(side=tk.LEFT, padx=3)
                self._bind_click_nav(chip, viol_tab)

        chart_row = ttkb.Frame(main_frame)
        chart_row.pack(fill=tk.BOTH, expand=True, pady=10)

        share_frame = ttkb.Labelframe(chart_row, text="Структура нарушений", padding=10)
        share_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        if share_df.empty:
            ttkb.Label(
                share_frame, text="Нарушений нет", font=("Calibri", 13), bootstyle="success"
            ).pack(pady=20)
        else:
            columns = ("Тип нарушения", "Количество", "Доля, %")
            data = [tuple(row) for row in share_df.to_numpy()]
            make_filtered_tree(
                share_frame,
                columns,
                data,
                {c: c for c in columns},
                clipboard_host=self,
                copy_df=share_df,
                on_copy_df=self._copy_df,
                tag_column_index=0,
                tag_colors=VIOLATION_TREE_TAGS,
            )

        graph_frame = ttkb.Frame(chart_row)
        graph_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10)
        fig = Figure(figsize=(5, 3.8), dpi=100)
        ax = fig.add_subplot(111)
        if share_df.empty:
            ax.text(0.5, 0.5, "Нет нарушений", ha="center", va="center")
            ax.axis("off")
        else:
            labels = share_df["Тип нарушения"].tolist()
            shares = share_df["Доля, %"].tolist()
            colors = [chart_color_for_violation(lbl) for lbl in labels]
            bars = ax.bar(range(len(labels)), shares, color=colors)
            ax.set_xticks(range(len(labels)))
            ax.set_xticklabels(labels, rotation=25, ha="right", fontsize=8)
            ax.set_ylabel("Доля, %")
            ax.set_title("Доля нарушений по типам", fontsize=12)
            ax.set_ylim(0, max(shares) * 1.15 if shares else 1)
            for bar, val in zip(bars, shares):
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    f"{val}%",
                    ha="center",
                    va="bottom",
                    fontsize=8,
                )
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=graph_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        ttkb.Button(
            graph_frame,
            text="Сохранить график",
            command=lambda: self._save_graph(fig),
            bootstyle="secondary",
        ).pack(pady=5)

        age_frame = ttkb.Labelframe(main_frame, text="Возрастные группы", padding=8)
        age_frame.pack(fill=tk.X, pady=6)
        age_data = [(grp, cnt) for grp, cnt in r.age_dist.items()]
        make_filtered_tree(
            age_frame,
            ("Группа", "Количество"),
            age_data,
            {"Группа": "Возрастная группа", "Количество": "Количество пациентов"},
            clipboard_host=self,
        )

        note_frame = ttkb.Labelframe(main_frame, text="Аналитическая записка", padding=10)
        note_frame.pack(fill=tk.X, pady=10)
        note_text = tk.Text(note_frame, height=7, font=("Calibri", 12), wrap=tk.WORD)
        note_text.pack(fill=tk.BOTH, expand=True)
        if not r.doctor_stats.empty:
            worst = r.doctor_stats.loc[r.doctor_stats["количество нарушений"].idxmax(), "врач"]
            worst_cnt = r.doctor_stats["количество нарушений"].max()
            note_text.insert(
                tk.END,
                f"Больше всего нарушений (без учёта длительных госпитализаций) у врача: "
                f"{worst} – {worst_cnt} нарушений.\n",
            )
        else:
            note_text.insert(tk.END, "Нарушений (кроме длительных госпитализаций) нет – отличная работа!\n")
        if not r.ids_stats.empty:
            ids_count = len(r.violations_df[r.violations_df["тип_нарушения"] == "ИДС"])
            note_text.insert(tk.END, f"Основная проблема: отсутствие ИДС – {ids_count} случаев.\n")
        if not r.long_stay.empty:
            note_text.insert(
                tk.END,
                f"Длительные госпитализации (>7 дней) как индикатор – {len(r.long_stay)} случаев "
                "(не влияют на рейтинг врача).\n",
            )
        note_text.insert(
            tk.END,
            "Рекомендации: усилить контроль за оформлением ИДС, дневников и эпикризов.",
        )
        note_text.configure(state=tk.DISABLED)

    def _copy_df(self, df: pd.DataFrame) -> None:
        self.clipboard_clear()
        self.clipboard_append(df.to_string(index=False))
        notify_copied(self, "Таблица скопирована")

    def _copy_main_metrics(self) -> None:
        if not self.analysis:
            return
        r = self.analysis
        lines = [
            "Основные показатели",
            f"Отделение: {self.department_var.get()}",
        ]
        if r.period_start and r.period_end:
            lines.append(
                f"Период: {r.period_start.strftime('%d.%m.%Y')} — "
                f"{r.period_end.strftime('%d.%m.%Y')}"
            )
        lines.extend(
            [
                f"Всего пациентов: {r.total_patients}",
                f"Средний койко-день: {r.avg_beddays:.2f}",
                f"Экстренные госпитализации: {r.urgent}",
                f"Плановые госпитализации: {r.planned}",
            ]
        )
        share_df = violation_share_table(r.violations_df)
        if not share_df.empty:
            lines.append("")
            lines.append("Структура нарушений:")
            for _, row in share_df.iterrows():
                lines.append(
                    f"  {row['Тип нарушения']}: {row['Количество']} ({row['Доля, %']}%)"
                )
        self.clipboard_clear()
        self.clipboard_append("\n".join(lines))
        notify_copied(self, "Показатели скопированы")

    def _default_report_path(self, extension: str) -> str:
        r = self.analysis
        start = r.period_start if r else None
        end = r.period_end if r else None
        return emk_report_basename(start, end) + extension

    def _save_excel_with_options(self) -> None:
        if not self.analysis:
            messagebox.showwarning("Нет данных", "Сначала загрузите и проанализируйте файл.")
            return
        if export_sections_dialog(self, self.export_sections, "Сохранить Excel"):
            self.save_report_excel()

    def _save_txt_with_options(self) -> None:
        if not self.analysis:
            messagebox.showwarning("Нет данных", "Сначала загрузите и проанализируйте файл.")
            return
        if export_sections_dialog(self, self.export_sections, "Сохранить TXT"):
            self.save_report_txt()

    def _create_violations_tabs(self) -> None:
        for w in self.viol_cat_tab.winfo_children():
            w.destroy()
        if not self.analysis or self.analysis.violations_df.empty:
            ttkb.Label(
                self.viol_cat_tab,
                text="Нарушений не найдено",
                font=("Calibri", 14),
                bootstyle="success",
            ).pack(pady=50)
            self._create_viol_all_tab()
            return

        r = self.analysis
        cat_notebook = ttkb.Notebook(self.viol_cat_tab, bootstyle="primary")
        cat_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        present_categories: set[str] = set()
        for group_name, group_data in r.violations_df.groupby("тип_нарушения"):
            present_categories.add(group_name)
            tab = ttkb.Frame(cat_notebook)
            cat_notebook.add(tab, text=group_name)
            columns = ("тип_нарушения", "КВС", "возраст", "тип госпитализации", "врач", "нарушение")
            headings = {
                "тип_нарушения": "Тип",
                "КВС": "КВС",
                "возраст": "Возраст",
                "тип госпитализации": "Тип",
                "врач": "Врач",
                "нарушение": "Нарушение",
            }
            data = [
                (group_name,) + tuple(row[col] for col in columns[1:])
                for _, row in group_data.iterrows()
            ]
            make_filtered_tree(
                tab,
                columns,
                data,
                headings,
                clipboard_host=self,
                tag_column_index=0,
                tag_colors=VIOLATION_TREE_TAGS,
            )

            if group_name == "ИДС" and not r.ids_stats.empty:
                summary_frame = ttkb.Labelframe(tab, text="Сводка по врачам (ИДС)", padding=5)
                summary_frame.pack(fill=tk.X, padx=5, pady=10)
                cols = ("Врач", "Нарушения по ИДС")
                data_ids = [(row["врач"], row["нарушения по ИДС"]) for _, row in r.ids_stats.iterrows()]
                make_filtered_tree(
                    summary_frame,
                    cols,
                    data_ids,
                    {"Врач": "Врач", "Нарушения по ИДС": "Количество нарушений ИДС"},
                    clipboard_host=self,
                )

        all_categories = {
            "Первичный осмотр",
            "Эпикриз",
            "МКСБ",
            "Лекарственные назначения",
            "Дневниковые записи",
            "ИДС",
            "Протоколы операций",
        }
        missing = all_categories - present_categories
        if missing:
            ttkb.Label(
                self.viol_cat_tab,
                text="Нарушений в других категориях не найдено",
                font=("Calibri", 12),
                bootstyle="secondary",
            ).pack(side=tk.BOTTOM, pady=(5, 0))

        self._create_viol_all_tab()

    def _create_viol_all_tab(self) -> None:
        for w in self.viol_all_tab.winfo_children():
            w.destroy()
        if not self.analysis or self.analysis.violations_df.empty:
            ttkb.Label(
                self.viol_all_tab,
                text="Нарушений не найдено",
                font=("Calibri", 14),
                bootstyle="success",
            ).pack(pady=50)
            return

        r = self.analysis
        container = ttkb.Frame(self.viol_all_tab)
        container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        category_info = {
            "МКСБ": {"title": "МКСБ (Не подписана)"},
            "Протоколы операций": {"title": "Протоколы операций (несоответствие)"},
            "Эпикриз": {"title": "Эпикризы (не оформлены)"},
            "Первичный осмотр": {"title": "Первичный осмотр (не оформлен)"},
            "Лекарственные назначения": {"title": "Лекарственные назначения (отсутствуют)"},
            "Дневниковые записи": {"title": "Дневниковые записи (недостаточно)"},
            "ИДС": {"title": "ИДС (отсутствует)"},
            "Длительная госпитализация": {"title": "Длительная госпитализация (>7 дней)"},
        }

        grouped = r.violations_df.groupby("тип_нарушения")
        all_sections: list[tuple[str, str]] = []
        for vtype, group in grouped:
            info = category_info.get(vtype, {"title": vtype})
            lines = [f"{info['title']}:"]
            if vtype == "Протоколы операций":
                for _, row in group.iterrows():
                    doctor_short = format_doctor_name(row["врач"])
                    match = re.search(r"операций (\d+), протоколов (\d+)", row["нарушение"])
                    if match:
                        lines.append(
                            f"• {row['КВС']} ({doctor_short}): {match.group(1)} операции / "
                            f"{match.group(2)} протоколов"
                        )
                    else:
                        lines.append(f"• {row['КВС']} ({doctor_short}): {row['нарушение']}")
            elif vtype == "Дневниковые записи":
                for _, row in group.iterrows():
                    doctor_short = format_doctor_name(row["врач"])
                    match = re.search(r"нужно (\d+), оформлено (\d+)", row["нарушение"])
                    if match:
                        lines.append(
                            f"• {row['КВС']} ({doctor_short}): нужно {match.group(1)}, "
                            f"оформлено {match.group(2)}"
                        )
                    else:
                        lines.append(f"• {row['КВС']} ({doctor_short}): {row['нарушение']}")
            elif vtype == "МКСБ":
                for _, row in group.iterrows():
                    doctor_short = format_doctor_name(row["врач"])
                    age_str = f"{int(row['возраст'])}г" if pd.notna(row["возраст"]) else "?г"
                    lines.append(f"• {row['КВС']} ({age_str}) — {doctor_short}")
            elif vtype == "Длительная госпитализация":
                for _, row in group.iterrows():
                    doctor_short = format_doctor_name(row["врач"])
                    match = re.search(r"\((\d+)\)", str(row["нарушение"]))
                    days = match.group(1) if match else "?"
                    lines.append(f"• {row['КВС']} ({doctor_short}) — {days} дн.")
            else:
                for _, row in group.iterrows():
                    doctor_short = format_doctor_name(row["врач"])
                    lines.append(f"• {row['КВС']} ({doctor_short})")
            lines.append("-" * 50)
            all_sections.append((info["title"], "\n".join(lines)))

        top_frame = ttkb.Frame(container)
        top_frame.pack(fill=tk.X, pady=5)

        def copy_all():
            full_text = "\n\n".join(block for _, block in all_sections)
            self.clipboard_clear()
            self.clipboard_append(full_text)
            notify_copied(self, "Нарушения скопированы")

        def copy_selected():
            selected_blocks = [
                block for (_, var), (_, block) in zip(check_vars, all_sections) if var.get()
            ]
            if selected_blocks:
                self.clipboard_clear()
                self.clipboard_append("\n\n".join(selected_blocks))
                notify_copied(self, "Категории скопированы")
            else:
                messagebox.showwarning("Нет выбора", "Не выбрано ни одной категории.")

        # Кнопки всегда на своей строке — не уезжают за край при многих категориях
        btn_row = ttkb.Frame(top_frame)
        btn_row.pack(fill=tk.X, pady=(0, 4))
        ttkb.Button(
            btn_row,
            text="Копировать всё",
            command=copy_all,
            bootstyle="secondary-outline",
            padding=SECONDARY_PAD,
        ).pack(side=tk.LEFT, padx=5)
        btn_sel = ttkb.Button(
            btn_row,
            text="Копировать выбранные",
            command=copy_selected,
            bootstyle="secondary",
            padding=SECONDARY_PAD,
        )
        btn_sel.pack(side=tk.LEFT, padx=5)
        ToolTip(
            btn_sel,
            f"Копировать отмеченные категории\n"
            f"Выделенный текст ниже: {copy_selection_hint()}",
        )

        check_frame = ttkb.Labelframe(
            top_frame, text="Выберите категории для копирования", padding=5
        )
        check_frame.pack(fill=tk.X, padx=5)

        check_vars: list[tuple[str, tk.BooleanVar]] = []
        cols = 3
        for i, (title, _) in enumerate(all_sections):
            var = tk.BooleanVar(value=True)
            check_vars.append((title, var))
            ttkb.Checkbutton(
                check_frame, text=title, variable=var, bootstyle="round-toggle"
            ).grid(row=i // cols, column=i % cols, sticky=tk.W, padx=6, pady=2)
        for c in range(cols):
            check_frame.columnconfigure(c, weight=1)

        text_frame = ttkb.Frame(container)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        text_widget = tk.Text(text_frame, wrap=tk.WORD, font=("Segoe UI", 10), bg="white", fg="black")
        v_scroll = ttkb.Scrollbar(text_frame, orient=tk.VERTICAL, command=text_widget.yview)
        h_scroll = ttkb.Scrollbar(text_frame, orient=tk.HORIZONTAL, command=text_widget.xview)
        text_widget.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        text_widget.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        text_frame.grid_rowconfigure(0, weight=1)
        text_frame.grid_columnconfigure(0, weight=1)

        def update_preview():
            selected_blocks = [
                block for (_, var), (_, block) in zip(check_vars, all_sections) if var.get()
            ]
            text_widget.configure(state=tk.NORMAL)
            text_widget.delete(1.0, tk.END)
            text_widget.insert(tk.END, "\n\n".join(selected_blocks))
            text_widget.configure(state=tk.DISABLED)

        for _, var in check_vars:
            var.trace_add("write", lambda *args, v=var: update_preview())
        update_preview()

        text_widget.bind("<Command-c>", lambda e: self._copy_text_widget(text_widget))
        text_widget.bind("<Control-c>", lambda e: self._copy_text_widget(text_widget))

    def _copy_text_widget(self, widget) -> None:
        try:
            selected = widget.get(tk.SEL_FIRST, tk.SEL_LAST)
            self.clipboard_clear()
            self.clipboard_append(selected)
        except tk.TclError:
            pass

    def _create_doctors_tab(self) -> None:
        for w in self.doctors_tab.winfo_children():
            w.destroy()
        if not self.analysis or self.analysis.doctor_stats.empty:
            ttkb.Label(self.doctors_tab, text="Нет данных о нарушениях", font=("Calibri", 14)).pack(
                pady=50
            )
            return
        r = self.analysis
        columns = ("№", "Врач", "Количество нарушений")
        headings = {
            "№": "№",
            "Врач": "Врач",
            "Количество нарушений": "Количество нарушений (без длительных госпитализаций)",
        }
        data = [
            (i, row["врач"], row["количество нарушений"])
            for i, (_, row) in enumerate(r.doctor_stats.iterrows(), start=1)
        ]
        make_filtered_tree(self.doctors_tab, columns, data, headings, clipboard_host=self)

    def _save_graph(self, figure) -> None:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".png", filetypes=[("PNG files", "*.png")]
        )
        if file_path:
            figure.savefig(file_path, dpi=150)
            messagebox.showinfo("График сохранён", f"График сохранён в {file_path}")

    def save_report_txt(self) -> None:
        if not self.analysis:
            messagebox.showwarning("Нет данных", "Сначала загрузите и проанализируйте файл.")
            return
        r = self.analysis
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt")],
            initialfile=self._default_report_path(".txt"),
        )
        if not file_path:
            return
        with open(file_path, "w", encoding="utf-8") as f:
            if self.export_sections["Метаданные"].get():
                f.write(f"Отчёт сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
                f.write(f"Исходный файл: {self.file_name}\n")
                f.write(f"Отделение: {self.department_var.get()}\n")
                if r.period_start and r.period_end:
                    f.write(
                        f"Период: {r.period_start.strftime('%d.%m.%Y')} — "
                        f"{r.period_end.strftime('%d.%m.%Y')}\n"
                    )
                f.write("\n")
            if self.export_sections["Основные показатели"].get():
                f.write("ОСНОВНЫЕ ПОКАЗАТЕЛИ\n")
                f.write(f"Всего пациентов: {r.total_patients}\n")
                f.write(f"Средний койко-день: {r.avg_beddays:.2f}\n")
                f.write(f"Экстренные: {r.urgent}, Плановые: {r.planned}\n")
                share_df = violation_share_table(r.violations_df)
                if not share_df.empty:
                    f.write("\nСтруктура нарушений:\n")
                    for _, row in share_df.iterrows():
                        f.write(
                            f"  {row['Тип нарушения']}: {row['Количество']} ({row['Доля, %']}%)\n"
                        )
                f.write("\n")
            if self.export_sections["Возрастные группы"].get():
                f.write("ВОЗРАСТНЫЕ ГРУППЫ\n")
                for grp, cnt in r.age_dist.items():
                    f.write(f"  {grp}: {cnt}\n")
                f.write("\n")
            if self.export_sections["Нарушения (все)"].get():
                f.write("НАРУШЕНИЯ\n")
                for _, row in r.violations_df.iterrows():
                    f.write(f"{row['КВС']} | {row['врач']} | {row['нарушение']}\n")
                f.write("\n")
            if self.export_sections["Сводка по врачам"].get():
                f.write("СВОДКА ПО ВРАЧАМ (без учёта длительных госпитализаций)\n")
                for _, row in r.doctor_stats.iterrows():
                    f.write(f"{row['врач']}: {row['количество нарушений']} нарушений\n")
                f.write("\n")
            if self.export_sections["ИДС по врачам"].get() and not r.ids_stats.empty:
                f.write("НАРУШЕНИЯ ПО ИДС\n")
                for _, row in r.ids_stats.iterrows():
                    f.write(f"{row['врач']}: {row['нарушения по ИДС']} нарушений\n")
                f.write("\n")
            if self.export_sections["Длительные госпитализации"].get() and not r.long_stay.empty:
                f.write(f"Длительные госпитализации (>7 дней): {len(r.long_stay)} случаев\n")
                for _, row in r.long_stay.iterrows():
                    doctor = format_doctor_name(row.get("Лечащий врач"))
                    days = int(row.get("Койко-дни_скор", 0))
                    f.write(f"  • {row['Номер КВС']} ({doctor}) — {days} дн.\n")
        offer_open_folder(file_path)

    def save_report_excel(self) -> None:
        if not self.analysis:
            messagebox.showwarning("Нет данных", "Сначала загрузите и проанализируйте файл.")
            return
        r = self.analysis
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx")],
            initialfile=self._default_report_path(".xlsx"),
        )
        if not file_path:
            return
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            if self.export_sections["Метаданные"].get():
                meta_rows = {
                    "Параметр": ["Дата формирования", "Исходный файл", "Отделение"],
                    "Значение": [
                        datetime.now().strftime("%d.%m.%Y %H:%M"),
                        self.file_name,
                        self.department_var.get(),
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
            if self.export_sections["Основные показатели"].get():
                summary = pd.DataFrame(
                    {
                        "Показатель": [
                            "Всего пациентов",
                            "Средний койко-день",
                            "Экстренные",
                            "Плановые",
                        ],
                        "Значение": [
                            r.total_patients,
                            f"{r.avg_beddays:.2f}",
                            r.urgent,
                            r.planned,
                        ],
                    }
                )
                summary.to_excel(writer, sheet_name="Основные показатели", index=False)
                auto_adjust_excel_columns(writer, "Основные показатели", summary)
                share_df = violation_share_table(r.violations_df)
                if not share_df.empty:
                    share_df.to_excel(writer, sheet_name="Структура нарушений", index=False)
                    auto_adjust_excel_columns(writer, "Структура нарушений", share_df)
            if self.export_sections["Возрастные группы"].get():
                age_df = r.age_dist.reset_index()
                age_df.columns = ["Возрастная группа", "Количество"]
                age_df.to_excel(writer, sheet_name="Возрастные группы", index=False)
                auto_adjust_excel_columns(writer, "Возрастные группы", age_df)
            if self.export_sections["Нарушения (все)"].get():
                r.violations_df.to_excel(writer, sheet_name="Нарушения", index=False)
                auto_adjust_excel_columns(writer, "Нарушения", r.violations_df)
            if self.export_sections["Сводка по врачам"].get():
                r.doctor_stats.to_excel(writer, sheet_name="Сводка по врачам", index=False)
                auto_adjust_excel_columns(writer, "Сводка по врачам", r.doctor_stats)
            if self.export_sections["ИДС по врачам"].get() and not r.ids_stats.empty:
                r.ids_stats.to_excel(writer, sheet_name="ИДС по врачам", index=False)
                auto_adjust_excel_columns(writer, "ИДС по врачам", r.ids_stats)
            if self.export_sections["Длительные госпитализации"].get() and not r.long_stay.empty:
                long_df = r.long_stay[
                    ["Номер КВС", "Возраст", "Койко-дни_скор", "Лечащий врач"]
                ].copy()
                long_df.columns = ["КВС", "Возраст", "Койко-дни", "Врач"]
                long_df.to_excel(writer, sheet_name="Длительные госпитализации", index=False)
                auto_adjust_excel_columns(writer, "Длительные госпитализации", long_df)
        offer_open_folder(file_path)
