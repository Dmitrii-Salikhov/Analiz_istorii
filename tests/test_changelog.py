from changelog import format_notes, notes_between


def test_notes_between_upgrade():
    entries = notes_between("1.0.5", "1.0.7")
    versions = [e["version"] for e in entries]
    assert versions == ["1.0.7", "1.0.6"]


def test_notes_between_same_version():
    assert notes_between("1.0.7", "1.0.7") == []


def test_notes_between_from_none():
    entries = notes_between(None, "1.0.6")
    assert any(e["version"] == "1.0.6" for e in entries)
    assert any(e["version"] == "1.0.5" for e in entries)


def test_format_notes_empty():
    text = format_notes([])
    assert "стабильности" in text


def test_format_notes_content():
    text = format_notes(
        [{"version": "9.9.9", "title": "Заголовок", "items": ["Первое", "Второе"]}]
    )
    assert "Заголовок" in text
    assert "• Первое" in text
    assert "• Второе" in text
