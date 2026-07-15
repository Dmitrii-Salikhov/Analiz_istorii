import hashlib
import json
import urllib.error

import updater
from updater import compute_sha256, find_release_asset, parse_sha256_text, parse_version


def test_parse_version():
    assert parse_version("v1.2.3") == (1, 2, 3)
    assert parse_version("2.0") == (2, 0)
    assert parse_version("broken") == (0, 0, 0)


def test_parse_sha256_text():
    digest = "a" * 64
    assert parse_sha256_text(digest) == digest
    assert parse_sha256_text(f"{digest}  AnalizIstorii.zip") == digest
    assert parse_sha256_text(f"{digest} other.zip") is None


def test_compute_sha256(tmp_path):
    path = tmp_path / "a.zip"
    path.write_bytes(b"abc")
    assert compute_sha256(path) == hashlib.sha256(b"abc").hexdigest()


def test_find_release_asset():
    release = {"assets": [{"name": "one.zip"}, {"name": "two.sha256"}]}
    assert find_release_asset(release, "two.sha256")["name"] == "two.sha256"


def test_fetch_latest_release(monkeypatch):
    release = {"tag_name": "v2.1.0", "assets": []}
    monkeypatch.setattr(updater, "_http_get", lambda *a, **k: json.dumps(release).encode())
    assert updater.fetch_latest_release("org/repo") == release
    assert updater.get_latest_version("org/repo") == "v2.1.0"


def test_fetch_failure(monkeypatch):
    monkeypatch.setattr(
        updater,
        "_http_get",
        lambda *a, **k: (_ for _ in ()).throw(urllib.error.URLError("offline")),
    )
    assert updater.fetch_latest_release("org/repo") is None
