from app.services.skill_canon import MAX_SKILLS, canonicalize, load_aliases


def test_aliases_map_to_canonical_names_case_insensitively() -> None:
    assert canonicalize(["js", "TS", "postgres", "K8s", "GOLANG"]) == [
        "JavaScript",
        "TypeScript",
        "PostgreSQL",
        "Kubernetes",
        "Go",
    ]


def test_unknown_skills_pass_through_trimmed() -> None:
    assert canonicalize(["  Elixir  ", "Obscure Tool"]) == ["Elixir", "Obscure Tool"]


def test_a_skill_the_user_lists_keeps_their_spelling() -> None:
    assert canonicalize(["postgres", "js"], ["postgresql", "Javascript"]) == [
        "postgresql",
        "Javascript",
    ]


def test_duplicates_collapse_after_canonicalization_in_order() -> None:
    assert canonicalize(["js", "JavaScript", "ecmascript", "python"]) == ["JavaScript", "Python"]


def test_blank_entries_are_dropped_and_the_list_is_capped() -> None:
    many = [f"skill-{i}" for i in range(30)]

    result = canonicalize(["", "  ", *many])

    assert len(result) == MAX_SKILLS
    assert result[0] == "skill-0"


def test_every_alias_is_lowercase_and_points_at_a_listed_canonical_name() -> None:
    aliases = load_aliases()

    assert all(alias == alias.lower() for alias in aliases)
    assert aliases["c++"] == "C++"
    assert aliases["ci/cd"] == "CI/CD"
