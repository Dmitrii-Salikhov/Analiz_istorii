from ksg_kslp_profiles import (
    BUILTIN_LOR,
    default_profile_for_department,
    normalize_department_profile_map,
    normalize_ksg_kslp_profiles,
    profile_settings,
    resolve_row_kslp_settings,
)


def test_normalize_ksg_kslp_profiles_includes_lor_rules():
    cfg = {
        "kslp_rules": [{"id": "r1", "name": "Ops", "codes": ["A16.08.017.001"]}],
    }
    profiles = normalize_ksg_kslp_profiles(cfg)
    assert BUILTIN_LOR in profiles
    assert profiles[BUILTIN_LOR]["rules"][0]["codes"] == ["A16.08.017.001"]


def test_default_profile_for_department():
    assert default_profile_for_department("Оториноларингologическое отделение", "009") == BUILTIN_LOR
    assert default_profile_for_department("Терапевтическое отделение") == "standard"


def test_department_profile_map_defaults():
    mapping = normalize_department_profile_map({}, ["Оториноларингologическое отделение", "Терапевтия"])
    assert mapping["Оториноларингologическое отделение"] == BUILTIN_LOR
    assert mapping["Терапевтия"] == "standard"


def test_resolve_row_kslp_settings_standard_age_only():
    profiles = normalize_ksg_kslp_profiles({})
    mapping = {"Терапевтия": "standard"}
    settings = resolve_row_kslp_settings("Терапевтия", None, profiles, mapping)
    assert settings["check_kslp"] is True
    assert settings["use_rules"] is False


def test_profile_settings_none_mode():
    profiles = normalize_ksg_kslp_profiles({})
    none = profile_settings(profiles["none"])
    assert none["check_kslp"] is False
