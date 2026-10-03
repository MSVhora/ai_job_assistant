import pytest

from app.adapters.job_sources.base import (
    SourceFilterDecl,
    SourceFilterOption,
    SourceFilterValue,
    validate_source_options,
)
from app.core.errors import InvalidSourceFilterError
from app.schemas.job_search import SourceQuerySpec


def decl(key: str, type_: str) -> SourceFilterDecl:
    return SourceFilterDecl(
        key=key,
        label=key,
        type=type_,  # type: ignore[arg-type]
        options=[
            SourceFilterOption(value="relevance", label="Relevance"),
            SourceFilterOption(value="date", label="Date"),
        ]
        if type_ == "select"
        else None,
    )


def test_accepts_valid_options_for_each_declaration_type() -> None:
    declarations = [
        decl("title_only", "boolean"),
        decl("distance_km", "number"),
        decl("sort_by", "select"),
        decl("company_ids", "multiselect"),
        decl("geo_id", "text"),
    ]
    options: dict[str, SourceFilterValue] = {
        "title_only": True,
        "distance_km": 25,
        "sort_by": "date",
        "company_ids": ["123", "456"],
        "geo_id": "Berlin",
    }

    validate_source_options(declarations, options, "adzuna")


@pytest.mark.parametrize(
    ("type_", "value", "message"),
    [
        ("boolean", "true", "must be true or false"),
        ("boolean", 1, "must be true or false"),
        ("number", "25", "must be an integer"),
        ("number", True, "must be an integer"),
        ("number", 25.5, "must be an integer"),
        ("select", "salary", "must be one of: date, relevance"),
        ("select", 25, "must be one of: date, relevance"),
        ("multiselect", "123", "must be a non-empty list of strings"),
        ("multiselect", [], "must be a non-empty list of strings"),
        ("multiselect", [1], "must be a non-empty list of strings"),
        ("text", "", "must be a non-empty string"),
        ("text", 25, "must be a non-empty string"),
    ],
)
def test_rejects_bad_types_and_values(type_: str, value: object, message: str) -> None:
    declarations = [decl("filter_key", type_)]

    with pytest.raises(InvalidSourceFilterError, match=message):
        validate_source_options(declarations, {"filter_key": value}, "adzuna")  # type: ignore[arg-type]


def test_rejects_unknown_option_key_naming_key_and_source() -> None:
    with pytest.raises(InvalidSourceFilterError, match=r"unknown filter 'foo' for source 'adzuna'"):
        validate_source_options([decl("title_only", "boolean")], {"foo": "bar"}, "adzuna")


def test_select_uses_declared_values_not_labels() -> None:
    declarations = [decl("sort_by", "select")]

    validate_source_options(declarations, {"sort_by": "relevance"}, "adzuna")
    with pytest.raises(InvalidSourceFilterError, match="must be one of"):
        validate_source_options(declarations, {"sort_by": "Relevance"}, "adzuna")


def test_multiselect_rejects_oversized_lists() -> None:
    declarations = [decl("company_ids", "multiselect")]

    with pytest.raises(InvalidSourceFilterError, match="at most 50"):
        validate_source_options(
            declarations, {"company_ids": [f"id-{i}" for i in range(51)]}, "adzuna"
        )


def test_options_only_spec_counts_as_content() -> None:
    assert SourceQuerySpec(options={"title_only": True}).has_content() is True
    assert SourceQuerySpec().has_content() is False
