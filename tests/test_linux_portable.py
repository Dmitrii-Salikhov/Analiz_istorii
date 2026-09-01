from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PORTABLE = ROOT / "desktop" / "linux-portable"


def test_linux_portable_launcher_files_exist():
    assert (PORTABLE / "start.sh").is_file()
    assert (PORTABLE / "AnalizIstorii.desktop").is_file()
    assert (PORTABLE / "install-shortcut.sh").is_file()


def test_start_sh_uses_no_sandbox():
    text = (PORTABLE / "start.sh").read_text(encoding="utf-8")
    assert "--no-sandbox" in text
    assert "./AnalizIstorii" in text


def test_in_folder_desktop_has_icon_and_relative_exec():
    text = (PORTABLE / "AnalizIstorii.desktop").read_text(encoding="utf-8")
    assert "Icon=./icon.png" in text
    assert "Exec=./start.sh" in text
    assert "Terminal=false" in text


def test_install_shortcut_uses_absolute_paths():
    text = (PORTABLE / "install-shortcut.sh").read_text(encoding="utf-8")
    assert "Icon=$ROOT/icon.png" in text
    assert 'Exec=$ROOT/start.sh' in text
    assert "Рабочий стол" in text
