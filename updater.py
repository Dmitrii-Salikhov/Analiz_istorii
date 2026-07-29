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

from paths import get_base_dir, resource_path

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
        path = resource_path("version.txt")
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


def read_version_file(directory: Path) -> str | None:
    path = Path(directory) / "version.txt"
    try:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    internal = Path(directory) / "_internal" / "version.txt"
    try:
        if internal.exists():
            return internal.read_text(encoding="utf-8").strip()
    except OSError:
        pass
    # Electron: resources/backend/_internal or next to backend exe
    for rel in (
        ("resources", "backend", "version.txt"),
        ("resources", "backend", "_internal", "version.txt"),
    ):
        cand = Path(directory).joinpath(*rel)
        try:
            if cand.exists():
                return cand.read_text(encoding="utf-8").strip()
        except OSError:
            pass
    return None


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
        expected_version = str(release.get("tag_name") or "").lstrip("v").strip()
        try:
            from config_store import load_config, save_config

            cfg = load_config()
            cfg["pending_update_from"] = read_current_version()
            save_config(cfg)
        except Exception as e:
            _log(f"Не удалось записать pending_update_from: {e}")

        if sys.platform == "win32" and getattr(sys, "frozen", False):
            # Распаковка в staging ДО закрытия exe — файлы приложения ещё заняты.
            staging = Path(tempfile.mkdtemp(prefix="analiz_istorii_update_"))
            try:
                _extract_update(zip_path, staging)
                staged_ver = read_version_file(staging)
                _log(f"Staging: {staging}, version={staged_ver}, expected={expected_version}")
                if expected_version and staged_ver and staged_ver != expected_version:
                    progress_win.destroy()
                    messagebox.showerror(
                        "Ошибка обновления",
                        f"В архиве версия {staged_ver}, ожидалась {expected_version}.",
                    )
                    shutil.rmtree(staging, ignore_errors=True)
                    _safe_remove(zip_path)
                    _safe_remove(sha_path)
                    return
                if not staged_ver:
                    progress_win.destroy()
                    messagebox.showerror(
                        "Ошибка обновления",
                        "В архиве не найден version.txt.",
                    )
                    shutil.rmtree(staging, ignore_errors=True)
                    _safe_remove(zip_path)
                    _safe_remove(sha_path)
                    return
            except Exception as e:
                progress_win.destroy()
                messagebox.showerror("Ошибка обновления", f"Не удалось распаковать архив:\n{e}")
                shutil.rmtree(staging, ignore_errors=True)
                _safe_remove(zip_path)
                _safe_remove(sha_path)
                return

            progress_win.destroy()
            _launch_windows_frozen_update(
                app_dir=app_dir,
                staging_dir=staging,
                zip_path=zip_path,
                sha_path=sha_path,
                expected_version=staged_ver or expected_version,
            )
            messagebox.showinfo(
                "Обновление",
                "Обновление подготовлено.\n"
                "После закрытия этого окна файлы будут заменены и приложение перезапустится.\n"
                "Не запускайте программу вручную, пока не откроется новая версия.",
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


def _launch_windows_frozen_update(
    app_dir: Path,
    staging_dir: Path,
    zip_path: Path,
    sha_path: Path,
    expected_version: str,
) -> None:
    """
    После выхода текущего процесса копирует staging → app_dir (robocopy),
    проверяет version.txt и перезапускает exe.

    Пути передаются через UTF-8 JSON (не вшиваются в .ps1), чтобы на русской
    Windows PowerShell 5.1 не портил кириллицу и не создавал «иероглифные»
    папки на рабочем столе.
    """
    job_dir = Path(tempfile.gettempdir()) / f"analiz_upd_job_{os.getpid()}"
    job_dir.mkdir(parents=True, exist_ok=True)
    params_path = job_dir / "params.json"
    ps_script = job_dir / "update.ps1"

    params = {
        "pid": os.getpid(),
        "app_dir": str(app_dir),
        "staging_dir": str(staging_dir),
        "zip_path": str(zip_path),
        "sha_path": str(sha_path),
        "exe_path": str(Path(sys.executable)),
        "log_path": str(app_dir / LOG_NAME),
        "expected_version": expected_version,
        "proc_name": Path(sys.executable).stem,
        "job_dir": str(job_dir),
    }
    params_path.write_text(json.dumps(params, ensure_ascii=False, indent=2), encoding="utf-8")

    # Скрипт только ASCII: все пути читаются из JSON в UTF-8.
    commands = r"""param(
    [Parameter(Mandatory = $true)]
    [string]$ParamsFile
)
$ErrorActionPreference = 'Continue'
if (-not (Test-Path -LiteralPath $ParamsFile)) {
    exit 1
}
$p = Get-Content -LiteralPath $ParamsFile -Encoding UTF8 | ConvertFrom-Json
$log = [string]$p.log_path
function Write-UpdateLog([string]$msg) {
    $line = '{0} {1}' -f (Get-Date -Format 'yyyy-MM-dd HH:mm:ss'), $msg
    try {
        Add-Content -LiteralPath $log -Value $line -Encoding UTF8
    } catch {}
}
Write-UpdateLog ("Windows updater start. pid={0}, staging='{1}', app='{2}', expect={3}" -f $p.pid, $p.staging_dir, $p.app_dir, $p.expected_version)

$waited = $false
try {
    Wait-Process -Id ([int]$p.pid) -Timeout 180 -ErrorAction Stop
    $waited = $true
    Write-UpdateLog ("Process {0} exited" -f $p.pid)
} catch {
    Write-UpdateLog ("Wait-Process: {0}" -f $_.Exception.Message)
}
if (-not $waited) {
    Start-Sleep -Seconds 2
    Stop-Process -Id ([int]$p.pid) -Force -ErrorAction SilentlyContinue
    Write-UpdateLog ("Force-stopped pid {0}" -f $p.pid)
}
Start-Sleep -Milliseconds 800

Get-Process -Name ([string]$p.proc_name) -ErrorAction SilentlyContinue | ForEach-Object {
    Write-UpdateLog ("Stopping leftover {0}" -f $_.Id)
    Stop-Process -Id $_.Id -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Milliseconds 500

if (-not (Test-Path -LiteralPath ([string]$p.staging_dir))) {
    Write-UpdateLog 'ERROR: staging missing'
    exit 1
}

$robolog = Join-Path $env:TEMP 'analiz_istorii_robocopy.log'
$rc = 0
for ($attempt = 1; $attempt -le 5; $attempt++) {
    Write-UpdateLog ("Robocopy attempt {0}" -f $attempt)
    & robocopy ([string]$p.staging_dir) ([string]$p.app_dir) /E /IS /IT /R:3 /W:1 /NFL /NDL /NJH /NJS /NP /LOG+:$robolog | Out-Null
    $rc = $LASTEXITCODE
    Write-UpdateLog ("Robocopy exit={0}" -f $rc)
    if ($rc -lt 8) { break }
    Start-Sleep -Seconds 2
}
if ($rc -ge 8) {
    Write-UpdateLog ("ERROR: robocopy failed with {0}" -f $rc)
}

$srcVer = Join-Path ([string]$p.staging_dir) 'version.txt'
$dstVer = Join-Path ([string]$p.app_dir) 'version.txt'
$srcVerInternal = Join-Path ([string]$p.staging_dir) '_internal\version.txt'
if (Test-Path -LiteralPath $srcVer) {
    Copy-Item -LiteralPath $srcVer -Destination $dstVer -Force
    Write-UpdateLog 'Copied version.txt from staging root'
} elseif (Test-Path -LiteralPath $srcVerInternal) {
    Copy-Item -LiteralPath $srcVerInternal -Destination $dstVer -Force
    Write-UpdateLog 'Copied version.txt from staging _internal'
}
if (Test-Path -LiteralPath $srcVerInternal) {
    $dstInternal = Join-Path ([string]$p.app_dir) '_internal\version.txt'
    New-Item -ItemType Directory -Path (Split-Path -Parent $dstInternal) -Force | Out-Null
    Copy-Item -LiteralPath $srcVerInternal -Destination $dstInternal -Force
}

$installed = $null
if (Test-Path -LiteralPath $dstVer) {
    $installed = (Get-Content -LiteralPath $dstVer -Raw -ErrorAction SilentlyContinue).Trim()
}
Write-UpdateLog ("Installed version.txt='{0}' (expected '{1}')" -f $installed, $p.expected_version)
if ($installed -ne [string]$p.expected_version) {
    Write-UpdateLog 'ERROR: version mismatch after copy'
}

$exe = [string]$p.exe_path
if (Test-Path -LiteralPath $exe) {
    Write-UpdateLog ("Starting '{0}'" -f $exe)
    Start-Process -FilePath $exe -WorkingDirectory ([string]$p.app_dir)
} else {
    Write-UpdateLog ("ERROR: exe missing '{0}'" -f $exe)
}

Remove-Item -LiteralPath ([string]$p.staging_dir) -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath ([string]$p.zip_path) -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath ([string]$p.sha_path) -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath ([string]$p.job_dir) -Recurse -Force -ErrorAction SilentlyContinue
Write-UpdateLog 'Windows updater done'
"""
    ps_script.write_text(commands, encoding="ascii")
    _log(f"Запущен Windows updater job={job_dir}, pid={params['pid']}, staging={staging_dir}")
    creationflags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    # cwd = TEMP (обычно без кириллицы в коротком виде не гарантировано, но пути абсолютные)
    subprocess.Popen(
        [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(ps_script),
            "-ParamsFile",
            str(params_path),
        ],
        cwd=str(Path(tempfile.gettempdir())),
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
