"""Модальное окно настроек приложения."""
from __future__ import annotations

import tkinter as tk
from tkinter import messagebox

import ttkbootstrap as ttkb

from config_store import save_config

THEME_CHOICES = (
    "cosmo",
    "flatly",
    "journal",
    "litera",
    "lumen",
    "minty",
    "pulse",
    "sandstone",
    "united",
    "yeti",
    "morph",
    "simplex",
    "cerculean",
)


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.title("Настройки")
        self.geometry("520x620")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        settings = app.app_settings
        body = ttkb.Frame(self, padding=16)
        body.pack(fill=tk.BOTH, expand=True)

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
        self.theme_var = tk.StringVar(value=settings.get("theme", "cosmo"))
        theme_combo = ttkb.Combobox(
            body,
            textvariable=self.theme_var,
            values=THEME_CHOICES,
            state="readonly",
            width=28,
        )
        theme_combo.grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 10))
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

        old_theme = self.app.app_settings.get("theme", "cosmo")
        new_theme = self.theme_var.get().strip() or old_theme

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
                "preferred_department": self.dept_var.get().strip(),
                "github_repo": self.repo_var.get().strip(),
                "check_updates_on_start": self.check_updates_var.get(),
            }
        )
        save_config(self.app.app_settings)

        if hasattr(self.app, "date_format_var"):
            self.app.date_format_var.set(self.app.app_settings["date_format"])

        if new_theme != old_theme:
            messagebox.showinfo(
                "Настройки",
                "Тема изменена. Перезапустите приложение для применения.",
                parent=self,
            )

        messagebox.showinfo(
            "Настройки",
            "Настройки сохранены.\nПерезагрузите данные КСГ/ЛОР для применения порогов и формата даты.",
            parent=self,
        )
        self.destroy()
