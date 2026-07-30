"""JSON-RPC bridge over stdin/stdout for Electron UI."""

from __future__ import annotations

import json
import os
import sys
import traceback


def _force_utf8_stdio() -> None:
    """Windows pipes default to cp1251; Node speaks UTF-8 — force UTF-8 both ways."""
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for name in ("stdin", "stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            continue
        try:
            if hasattr(stream, "reconfigure"):
                stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _bootstrap() -> str:
    _force_utf8_stdio()
    root = os.environ.get("ANALIZ_BASE_DIR")
    if not root:
        root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    os.chdir(root)
    if root not in sys.path:
        sys.path.insert(0, root)
    os.environ["ANALIZ_BASE_DIR"] = root
    return root


ROOT = _bootstrap()

from bridge import handlers  # noqa: E402


def _write(obj: dict) -> None:
    payload = json.dumps(obj, ensure_ascii=False, default=str) + "\n"
    out = getattr(sys.stdout, "buffer", None)
    if out is not None:
        out.write(payload.encode("utf-8"))
        out.flush()
    else:
        sys.stdout.write(payload)
        sys.stdout.flush()


def _read_lines():
    """Yield UTF-8 lines from stdin (binary-safe on Windows)."""
    buf = getattr(sys.stdin, "buffer", None)
    if buf is not None:
        for raw in buf:
            yield raw.decode("utf-8", errors="replace").strip()
    else:
        for line in sys.stdin:
            yield line.strip()


def main() -> int:
    for line in _read_lines():
        if not line:
            continue
        req_id = None
        try:
            req = json.loads(line)
            req_id = req.get("id")
            method = req.get("method")
            params = req.get("params") or {}
            if not isinstance(params, dict):
                params = {}
            result = handlers.dispatch(method, params)
            _write({"id": req_id, "result": result})
        except Exception as e:
            tb = traceback.format_exc()
            err_stream = getattr(sys.stderr, "buffer", None)
            if err_stream is not None:
                err_stream.write(tb.encode("utf-8", errors="replace"))
                err_stream.flush()
            else:
                sys.stderr.write(tb)
                sys.stderr.flush()
            _write(
                {
                    "id": req_id,
                    "error": {
                        "message": str(e),
                    },
                }
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
