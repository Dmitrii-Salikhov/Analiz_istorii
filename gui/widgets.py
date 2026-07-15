"""Общие GUI-виджеты: скролл, прогресс, таблицы, drag-and-drop."""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import font as tkfont
from tkinter import messagebox
from typing import Callable, Iterable, Sequence

import ttkbootstrap as ttkb


class ScrollableFrame(ttkb.Frame):
    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.v_scrollbar = ttkb.Scrollbar(self, orient=tk.VERTICAL, command=self.canvas.yview)
        self.h_scrollbar = ttkb.Scrollbar(self, orient=tk.HORIZONTAL, command=self.canvas.xview)
        self.scrollable_frame = ttkb.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(
            yscrollcommand=self.v_scrollbar.set, xscrollcommand=self.h_scrollbar.set
        )

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)


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

    tree = ttkb.Treeview(tree_frame, columns=columns, show="headings", height=15)
    tree_h_scroll = ttkb.Scrollbar(tree_frame, orient=tk.HORIZONTAL, command=tree.xview)
    tree_v_scroll = ttkb.Scrollbar(tree_frame, orient=tk.VERTICAL, command=tree.yview)
    tree.configure(yscrollcommand=tree_v_scroll.set, xscrollcommand=tree_h_scroll.set)
    tree.grid(row=0, column=0, sticky="nsew")
    tree_v_scroll.grid(row=0, column=1, sticky="ns")
    tree_h_scroll.grid(row=1, column=0, sticky="ew")
    tree_frame.grid_rowconfigure(0, weight=1)
    tree_frame.grid_columnconfigure(0, weight=1)

    font = tkfont.Font()
    for col in columns:
        header_text = headings.get(col, col)
        max_width = font.measure(header_text) + 20
        col_idx = list(columns).index(col)
        for row in data:
            max_width = max(max_width, font.measure(str(row[col_idx])) + 20)
        tree.heading(col, text=header_text)
        tree.column(col, width=min(max_width, 500))

    for row in data:
        tree.insert("", tk.END, values=row)

    def update_filter(*_args):
        search_text = filter_var.get().lower()
        if search_text in ("поиск...", "🔍 поиск..."):
            search_text = ""
        tree.delete(*tree.get_children())
        for row in data:
            if search_text in " ".join(str(x).lower() for x in row):
                tree.insert("", tk.END, values=row)

    filter_var.trace_add("write", update_filter)

    def on_tree_mousewheel(event):
        tree.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    tree.bind("<MouseWheel>", on_tree_mousewheel)

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
        messagebox.showinfo("Скопировано", "Данные скопированы в буфер обмена")

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
