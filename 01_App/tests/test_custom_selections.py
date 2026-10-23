import json

import pytest

from custom_selections import (
    LIBRARY_SCHEMA_VERSION,
    MAX_LIBRARY_BYTES,
    matching_case_codes,
    new_rule,
    normalised_tokens,
    parse_library,
    phrase_matches,
    rule_expression,
    rule_matches_description,
    serialise_library,
    suggested_rule_name,
    validate_library,
)


def _rule(*, all=(), any=(), exclude=()):
    return {"all": list(all), "any": list(any), "exclude": list(exclude)}


def test_all_block_requires_every_phrase_and_any_block_groups_alternatives():
    strict = _rule(all=["5 strings", "no 154kV Filter"])
    assert rule_matches_description(
        "5 strings (J, K, F, E & D), no 154 kV Filters", strict
    )
    assert not rule_matches_description("5 strings and no WTGs", strict)
    assert not rule_matches_description("3 strings, no 154 kV Filters", strict)

    alternatives = _rule(
        all=["5 strings"],
        any=["no 154kV Filter", "no WTGs"],
    )
    assert rule_matches_description("5 strings; with 154 kV Filters and no WTGs", alternatives)
    assert rule_matches_description("5 strings; no 154 kV Filters and with WTGs", alternatives)
    assert not rule_matches_description("5 strings; with filters and with WTGs", alternatives)


def test_exclusion_is_negated_and_does_not_match_positive_filter_word_alone():
    rule = _rule(all=["5 strings"], exclude=["BB2"])
    assert rule_matches_description("5 strings; TSO_BB1", rule)
    assert not rule_matches_description("5 strings; BB2_66kV", rule)

    filter_rule = _rule(all=["no 154kV Filter"])
    assert phrase_matches("no 154 kV Filters", "no 154kV Filter")
    assert not rule_matches_description("with 154 kV Filters", filter_rule)


def test_units_plural_variants_case_whitespace_and_punctuation_are_normalised():
    assert normalised_tokens("  NO 154-kV   FILTERS ") == (
        "no",
        "154kv",
        "filter",
    )
    assert phrase_matches("No 154 kV Filters", "no 154kV filter")
    assert phrase_matches("5 STRINGS (J, K, F, E & D)", "5 strings, (j k f e d)")
    assert not phrase_matches("15 strings and no filters", "5 strings")


def test_comma_separated_phrase_remains_one_rule_term():
    phrase = "5 strings (J, K, F, E & D)"
    rule = new_rule("Comma phrase", [phrase], [], [])
    assert rule["all"] == [phrase]
    assert phrase_matches("5 strings, J, K, F, E & D", phrase)


def test_optional_blocks_and_negative_only_any_only_rules():
    assert rule_matches_description("contains WTGs", _rule(any=["WTGs"]))
    assert not rule_matches_description("without generators", _rule(any=["WTGs"]))
    assert rule_matches_description("contains WTGs", _rule(exclude=["BB2"]))
    assert not rule_matches_description("BB2 with WTGs", _rule(exclude=["BB2"]))
    assert rule_matches_description("anything", _rule())


def test_mapping_filter_preserves_distinct_codes_and_skips_missing_descriptions():
    rule = _rule(all=["5 strings"])
    descriptions = {
        "A1": "5 strings and no WTGs",
        "A2": "5 strings and no WTGs",
        "A3": "15 strings and no WTGs",
        "A4": "",
    }
    matches, missing = matching_case_codes(
        ["A1", "A2", "A3", "A4", "unmapped"], descriptions, rule
    )
    assert matches == ["A1", "A2"]
    assert missing == 2


def test_rule_validation_generates_blank_names_and_rejects_empty_rules_or_duplicates():
    with pytest.raises(ValueError, match="at least one phrase"):
        new_rule("Empty", [], [], [])

    generated = new_rule("   ", ["5 strings", "no 154kV Filter"], [], [])
    assert generated["name"] == "5 strings + no 154kV Filter"

    first = new_rule("Operating cases", ["WTGs"], [], [])
    with pytest.raises(ValueError, match="already exists"):
        new_rule(" operating CASES ", ["BB1"], [], [], [first])
    with pytest.raises(ValueError, match="duplicate phrase"):
        new_rule("Duplicate terms", ["154kV Filter", "154 kV Filters"], [], [])


def test_generated_rule_names_follow_conditions_and_get_unique_suffixes():
    first = new_rule("", ["5 strings"], ["no filters", "no WTGs"], [])
    second = new_rule("", ["5 strings"], ["no filters", "no WTGs"], [], [first])
    excluded = new_rule("", ["5 strings"], [], ["BB2"])

    assert first["name"] == "5 strings — no filters or no WTGs"
    assert second["name"] == "5 strings — no filters or no WTGs (2)"
    assert excluded["name"] == "5 strings — excluding BB2"
    assert suggested_rule_name([], [], [], [first]) == "Custom selection"


def test_boolean_preview_makes_block_precedence_explicit():
    expression = rule_expression(
        _rule(
            all=["5 strings", "no filter"],
            any=["no WTGs", "no 154kV Filter"],
            exclude=["BB2"],
        )
    )
    assert expression == (
        'contains("5 strings") AND contains("no filter") AND '
        '(contains("no WTGs") OR contains("no 154kV Filter")) AND '
        'NOT (contains("BB2"))'
    )


def test_in_memory_library_rejects_duplicate_ids_and_names():
    first = new_rule("First", ["WTGs"], [], [])
    duplicate_id = [{**first}, {**first, "name": "Second"}]
    with pytest.raises(ValueError, match="ID already exists"):
        validate_library(duplicate_id)

    second = new_rule("Second", ["BB2"], [], [], [first])
    with pytest.raises(ValueError, match="already exists"):
        validate_library([first, {**second, "name": " first "}])


def test_json_library_round_trip_preserves_rule_order_ids_and_unicode():
    first = new_rule("5 strings — filter", ["5 strings"], ["no filtre"], [])
    second = new_rule("Excluding BB2", [], ["no WTGs"], ["BB2"], [first])

    exported = serialise_library([first, second])
    document = json.loads(exported)

    assert document["schema_version"] == LIBRARY_SCHEMA_VERSION
    assert parse_library(exported.encode("utf-8")) == [first, second]


@pytest.mark.parametrize(
    "payload, message",
    [
        (b"{not-json", "not valid JSON"),
        (b"\xff", "UTF-8"),
        ('{"schema_version": 2, "selections": []}', "Unsupported"),
        ('{"schema_version": 1, "selections": {}, "extra": true}', "only"),
        ('{"schema_version": 1, "selections": [{}]}', "selection must contain"),
    ],
)
def test_json_library_rejects_malformed_or_unsupported_files(payload, message):
    with pytest.raises(ValueError, match=message):
        parse_library(payload)


def test_json_library_rejects_duplicate_rules_and_oversized_files():
    rule = new_rule("First", ["WTGs"], [], [])
    document = json.loads(serialise_library([rule]))
    document["selections"].append({**rule, "name": "Second"})
    with pytest.raises(ValueError, match="ID already exists"):
        parse_library(json.dumps(document))

    with pytest.raises(ValueError, match="1 MB"):
        parse_library(b" " * (MAX_LIBRARY_BYTES + 1))
