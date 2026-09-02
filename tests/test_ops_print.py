"""Проверки PDF таблиц операций: генерация, сохранение, открытие, путь в конфиге."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "desktop"
MAIN_CJS = DESKTOP / "electron" / "main.cjs"
PRELOAD = DESKTOP / "electron" / "preload.cjs"
API_DTS = DESKTOP / "electron" / "api.d.ts"
PRINT_TS = DESKTOP / "src" / "lib" / "printOpsReport.ts"
PDF_TS = DESKTOP / "src" / "lib" / "opsPrintPdf.ts"
DIALOG_TS = DESKTOP / "src" / "components" / "OpsPrintDialog.tsx"
CONFIG_STORE = ROOT / "config_store.py"
HANDLERS = ROOT / "bridge" / "handlers.py"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_preload_exposes_pdf_ipc_without_print():
    text = _read(PRELOAD)
    assert "pdfFromHtml:" in text
    assert "pdfSave:" in text
    assert "pdfRelease:" in text
    assert "pdfPrint" not in text


def test_api_types_pdf_save_open_after_save():
    text = _read(API_DTS)
    assert "pdfFromHtml?" in text
    assert "pdfSave?" in text
    assert "openAfterSave?" in text
    assert "pdfPrint" not in text
    assert "base64" not in text


def test_main_process_pdf_from_html_and_save_open():
    text = _read(MAIN_CJS)
    assert "ipcMain.handle('pdf:fromHtml'" in text
    assert "printToPDF" in text
    assert "ipcMain.handle('pdf:save'" in text
    assert "openAfterSave" in text
    assert "revealInFolder" in text
    assert "showItemInFolder" in text
    assert "ipcMain.handle('pdf:print'" not in text
    assert "printPdfBuffer" not in text
    assert "print:html" not in text


def test_ops_print_pdf_helpers_save_and_open():
    text = _read(PDF_TS)
    assert "generateOpsPdfDocument" in text
    assert "saveAndOpenOpsPdfDocument" in text
    assert "defaultOpsPdfSavePath" in text
    assert "printOpsPdfDocument" not in text
    assert "blobUrl" not in text


def test_ops_print_dialog_compact_pdf_only():
    text = _read(DIALOG_TS)
    assert "saveAndOpenOpsPdfDocument" in text
    assert "lastPdfPath" in text
    assert "Печать таблиц" in text
    assert "OpsPdfPreview" not in text
    assert "duplex" not in text
    assert "Печать…" not in text
    assert ">PDF<" in text or "'PDF'" in text or '"PDF"' in text


def test_config_stores_ops_pdf_last_path():
    text = _read(CONFIG_STORE)
    assert "ops_pdf_last_path" in text


def test_config_set_merges_ui_prefs():
    text = _read(HANDLERS)
    assert 'elif key == "ui_prefs"' in text
    assert "merged" in text


def test_print_html_no_forced_page_break_between_tables():
    text = _read(PRINT_TS)
    assert "ops-section--break" not in text
    assert "page-break-before: always" not in text
    assert "printOpsHtml" not in text


def test_oper_table_column_wider_than_service_reduction():
    text = _read(PRINT_TS)
    assert re.search(r"Опер\.стол.*width: '11%'", text)
    assert re.search(r"Услуга.*width: '34%'", text)


def test_desktop_build_succeeds_and_bundle_contains_pdf_export(capsys):
    npm = _npm_bin()
    vite_bin = DESKTOP / "node_modules" / ".bin" / "vite"
    if not vite_bin.is_file():
        ci = subprocess.run(
            [npm, "ci"],
            cwd=DESKTOP,
            capture_output=True,
            text=True,
            check=False,
        )
        if ci.returncode != 0:
            pytest.skip(f"npm ci unavailable in this environment: {ci.stderr.strip()}")

    proc = subprocess.run(
        [npm, "run", "build"],
        cwd=DESKTOP,
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
    assert proc.returncode == 0, "npm run build failed"

    dist_js = list((DESKTOP / "dist" / "assets").glob("*.js"))
    assert dist_js, "vite build produced no JS assets"
    bundle = "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in dist_js)
    assert "openAfterSave" in bundle
    assert "revealInFolder" in bundle
    assert "Печать таблиц в PDF" in bundle
    assert "pdfjs" not in bundle.lower()


def _npm_bin() -> str:
    local = Path.home() / ".local" / "node" / "bin" / "npm"
    if local.is_file():
        return str(local)
    return "npm"
