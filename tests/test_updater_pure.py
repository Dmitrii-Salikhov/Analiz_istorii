import hashlib
import json
import urllib.error
import zipfile

import updater
from updater import (
    _extract_update,
    compute_sha256,
    find_release_asset,
    parse_sha256_text,
    parse_version,
    read_version_file,
)


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


def test_extract_update_and_read_version(tmp_path):
    zip_path = tmp_path / "AnalizIstorii.zip"
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("AnalizIstorii.exe", b"fake")
        zf.writestr("version.txt", "1.0.9\n")
        zf.writestr("_internal/version.txt", "1.0.9\n")
        zf.writestr("config.json", '{"from_zip": true}')

    staging = tmp_path / "staging"
    staging.mkdir()
    app_dir = tmp_path / "app"
    app_dir.mkdir()
    (app_dir / "version.txt").write_text("1.0.7\n", encoding="utf-8")
    (app_dir / "config.json").write_text('{"keep": true}', encoding="utf-8")

    _extract_update(zip_path, staging)
    assert read_version_file(staging) == "1.0.9"
    assert (staging / "AnalizIstorii.exe").exists()
    assert not (staging / "config.json").exists()

    _extract_update(zip_path, app_dir)
    assert read_version_file(app_dir) == "1.0.9"
    assert (app_dir / "config.json").read_text(encoding="utf-8") == '{"keep": true}'
