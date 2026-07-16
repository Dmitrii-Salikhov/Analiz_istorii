"""Общие GUI-виджеты: скролл, прогресс, таблицы, drag-and-drop."""
from __future__ import annotations

import sys
import threading
import tkinter as tk
from tkinter import font as tkfont
from typing import Callable, Iterable, Sequence

import ttkbootstrap as ttkb

from gui.chrome import notify_copied


def wheel_steps(event) -> int:
    """Нормализует delta тачпада/мыши в шаги прокрутки (macOS / Win / Linux)."""
    # Linux scrollbar buttons
    num = getattr(event, "num", None)
    if num == 4:
        return -1
    if num == 5:
        return 1

    delta = int(getattr(event, "delta", 0) or 0)
    if delta == 0:
        return 0

    # Windows / часть Linux: кратно 120
    if abs(delta) >= 120:
        return int(-delta / 120)

    # macOS trackpad: мелкие значения ±1..±N
    if sys.platform == "darwin":
        return -delta
    return -1 if delta > 0 else 1


def bind_mousewheel(widget, on_vertical: Callable, on_horizontal: Callable | None = None) -> None:
    """Вешает прокрутку колёсиком/тачпадом на виджет (и Linux Button-4/5)."""

    def _vertical(event):
        steps = wheel_steps(event)
        if steps:
            on_vertical(steps)
        return "break"

    def _horizontal(event):
        if on_horizontal is None:
            return
        steps = wheel_steps(event)
        if steps:
            on_horizontal(steps)
        return "break"

    widget.bind("<MouseWheel>", _vertical, add="+")
    widget.bind("<Shift-MouseWheel>", _horizontal if on_horizontal else _vertical, add="+")
    widget.bind("<Button-4>", _vertical, add="+")
    widget.bind("<Button-5>", _vertical, add="+")
    if on_horizontal is not None:
        widget.bind("<Shift-Button-4>", lambda e: (on_horizontal(-1), "break")[1], add="+")
        widget.bind("<Shift-Button-5>", lambda e: (on_horizontal(1), "break")[1], add="+")


class ScrollableFrame(ttkb.Frame):
    """Растягиваемый контейнер с вертикальной/горизонтальной прокруткой."""

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0, borderwidth=0)
        self.v_scrollbar = ttkb.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.h_scrollbar = ttkb.Scrollbar(self, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.scrollable_frame = ttkb.Frame(self.canvas)

        self._window_id = self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(
            yscrollcommand=self.v_scrollbar.set,
            xscrollcommand=self.h_scrollbar.set,
        )

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.scrollable_frame.bind("<Configure>", self._on_frame_configure)
        self.canvas.bind("<Configure>", self._on_canvas_configure)

        bind_mousewheel(
            self.canvas,
            lambda steps: self.canvas.yview_scroll(steps, "units"),
            lambda steps: self.canvas.xview_scroll(steps, "units"),
        )
        bind_mousewheel(
            self.scrollable_frame,
            lambda steps: self.canvas.yview_scroll(steps, "units"),
            lambda steps: self.canvas.xview_scroll(steps, "units"),
        )

    def _on_frame_configure(self, _event=None) -> None:
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas_configure(self, event) -> None:
        # Растягиваем внутренний фрейм по ширине холста при ресайзе окна
        bbox = self.canvas.bbox("all")
        content_width = bbox[2] - bbox[0] if bbox else 0
        width = max(event.width, content_width)
        self.canvas.itemconfigure(self._window_id, width=width)
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def scroll_y(self, steps: int) -> None:
        if steps:
            self.canvas.yview_scroll(steps, "units")

    def scroll_x(self, steps: int) -> None:
        if steps:
            self.canvas.xview_scroll(steps, "units")


class ProgressDialog(tk.Toplevel):
    def __init__(self, parent, title: str = "Загрузка"):
        super().__init__(parent)
        self.title(title)
        self.geometry("420x120")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.status = tk.StringVar(value="Подготовка…")
        ttkb.Label(self, textvariable=self.status).pack(pady=(20, 8), padx=16)
        self.bar = ttkb.Progressbar(self, mode="determinate", maximum=100, bootstyle="info")
        self.bar.pack(fill=tk.X, padx=16, pady=8)
        self.protocol("WM_DELETE_WINDOW", lambda: None)

    def set_progress(self, message: str, fraction: float) -> None:
        self.status.set(message)
        self.bar["value"] = max(0, min(100, fraction * 100))
        self.update_idletasks()

    def close(self) -> None:
        try:
            self.grab_release()
        except tk.TclError:
            pass
        self.destroy()


def run_with_progress(
    parent,
    title: str,
    work: Callable[[Callable[[str, float], None]], object],
    on_success: Callable[[object], None],
    on_error: Callable[[BaseException], None],
) -> None:
    dialog = ProgressDialog(parent, title=title)

    def progress(msg: str, frac: float) -> None:
        parent.after(0, lambda: dialog.set_progress(msg, frac))

    def runner():
        try:
            result = work(progress)
            parent.after(0, lambda: (dialog.close(), on_success(result)))
        except BaseException as e:
            parent.after(0, lambda: (dialog.close(), on_error(e)))

    threading.Thread(target=runner, daemon=True).start()


def make_filtered_tree(
    parent,
    columns: Sequence[str],
    data: Sequence[tuple],
    headings: dict,
    clipboard_host=None,
    copy_df=None,
    on_copy_df: Callable | None = None,
    tag_column_index: int | None = None,
    tag_colors: dict[str, str] | None = None,
):
    frame = ttkb.Frame(parent)
    frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    top_bar = ttkb.Frame(frame)
    top_bar.pack(fill=tk.X, pady=(0, 2))
    filter_var = tk.StringVar()
    filter_entry = ttkb.Entry(top_bar, textvariable=filter_var, bootstyle="info")
    filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))
    filter_entry.insert(0, "Поиск...")

    if copy_df is not None and on_copy_df is not None:
        ttkb.Button(
            top_bar,
            text="Копировать таблицу",
            command=lambda: on_copy_df(copy_df),
            bootstyle="secondary",
        ).pack(side=tk.RIGHT)

    tree_frame = ttkb.Frame(frame)
    tree_frame.pack(fill=tk.BOTH, expand=True)

    tree = ttkb.Treeview(tree_frame, columns=columns, show="headings")
    tree_h_scroll = ttkb.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=tree.xview)
    tree_v_scroll = ttkb.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=tree_v_scroll.set, xscrollcommand=tree_h_scroll.set)
    tree.grid(row=0, column=0, sticky="nsew")
    tree_v_scroll.grid(row=0, column=1, sticky="ns")
    tree_h_scroll.grid(row=1, column=0, sticky="ew")
    tree_frame.grid_rowconfigure(0, weight=1)
    tree_frame.grid_columnconfigure(0, weight=1)

    if tag_colors:
        for tag_name, color in tag_colors.items():
            tree.tag_configure(tag_name, background=color)

    font = tkfont.Font()
    for col in columns:
        header_text = headings.get(col, col)
        max_width = font.measure(header_text) + 20
        col_idx = list(columns).index(col)
        for row in data:
            max_width = max(max_width, font.measure(str(row[col_idx])) + 20)
        tree.heading(col, text=header_text)
        tree.column(col, width=min(max_width, 500), stretch=True)

    def _insert_rows(rows):
        for row in rows:
            tags = ()
            if tag_column_index is not None and tag_column_index < len(row):
                tag = str(row[tag_column_index])
                if tag_colors and tag in tag_colors:
                    tags = (tag,)
            tree.insert("", tk.END, values=row, tags=tags)

    _insert_rows(data)

    def update_filter(*_args):
        search_text = filter_var.get().lower()
        if search_text in ("поиск...", "🔍 поиск..."):
            search_text = ""
        tree.delete(*tree.get_children())
        filtered = [
            row
            for row in data
            if search_text in " ".join(str(x).lower() for x in row)
        ]
        _insert_rows(filtered)

    filter_var.trace_add("write", update_filter)

    bind_mousewheel(
        tree,
        lambda steps: tree.yview_scroll(steps, "units"),
        lambda steps: tree.xview_scroll(steps, "units"),
    )

    def copy_selection():
        selected = tree.selection()
        if not selected:
            return
        values = tree.item(selected[0])["values"]
        if not values:
            return
        text = "\t".join(str(v) for v in values)
        host = clipboard_host or parent.winfo_toplevel()
        host.clipboard_clear()
        host.clipboard_append(text)
        notify_copied(host, "Скопировано")

    menu = tk.Menu(tree, tearoff=0)
    menu.add_command(label="Копировать выделенное", command=copy_selection)
    tree.bind("<Button-3>", lambda e: menu.post(e.x_root, e.y_root))
    tree.bind("<Command-c>", lambda e: copy_selection())
    tree.bind("<Control-c>", lambda e: copy_selection())
    return tree


def enable_file_drop(
    widget,
    on_files: Callable[[list[str]], None],
    extensions: Iterable[str] = (".xlsx",),
) -> bool:
    exts = {e.lower() for e in extensions}
    try:
        from tkinterdnd2 import DND_FILES  # type: ignore
    except ImportError:
        return False

    def _parse_paths(data: str) -> list[str]:
        paths = []
        buf = ""
        in_brace = False
        for ch in data:
            if ch == "{":
                in_brace = True
                buf = ""
            elif ch == "}":
                in_brace = False
                paths.append(buf)
                buf = ""
            elif ch == " " and not in_brace:
                if buf:
                    paths.append(buf)
                    buf = ""
            else:
                buf += ch
        if buf:
            paths.append(buf)
        return [p for p in paths if any(p.lower().endswith(ext) for ext in exts)]

    def handler(event):
        files = _parse_paths(event.data)
        if files:
            on_files(files)

    try:
        widget.drop_target_register(DND_FILES)
        widget.dnd_bind("<<Drop>>", handler)
        return True
    except Exception:
        return False
