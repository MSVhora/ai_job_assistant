from app.services.profile_service import diff_profiles


def test_no_changes_returns_empty_diff() -> None:
    profile = {"headline": "Analyst", "skills": ["SQL"]}
    assert diff_profiles(profile, {"headline": "Analyst", "skills": ["SQL"]}) == {}


def test_scalar_change_uses_dotted_path() -> None:
    old = {"contact": {"full_name": "Jane Doe", "email": "jane@example.com"}, "headline": "A"}
    new = {"contact": {"full_name": "Jane Smith", "email": "jane@example.com"}, "headline": "B"}
    assert diff_profiles(old, new) == {
        "contact.full_name": {"old": "Jane Doe", "new": "Jane Smith"},
        "headline": {"old": "A", "new": "B"},
    }


def test_lists_compare_as_whole_values() -> None:
    assert diff_profiles({"skills": ["SQL"]}, {"skills": ["SQL", "Python"]}) == {
        "skills": {"old": ["SQL"], "new": ["SQL", "Python"]}
    }


def test_null_baseline_reports_additions() -> None:
    assert diff_profiles(None, {"headline": "A", "skills": ["SQL"]}) == {
        "headline": {"old": None, "new": "A"},
        "skills": {"old": None, "new": ["SQL"]},
    }


def test_object_vs_null_emits_per_key() -> None:
    assert diff_profiles({"preferences": None}, {"preferences": {"target_title": "DA"}}) == {
        "preferences.target_title": {"old": None, "new": "DA"}
    }


def test_removed_keys_report_null_new() -> None:
    assert diff_profiles({"headline": "A"}, {}) == {"headline": {"old": "A", "new": None}}
