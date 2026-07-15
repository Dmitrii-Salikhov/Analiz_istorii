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

from excel_io import (
    ExcelParseError,
    MissingColumnsError,
    list_departments,
    load_lor_excel,
    pick_default_department,
)
from gui.widgets import ScrollableFrame, enable_file_drop, make_filtered_tree, run_with_progress
from lor_analysis import LorAnalysisResult, analyze_lor, filter_by_department, format_doctor_name


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
        top_frame = ttkb.Frame(self)
        top_frame.pack(side=tk.TOP, fill=tk.X, pady=5)

        self.btn_load = ttkb.Button(
            top_frame,
            text="📂 Загрузить Excel-файл",
            command=self.load_file,
            bootstyle="info",
            padding=(20, 5),
        )
        self.btn_load.pack(side=tk.LEFT, padx=5)

        ttkb.Label(top_frame, text="Отделение:", font=("Calibri", 11)).pack(side=tk.LEFT, padx=(12, 4))
        self.dept_combo = ttkb.Combobox(
            top_frame,
            textvariable=self.department_var,
            state="readonly",
            width=42,
        )
        self.dept_combo.pack(side=tk.LEFT, padx=4)
        self.dept_combo.bind("<<ComboboxSelected>>", self._on_department_changed)

        self.status_label = ttkb.Label(top_frame, text="Файл не загружен", bootstyle="secondary")
        self.status_label.pack(side=tk.RIGHT, padx=8)

        self.scroll = ScrollableFrame(self)
        self.scroll.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        self.notebook = ttkb.Notebook(self.scroll.scrollable_frame, bootstyle="primary")
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        self.main_tab = ttkb.Frame(self.notebook)
        self.viol_main_tab = ttkb.Frame(self.notebook)
        self.doctors_tab = ttkb.Frame(self.notebook)
        self.export_tab = ttkb.Frame(self.notebook)

        self.notebook.add(self.main_tab, text="📊 Основные показатели")
        self.notebook.add(self.viol_main_tab, text="⚠️ Нарушения")
        self.notebook.add(self.doctors_tab, text="👨‍⚕️ Сводка по врачам")
        self.notebook.add(self.export_tab, text="📁 Экспорт отчёта")

        self.viol_notebook = ttkb.Notebook(self.viol_main_tab, bootstyle="danger")
        self.viol_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.viol_cat_tab = ttkb.Frame(self.viol_notebook)
        self.viol_all_tab = ttkb.Frame(self.viol_notebook)
        self.viol_notebook.add(self.viol_cat_tab, text="📂 По категориям")
        self.viol_notebook.add(self.viol_all_tab, text="📋 Все нарушения")

        bottom_frame = ttkb.Frame(self)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=5)
        self.btn_save_txt = ttkb.Button(
            bottom_frame,
            text="💾 Сохранить отчёт (TXT)",
            command=self.save_report_txt,
            state=tk.DISABLED,
            bootstyle="success",
        )
        self.btn_save_txt.pack(side=tk.LEFT, padx=5)
        self.btn_save_excel = ttkb.Button(
            bottom_frame,
            text="📊 Сохранить в Excel",
            command=self.save_report_excel,
            state=tk.DISABLED,
            bootstyle="warning",
        )
        self.btn_save_excel.pack(side=tk.LEFT, padx=5)

    def _on_dropped_files(self, paths: list[str]) -> None:
        if paths:
            self._load_path(paths[0])

    def load_file(self) -> None:
        file_path = filedialog.askopenfilename(filetypes=[("Excel files", "*.xlsx")])
        if file_path:
            self._load_path(file_path)

    def _load_path(self, file_path: str) -> None:
        self.file_path = file_path
        self.file_name = Path(file_path).name
        self._clear_all_tabs()
        self.btn_save_txt.configure(state=tk.DISABLED)
        self.btn_save_excel.configure(state=tk.DISABLED)

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
            return
        dept = self.department_var.get().strip()
        filtered = filter_by_department(self.df_full, dept or None)
        if filtered.empty:
            messagebox.showwarning("Предупреждение", f"Нет данных по отделению «{dept}»")
            self.analysis = None
            self._update_status()
            self._clear_all_tabs()
            self.btn_save_txt.configure(state=tk.DISABLED)
            self.btn_save_excel.configure(state=tk.DISABLED)
            return
        self.analysis = analyze_lor(filtered)
        self._update_status()
        self.display_results()
        self.btn_save_txt.configure(state=tk.NORMAL)
        self.btn_save_excel.configure(state=tk.NORMAL)

    def _update_status(self) -> None:
        dept = self.department_var.get() or "—"
        count = self.analysis.total_patients if self.analysis else 0
        name = self.file_name or "—"
        self.status_label.configure(text=f"{name}  |  {dept}  |  пациентов: {count}")

    def _clear_all_tabs(self) -> None:
        for tab in [self.main_tab, self.viol_cat_tab, self.viol_all_tab, self.doctors_tab, self.export_tab]:
            for widget in tab.winfo_children():
                widget.destroy()

    def display_results(self) -> None:
        self._create_main_tab()
        self._create_violations_tabs()
        self._create_doctors_tab()
        self._create_export_tab()

    def _create_main_tab(self) -> None:
        for w in self.main_tab.winfo_children():
            w.destroy()
        if not self.analysis:
            return
        r = self.analysis
        main_frame = ttkb.Frame(self.main_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        metrics_frame = ttkb.Frame(main_frame)
        metrics_frame.pack(fill=tk.X, pady=5)
        for i, (label, value) in enumerate(
            [
                ("👥 Всего пациентов", r.total_patients),
                ("📅 Средний койко-день", f"{r.avg_beddays:.2f}"),
                ("🚑 Экстренные госпитализации", r.urgent),
                ("📋 Плановые госпитализации", r.planned),
            ]
        ):
            card = ttkb.Frame(metrics_frame, bootstyle="light", padding=10)
            card.grid(row=0, column=i, padx=10, pady=5, sticky="nsew")
            ttkb.Label(card, text=label, font=("Calibri", 14)).pack()
            ttkb.Label(card, text=value, font=("Calibri", 24, "bold"), bootstyle="warning").pack()
            metrics_frame.columnconfigure(i, weight=1)

        age_main_frame = ttkb.Frame(main_frame)
        age_main_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        age_frame = ttkb.Labelframe(
            age_main_frame, text="📊 Распределение по возрастным группам", padding=10
        )
        age_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        columns = ("Группа", "Количество")
        headings = {"Группа": "Возрастная группа", "Количество": "Количество пациентов"}
        data = [(grp, cnt) for grp, cnt in r.age_dist.items()]
        make_filtered_tree(age_frame, columns, data, headings, clipboard_host=self)

        fig = Figure(figsize=(4, 3), dpi=100)
        ax = fig.add_subplot(111)
        groups = r.age_dist.index.tolist()
        counts = r.age_dist.values.tolist()
        ax.bar(groups, counts, color="#8DB4E2")
        ax.set_title("Возрастные группы", fontsize=12)
        ax.set_ylabel("Пациентов")
        ax.tick_params(axis="x", rotation=30)
        fig.tight_layout()
        canvas = FigureCanvasTkAgg(fig, master=age_main_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10)

        ttkb.Button(
            age_main_frame,
            text="📷 Сохранить график",
            command=lambda: self._save_graph(fig),
            bootstyle="secondary",
        ).pack(side=tk.BOTTOM, pady=5)

        note_frame = ttkb.Labelframe(main_frame, text="📝 Аналитическая записка", padding=10)
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

    def _create_violations_tabs(self) -> None:
        for w in self.viol_cat_tab.winfo_children():
            w.destroy()
        if not self.analysis or self.analysis.violations_df.empty:
            ttkb.Label(
                self.viol_cat_tab,
                text="✅ Нарушений не найдено",
                font=("Calibri", 14),
                bootstyle="success",
            ).pack(pady=50)
            self._create_viol_all_tab()
            return

        r = self.analysis
        icons = {
            "Первичный осмотр": "🩺",
            "Эпикриз": "📄",
            "МКСБ": "📑",
            "Лекарственные назначения": "💊",
            "Дневниковые записи": "📋",
            "ИДС": "✍️",
            "Длительная госпитализация": "⏰",
            "Протоколы операций": "🔪",
        }

        cat_notebook = ttkb.Notebook(self.viol_cat_tab, bootstyle="danger")
        cat_notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        present_categories: set[str] = set()
        for group_name, group_data in r.violations_df.groupby("тип_нарушения"):
            present_categories.add(group_name)
            tab = ttkb.Frame(cat_notebook)
            cat_notebook.add(tab, text=f"{icons.get(group_name, '⚠️')} {group_name}")
            columns = ("КВС", "возраст", "тип госпитализации", "врач", "нарушение")
            headings = {
                "КВС": "КВС",
                "возраст": "Возраст",
                "тип госпитализации": "Тип",
                "врач": "Врач",
                "нарушение": "Нарушение",
            }
            data = [tuple(row[col] for col in columns) for _, row in group_data.iterrows()]
            make_filtered_tree(tab, columns, data, headings, clipboard_host=self)

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
                text="✅ Нарушений в других категориях не найдено",
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
                text="✅ Нарушений не найдено",
                font=("Calibri", 14),
                bootstyle="success",
            ).pack(pady=50)
            return

        r = self.analysis
        container = ttkb.Frame(self.viol_all_tab)
        container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        category_info = {
            "МКСБ": {"icon": "🚫", "title": "МКСБ (Не подписана)"},
            "Протоколы операций": {"icon": "❌", "title": "Протоколы операций (несоответствие)"},
            "Эпикриз": {"icon": "📝", "title": "Эпикризы (не оформлены)"},
            "Первичный осмотр": {"icon": "🩺", "title": "Первичный осмотр (не оформлен)"},
            "Лекарственные назначения": {"icon": "💊", "title": "Лекарственные назначения (отсутствуют)"},
            "Дневниковые записи": {"icon": "📋", "title": "Дневниковые записи (недостаточно)"},
            "ИДС": {"icon": "✍️", "title": "ИДС (отсутствует)"},
            "Длительная госпитализация": {"icon": "⏰", "title": "Длительная госпитализация (>7 дней)"},
        }

        grouped = r.violations_df.groupby("тип_нарушения")
        all_sections: list[tuple[str, str]] = []
        for vtype, group in grouped:
            info = category_info.get(vtype, {"icon": "⚠️", "title": vtype})
            lines = [f"{info['icon']} {info['title']}:"]
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
            messagebox.showinfo("Скопировано", "Все нарушения скопированы в буфер обмена.")

        ttkb.Button(top_frame, text="📋 Копировать всё", command=copy_all, bootstyle="info").pack(
            side=tk.LEFT, padx=5
        )

        check_frame = ttkb.Labelframe(top_frame, text="Выберите категории для копирования", padding=5)
        check_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=10)

        check_vars: list[tuple[str, tk.BooleanVar]] = []
        for title, _ in all_sections:
            var = tk.BooleanVar(value=True)
            check_vars.append((title, var))
            ttkb.Checkbutton(check_frame, text=title, variable=var, bootstyle="round-toggle").pack(
                side=tk.LEFT, padx=5
            )

        def copy_selected():
            selected_blocks = [
                block for (_, var), (_, block) in zip(check_vars, all_sections) if var.get()
            ]
            if selected_blocks:
                self.clipboard_clear()
                self.clipboard_append("\n\n".join(selected_blocks))
                messagebox.showinfo("Скопировано", "Выбранные категории скопированы в буфер обмена.")
            else:
                messagebox.showwarning("Нет выбора", "Не выбрано ни одной категории.")

        ttkb.Button(top_frame, text="📋 Копировать выбранные", command=copy_selected, bootstyle="warning").pack(
            side=tk.LEFT, padx=5
        )

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

    def _create_export_tab(self) -> None:
        for w in self.export_tab.winfo_children():
            w.destroy()
        frame = ttkb.Frame(self.export_tab, padding=20)
        frame.pack(fill=tk.BOTH, expand=True)
        ttkb.Label(frame, text="Выберите разделы для экспорта", font=("Calibri", 14, "bold")).pack(
            anchor=tk.W, pady=10
        )
        for section, var in self.export_sections.items():
            ttkb.Checkbutton(frame, text=section, variable=var, bootstyle="round-toggle").pack(
                anchor=tk.W, padx=20
            )
        ttkb.Label(
            frame,
            text="Метаданные (дата и имя файла) будут добавлены при включении опции «Метаданные».",
            font=("Calibri", 10),
        ).pack(anchor=tk.W, pady=5)

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
            defaultextension=".txt", filetypes=[("Text files", "*.txt")]
        )
        if not file_path:
            return
        with open(file_path, "w", encoding="utf-8") as f:
            if self.export_sections["Метаданные"].get():
                f.write(f"Отчёт сформирован: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n")
                f.write(f"Исходный файл: {self.file_name}\n")
                f.write(f"Отделение: {self.department_var.get()}\n\n")
            if self.export_sections["Основные показатели"].get():
                f.write("ОСНОВНЫЕ ПОКАЗАТЕЛИ\n")
                f.write(f"Всего пациентов: {r.total_patients}\n")
                f.write(f"Средний койко-день: {r.avg_beddays:.2f}\n")
                f.write(f"Экстренные: {r.urgent}, Плановые: {r.planned}\n\n")
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
                f.write(
                    f"Длительные госпитализации (>7 дней): {len(r.long_stay)} случаев (индикатор)\n"
                )
        messagebox.showinfo("Сохранено", f"Отчёт сохранён в {file_path}")

    def save_report_excel(self) -> None:
        if not self.analysis:
            messagebox.showwarning("Нет данных", "Сначала загрузите и проанализируйте файл.")
            return
        r = self.analysis
        file_path = filedialog.asksaveasfilename(
            defaultextension=".xlsx", filetypes=[("Excel files", "*.xlsx")]
        )
        if not file_path:
            return
        with pd.ExcelWriter(file_path, engine="openpyxl") as writer:
            if self.export_sections["Метаданные"].get():
                meta = pd.DataFrame(
                    {
                        "Параметр": ["Дата формирования", "Исходный файл", "Отделение"],
                        "Значение": [
                            datetime.now().strftime("%d.%m.%Y %H:%M"),
                            self.file_name,
                            self.department_var.get(),
                        ],
                    }
                )
                meta.to_excel(writer, sheet_name="Метаданные", index=False)
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
            if self.export_sections["Возрастные группы"].get():
                age_df = r.age_dist.reset_index()
                age_df.columns = ["Возрастная группа", "Количество"]
                age_df.to_excel(writer, sheet_name="Возрастные группы", index=False)
            if self.export_sections["Нарушения (все)"].get():
                r.violations_df.to_excel(writer, sheet_name="Нарушения", index=False)
            if self.export_sections["Сводка по врачам"].get():
                r.doctor_stats.to_excel(writer, sheet_name="Сводка по врачам", index=False)
            if self.export_sections["ИДС по врачам"].get() and not r.ids_stats.empty:
                r.ids_stats.to_excel(writer, sheet_name="ИДС по врачам", index=False)
            if self.export_sections["Длительные госпитализации"].get() and not r.long_stay.empty:
                long_df = r.long_stay[
                    ["Номер КВС", "Возраст", "Койко-дни_скор", "Лечащий врач"]
                ].copy()
                long_df.columns = ["КВС", "Возраст", "Койко-дни", "Врач"]
                long_df.to_excel(writer, sheet_name="Длительные госпитализации", index=False)
        messagebox.showinfo("Сохранено", f"Отчёт сохранён в {file_path}")
