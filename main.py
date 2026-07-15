#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Точка входа приложения «Анализ работы отделения»."""
from __future__ import annotations

import logging
import sys
from tkinter import messagebox

LOG_FILE = "errors.log"


def setup_logging() -> None:
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.ERROR,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        force=True,
    )


def log_exception(exc_type, exc_value, exc_traceback) -> None:
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_traceback)
        return
    logging.error("Необработанное исключение", exc_info=(exc_type, exc_value, exc_traceback))
    messagebox.showerror(
        "Критическая ошибка",
        f"Произошла ошибка:\n{exc_value}\n\nИнформация записана в {LOG_FILE}",
    )


def create_app():
    from gui.app import App

    return App()


def main() -> None:
    setup_logging()
    sys.excepthook = log_exception
    app = create_app()
    app.mainloop()


if __name__ == "__main__":
    main()
