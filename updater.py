"""Автообновление из GitHub Releases (проверка SHA-256)."""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

from paths import get_base_dir

ZIP_FILENAME = "AnalizIstorii.zip"
SHA256_FILENAME = f"{ZIP_FILENAME}.sha256"
USER_AGENT = "AnalizIstorii-Updater"
LOG_NAME = "update.log"


def _log(message: str) -> None:
    try:
        path = get_base_dir() / LOG_NAME
        with path.open("a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except OSError:
        logging.error("update log failed: %s", message)


def _ssl_context():
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def _http_get(url: str, timeout: int = 15) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout, context=_ssl_context()) as resp:
        return resp.read()


def api_url_for_repo(repo: str) -> str:
    return f"https://api.github.com/repos/{repo}/releases/latest"


def fetch_latest_release(repo: str):
    try:
        data = json.loads(_http_get(api_url_for_repo(repo), timeout=10).decode("utf-8"))
        _log(f"Получен тег: {data.get('tag_name')} ({repo})")
        return data
    except (OSError, urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as e:
        _log(f"Ошибка проверки обновлений: {e}")
        return None


def get_latest_version(repo: str):
    release = fetch_latest_release(repo)
    return release.get("tag_name") if release else None


def parse_version(tag):
    if tag:
        parts = tag.lstrip("v").split(".")
        try:
            return tuple(int(p) for p in parts)
        except ValueError:
            pass
    return (0, 0, 0)


def read_current_version() -> str:
    try:
        return (get_base_dir() / "version.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


def find_release_asset(release, filename: str):
    for asset in release.get("assets") or []:
        if asset.get("name") == filename:
            return asset
    return None


def parse_sha256_text(text: str, expected_filename: str = ZIP_FILENAME):
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Fa-f0-9]{64})(?:\s+\*?(\S+))?$", line)
        if not match:
            continue
        digest, name = match.group(1), match.group(2)
        if name is None or os.path.basename(name) == expected_filename:
            return digest.lower()
    return None


def compute_sha256(path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def download_with_retries(url: str, dest_path, max_retries: int = 7, timeout: int = 60) -> bool:
    for attempt in range(1, max_retries + 1):
        try:
            data = _http_get(url, timeout=timeout)
            with open(dest_path, "wb") as out_file:
                out_file.write(data)
            return True
        except (OSError, urllib.error.URLError, TimeoutError, ValueError) as e:
            _log(f"Ошибка скачивания (попытка {attempt}/{max_retries}): {e}")
            if attempt == max_retries:
                return False
            time.sleep(3 * (2 ** (attempt - 1)))
    return False


def _asset_download_url(asset):
    return asset.get("browser_download_url") if asset else None


def _safe_remove(path) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except OSError:
        pass


def _extract_update(zip_path: Path, app_dir: Path) -> None:
    skip_names = {".git", "venv", ".venv", "__pycache__", "config.json", "errors.log", "update.log"}
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.namelist()
        # strip single top-level folder if present
        tops = {m.split("/")[0] for m in members if m and not m.endswith("/")}
        prefix = ""
        if len(tops) == 1:
            only = next(iter(tops))
            if all(m == only or m.startswith(only + "/") for m in members):
                prefix = only + "/"

        for info in zf.infolist():
            name = info.filename
            if prefix and name.startswith(prefix):
                name = name[len(prefix) :]
            if not name or name.endswith("/"):
                continue
            top = name.split("/")[0]
            if top in skip_names:
                continue
            dest = app_dir / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, open(dest, "wb") as out:
                shutil.copyfileobj(src, out)


def perform_update(repo: str, release=None) -> None:
    from tkinter import messagebox
    import tkinter as tk

    if release is None:
        release = fetch_latest_release(repo)
    if not release:
        messagebox.showerror(
            "Ошибка обновления",
            "Не удалось получить данные о релизе.\nПроверьте интернет-соединение.",
        )
        return

    zip_asset = find_release_asset(release, ZIP_FILENAME)
    sha_asset = find_release_asset(release, SHA256_FILENAME) or find_release_asset(
        release, "SHA256SUMS"
    )
    if not zip_asset or not _asset_download_url(zip_asset):
        messagebox.showerror("Ошибка обновления", f"В релизе нет файла {ZIP_FILENAME}.")
        return
    if not sha_asset or not _asset_download_url(sha_asset):
        messagebox.showerror(
            "Ошибка обновления",
            "В релизе нет контрольной суммы (*.sha256).\nОбновление отменено.",
        )
        return

    tmp_dir = Path(tempfile.gettempdir())
    zip_path = tmp_dir / ZIP_FILENAME
    sha_path = tmp_dir / SHA256_FILENAME

    progress_win = tk.Toplevel()
    progress_win.title("Обновление")
    progress_win.geometry("340x120")
    progress_win.resizable(False, False)
    tk.Label(
        progress_win,
        text="Идёт обновление…\nСкачивание и проверка целостности.",
        font=("Segoe UI", 10),
    ).pack(expand=True, pady=15)
    progress_win.update()

    try:
        if not download_with_retries(_asset_download_url(zip_asset), zip_path):
            progress_win.destroy()
            messagebox.showerror("Ошибка обновления", "Не удалось скачать обновление.")
            return
        if not download_with_retries(_asset_download_url(sha_asset), sha_path, max_retries=3):
            progress_win.destroy()
            messagebox.showerror("Ошибка обновления", "Не удалось скачать контрольную сумму.")
            _safe_remove(zip_path)
            return
        expected = parse_sha256_text(sha_path.read_text(encoding="utf-8", errors="ignore"))
        if not expected:
            progress_win.destroy()
            messagebox.showerror("Ошибка обновления", "Файл контрольной суммы повреждён.")
            _safe_remove(zip_path)
            _safe_remove(sha_path)
            return
        actual = compute_sha256(zip_path)
        if actual != expected:
            progress_win.destroy()
            messagebox.showerror(
                "Ошибка обновления",
                "Контрольная сумма архива не совпала. Обновление отменено.",
            )
            _log(f"SHA-256 mismatch: expected={expected}, actual={actual}")
            _safe_remove(zip_path)
            _safe_remove(sha_path)
            return
        _log(f"SHA-256 OK: {actual}")

        app_dir = get_base_dir()
        if sys.platform == "win32" and getattr(sys, "frozen", False):
            progress_win.destroy()
            _launch_windows_frozen_update(app_dir, zip_path, sha_path)
            messagebox.showinfo(
                "Обновление",
                "Обновление скачано.\nПриложение закроется и установит новую версию.",
            )
            sys.exit(0)

        _extract_update(zip_path, app_dir)
        _safe_remove(zip_path)
        _safe_remove(sha_path)
        progress_win.destroy()
        messagebox.showinfo(
            "Обновление",
            "Обновление установлено.\nПриложение будет перезапущено.",
        )
        _restart_application(app_dir)
        sys.exit(0)
    except Exception as e:
        try:
            progress_win.destroy()
        except Exception:
            pass
        messagebox.showerror("Ошибка обновления", f"Сбой при обновлении:\n{e}")
        _safe_remove(zip_path)
        _safe_remove(sha_path)


def _restart_application(app_dir: Path) -> None:
    if getattr(sys, "frozen", False):
        subprocess.Popen([sys.executable], cwd=str(app_dir))
        return
    python = sys.executable
    main_py = str(app_dir / "main.py")
    subprocess.Popen([python, main_py], cwd=str(app_dir))


def _launch_windows_frozen_update(app_dir: Path, zip_path: Path, sha_path: Path) -> None:
    """
    На Windows exe/DLL заняты процессом — распаковку делает внешний PowerShell-скрипт
    после завершения текущего процесса.
    """
    ps_script = Path(tempfile.gettempdir()) / "update_analiz_istorii.ps1"
    exe_name = Path(sys.executable).name
    ps_app = str(app_dir).replace("'", "''")
    ps_zip = str(zip_path).replace("'", "''")
    ps_sha = str(sha_path).replace("'", "''")
    ps_exe = str(Path(sys.executable)).replace("'", "''")
    commands = f"""
$ErrorActionPreference = 'SilentlyContinue'
$timeout = 60
$procName = '{Path(exe_name).stem}'
Get-Process -Name $procName -ErrorAction SilentlyContinue | Stop-Process -Force
for ($i=0; $i -lt $timeout; $i++) {{
    if (-not (Get-Process -Name $procName -ErrorAction SilentlyContinue)) {{ break }}
    Start-Sleep -Milliseconds 100
}}
Expand-Archive -Path '{ps_zip}' -DestinationPath '{ps_app}' -Force
if (Test-Path '{ps_app}\\_internal\\version.txt') {{
    Copy-Item -Path '{ps_app}\\_internal\\version.txt' -Destination '{ps_app}\\version.txt' -Force
}}
Start-Process -FilePath '{ps_exe}'
Remove-Item -Path '{ps_zip}' -Force -ErrorAction SilentlyContinue
Remove-Item -Path '{ps_sha}' -Force -ErrorAction SilentlyContinue
"""
    ps_script.write_text(commands, encoding="utf-8")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    subprocess.Popen(
        [
            "powershell.exe",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps_script),
        ],
        creationflags=creationflags,
    )


def check_for_updates(repo: str, current_version_str: str, silent_if_updated: bool = False):
    from tkinter import messagebox
    import tkinter as tk

    release = fetch_latest_release(repo)
    if not release:
        if not silent_if_updated:
            messagebox.showinfo(
                "Проверка обновлений",
                "Не удалось проверить обновления.\nПроверьте интернет-соединение\n"
                f"и доступность репозитория {repo}.",
            )
        return

    latest_tag = release.get("tag_name")
    latest_version = parse_version(latest_tag)
    current_version = parse_version(current_version_str)
    _log(
        f"Сравнение: локальная {current_version_str} ({current_version}), "
        f"последняя {latest_tag} ({latest_version})"
    )

    if latest_version > current_version:
        root = tk._default_root
        owned = False
        if root is None:
            root = tk.Tk()
            root.withdraw()
            owned = True
        answer = messagebox.askyesno(
            "Доступно обновление",
            f"Вышла новая версия {latest_tag}!\n"
            f"Текущая версия: v{current_version_str}\n\n"
            "Скачать и установить сейчас?\n(проверка SHA-256)",
        )
        if answer:
            perform_update(repo, release=release)
        if owned:
            root.destroy()
    else:
        _log("Обновлений нет.")
        if not silent_if_updated:
            messagebox.showinfo("Проверка обновлений", "У вас установлена последняя версия.")
