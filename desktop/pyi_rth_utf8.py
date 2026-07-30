# Force UTF-8 stdio early for frozen Windows sidecar (before app code runs).
import os
import sys

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
