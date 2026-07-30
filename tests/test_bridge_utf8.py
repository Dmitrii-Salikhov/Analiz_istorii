"""UTF-8 bridge I/O helpers (Windows pipe safety)."""
from __future__ import annotations

import io
import json
import sys

from bridge import cli


def test_write_emits_utf8_bytes():
    buf = io.BytesIO()

    class Out:
        buffer = buf

        def write(self, _s):
            raise AssertionError("text write should not be used when buffer exists")

        def flush(self):
            pass

    old = sys.stdout
    sys.stdout = Out()  # type: ignore[assignment]
    try:
        cli._write({"id": 1, "result": {"name": "ЭМК стандарт", "path": r"C:\Users\Тест\файл.xlsx"}})
    finally:
        sys.stdout = old

    raw = buf.getvalue()
    assert "ЭМК стандарт".encode("utf-8") in raw
    assert "файл.xlsx".encode("utf-8") in raw
    msg = json.loads(raw.decode("utf-8").strip())
    assert msg["result"]["name"] == "ЭМК стандарт"


def test_read_lines_decodes_utf8_bytes():
    data = (
        json.dumps({"id": 2, "method": "ping", "params": {"p": "Отчет.xlsx"}}, ensure_ascii=False)
        + "\n"
    ).encode("utf-8")

    class In:
        buffer = io.BytesIO(data)

    old = sys.stdin
    sys.stdin = In()  # type: ignore[assignment]
    try:
        lines = list(cli._read_lines())
    finally:
        sys.stdin = old

    assert len(lines) == 1
    req = json.loads(lines[0])
    assert req["params"]["p"] == "Отчет.xlsx"
