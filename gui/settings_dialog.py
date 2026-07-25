"""Модальное окно настроек приложения."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttkb

from config_store import save_config
from gui.ui_theme import (
    DARK_THEME,
    LIGHT_THEME,
    apply_slice_chrome,
    normalize_theme_name,
    register_slice_themes,
)
from gui.widgets import ScrollableFrame

THEME_CHOICES = (LIGHT_THEME, DARK_THEME)
THEME_LABELS = {
    LIGHT_THEME: "Светлая (Slice)",
    DARK_THEME: "Тёмная (Slice)",
}


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("Настройки")
        self.geometry("560x640")
        self.minsize(480, 420)
        self.resizable(True, True)
        self.transient(parent)
        self.grab_set()

        settings = app.app_settings
        scroll = ScrollableFrame(self)
        scroll.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)
        body = ttkb.Frame(scroll.scrollable_frame, padding=16)
        body.pack(fill=tk.BOTH, expand=True)
        body.columnconfigure(0, weight=1)

        row = 0

        ttkb.Label(body, text="Формат даты:", font=("Calibri", 11, "bold")).grid(
            row=row, column=0, sticky="w", pady=(0, 4)
        )
        row += 1
        self.date_format_var = tk.StringVar(value=settings.get("date_format", "dayfirst"))
        df_frame = ttkb.Frame(body)
        df_frame.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 10))
        ttkb.Radiobutton(
            df_frame,
            text="ДД.ММ.ГГГГ",
            variable=self.date_format_var,
            value="dayfirst",
            bootstyle="info",
        ).pack(side=tk.LEFT, padx=(0, 12))
        ttkb.Radiobutton(
            df_frame,
            text="ММ.ДД.ГГГГ",
            variable=self.date_format_var,
            value="monthfirst",
            bootstyle="info",
        ).pack(side=tk.LEFT)
        row += 1

        ttkb.Label(body, text="Тема оформления:", font=("Calibri", 11, "bold")).grid(
            row=row, column=0, sticky="w", pady=(0, 4)
        )
        row += 1
        current_theme = normalize_theme_name(settings.get("theme"))
        self.theme_var = tk.StringVar(value=current_theme)
        theme_frame = ttkb.Frame(body)
        theme_frame.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 10))
        for value in THEME_CHOICES:
            ttkb.Radiobutton(
                theme_frame,
                text=THEME_LABELS[value],
                variable=self.theme_var,
                value=value,
                bootstyle="info",
            ).pack(side=tk.LEFT, padx=(0, 16))
        row += 1

        ttkb.Label(body, text="Пороги КСГ (руб.):", font=("Calibri", 11, "bold")).grid(
            row=row, column=0, sticky="w", pady=(0, 4)
        )
        row += 1
        thresh_frame = ttkb.Frame(body)
        thresh_frame.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 10))
        ttkb.Label(thresh_frame, text="Нижний (<):").pack(side=tk.LEFT)
        self.low_var = tk.StringVar(value=str(settings.get("ksg_threshold_low", 20000)))
        ttkb.Entry(thresh_frame, textvariable=self.low_var, width=12).pack(side=tk.LEFT, padx=(4, 16))
        ttkb.Label(thresh_frame, text="Верхний (>):").pack(side=tk.LEFT)
        self.high_var = tk.StringVar(value=str(settings.get("ksg_threshold_high", 100000)))
        ttkb.Entry(thresh_frame, textvariable=self.high_var, width=12).pack(side=tk.LEFT, padx=4)
        row += 1

        ttkb.Label(body, text="Проверка КСЛП:", font=("Calibri", 11, "bold")).grid(
            row=row, column=0, sticky="w", pady=(0, 4)
        )
        row += 1
        kslp_frame = ttkb.Frame(body)
        kslp_frame.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 6))
        ttkb.Label(kslp_frame, text="Возраст от:").grid(row=0, column=0, sticky="w")
        self.age_min_var = tk.StringVar(value=str(settings.get("kslp_age_min", 0)))
        ttkb.Entry(kslp_frame, textvariable=self.age_min_var, width=6).grid(row=0, column=1, padx=4)
        ttkb.Label(kslp_frame, text="до:").grid(row=0, column=2, sticky="w")
        self.age_max_var = tk.StringVar(value=str(settings.get("kslp_age_max", 4)))
        ttkb.Entry(kslp_frame, textvariable=self.age_max_var, width=6).grid(row=0, column=3, padx=4)
        ttkb.Label(kslp_frame, text="Старший возраст ≥:").grid(row=1, column=0, sticky="w", pady=(6, 0))
        self.senior_var = tk.StringVar(value=str(settings.get("kslp_senior_age", 75)))
        ttkb.Entry(kslp_frame, textvariable=self.senior_var, width=6).grid(
            row=1, column=1, padx=4, pady=(6, 0), sticky="w"
        )
        row += 1

        ttkb.Label(body, text="Коды операций КСЛП (через запятую):").grid(
            row=row, column=0, columnspan=2, sticky="w", pady=(4, 2)
        )
        row += 1
        rules = settings.get("kslp_rules") or []
        if isinstance(rules, list) and rules and isinstance(rules[0], dict):
            codes = list(rules[0].get("codes") or [])
        else:
            codes = settings.get("kslp_operations_codes") or []
        self.codes_var = tk.StringVar(value=", ".join(codes))
        ttkb.Entry(body, textvariable=self.codes_var, width=48).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10)
        )
        row += 1

        ttkb.Label(body, text="Предпочитаемое отделение (ЛОР):", font=("Calibri", 11, "bold")).grid(
            row=row, column=0, sticky="w", pady=(0, 4)
        )
        row += 1
        self.dept_var = tk.StringVar(value=settings.get("preferred_department", ""))
        ttkb.Entry(body, textvariable=self.dept_var, width=48).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10)
        )
        row += 1

        ttkb.Label(body, text="Репозиторий GitHub (owner/repo):", font=("Calibri", 11, "bold")).grid(
            row=row, column=0, sticky="w", pady=(0, 4)
        )
        row += 1
        self.repo_var = tk.StringVar(value=settings.get("github_repo", ""))
        ttkb.Entry(body, textvariable=self.repo_var, width=48).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10)
        )
        row += 1

        self.check_updates_var = tk.BooleanVar(value=bool(settings.get("check_updates_on_start", True)))
        ttkb.Checkbutton(
            body,
            text="Проверять обновления при запуске",
            variable=self.check_updates_var,
            bootstyle="round-toggle",
        ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 10))
        row += 1

        btn_frame = ttkb.Frame(body)
        btn_frame.grid(row=row, column=0, columnspan=2, sticky="e", pady=(12, 0))
        ttkb.Button(btn_frame, text="Отмена", command=self.destroy, bootstyle="secondary").pack(
            side=tk.RIGHT, padx=(8, 0)
        )
        ttkb.Button(btn_frame, text="Сохранить", command=self._save, bootstyle="success").pack(side=tk.RIGHT)

        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _save(self) -> None:
        try:
            low = float(self.low_var.get().replace(",", ".").strip())
            high = float(self.high_var.get().replace(",", ".").strip())
            age_min = int(self.age_min_var.get().strip())
            age_max = int(self.age_max_var.get().strip())
            senior = int(self.senior_var.get().strip())
        except ValueError:
            messagebox.showerror("Ошибка", "Проверьте числовые поля настроек.", parent=self)
            return

        codes_raw = self.codes_var.get().strip()
        codes = [c.strip() for c in codes_raw.split(",") if c.strip()] if codes_raw else []
        # Tk UI edits a single flat list → keep as one rule (preserves multi-rule from Electron if
        # the first rule's codes match; otherwise replace with one rule from the field).
        existing_rules = self.app.app_settings.get("kslp_rules") or []
        first_codes = []
        if (
            isinstance(existing_rules, list)
            and existing_rules
            and isinstance(existing_rules[0], dict)
        ):
            first_codes = [str(c).strip() for c in (existing_rules[0].get("codes") or []) if str(c).strip()]
        if codes == first_codes and isinstance(existing_rules, list) and existing_rules:
            kslp_rules = existing_rules
        else:
            kslp_rules = (
                [{"id": "tk-ops", "name": "Правило 1", "codes": codes}] if codes else []
            )

        old_theme = normalize_theme_name(self.app.app_settings.get("theme"))
        new_theme = normalize_theme_name(self.theme_var.get() or old_theme)

        self.app.app_settings.update(
            {
                "date_format": self.date_format_var.get(),
                "theme": new_theme,
                "ksg_threshold_low": low,
                "ksg_threshold_high": high,
                "kslp_age_min": age_min,
                "kslp_age_max": age_max,
                "kslp_senior_age": senior,
                "kslp_operations_codes": codes,
                "kslp_rules": kslp_rules,
                "preferred_department": self.dept_var.get().strip(),
                "github_repo": self.repo_var.get().strip(),
                "check_updates_on_start": self.check_updates_var.get(),
            }
        )
        save_config(self.app.app_settings)

        if hasattr(self.app, "date_format_var"):
            self.app.date_format_var.set(self.app.app_settings["date_format"])

        if new_theme != old_theme:
            try:
                register_slice_themes()
                self.app.style.theme_use(new_theme)
                apply_slice_chrome(self.app.style, new_theme)
                if hasattr(self.app, "_apply_window_chrome"):
                    self.app._apply_window_chrome(new_theme)
                if hasattr(self.app, "theme_btn"):
                    self.app.theme_btn.configure(text=self.app._theme_button_label())
                if hasattr(self.app.lor_frame, "refresh_theme"):
                    self.app.lor_frame.refresh_theme()
                if hasattr(self.app.ksg_frame, "refresh_theme"):
                    self.app.ksg_frame.refresh_theme()
            except Exception:
                messagebox.showinfo(
                    "Настройки",
                    "Тема сохранена. Перезапустите приложение для полного применения.",
                    parent=self,
                )

        messagebox.showinfo(
            "Настройки",
            "Настройки сохранены.\nПерезагрузите данные КСГ/ЛОР для применения порогов и формата даты.",
            parent=self,
        )
        self.destroy()
