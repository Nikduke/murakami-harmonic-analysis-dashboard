"""Description-based saved case selection rules."""

from __future__ import annotations

import json
import re
import unicodedata
import uuid
from collections.abc import Mapping, Sequence
from typing import Any


MAX_NAME_LENGTH = 120
MAX_TERMS_PER_BLOCK = 20
MAX_TERM_LENGTH = 200
MAX_LIBRARY_BYTES = 1024 * 1024
LIBRARY_SCHEMA_VERSION = 1
RULE_BLOCKS = ("all", "any", "exclude")

_UNIT_154_RE = re.compile(r"(?<!\w)154(?:[\W_]*?)k(?:[\W_]*?)v(?!\w)")
_WORD_RE = re.compile(r"[^\W_]+", re.UNICODE)
_TOKEN_VARIANTS = {"filters": "filter", "strings": "string"}
_RULE_KEYS = {"id", "name", "all", "any", "exclude"}
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-"
    r"[89aAbB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$"
)


def normalised_tokens(text: str) -> tuple[str, ...]:
    """Tokenise description text with the explicitly supported text variants."""
    folded = unicodedata.normalize("NFKC", str(text)).casefold()
    folded = _UNIT_154_RE.sub("154kv", folded)
    return tuple(_TOKEN_VARIANTS.get(token, token) for token in _WORD_RE.findall(folded))


def phrase_matches(description: str, term: str) -> bool:
    """Return whether a complete ordered phrase occurs in a description."""
    phrase = normalised_tokens(term)
    description_tokens = normalised_tokens(description)
    if not phrase or len(phrase) > len(description_tokens):
        return False
    width = len(phrase)
    return any(
        description_tokens[start : start + width] == phrase
        for start in range(len(description_tokens) - width + 1)
    )


def rule_matches_description(description: str, rule: Mapping[str, Any]) -> bool:
    """Apply ALL, ANY and EXCLUDE blocks joined with AND."""
    all_terms = rule.get("all", [])
    any_terms = rule.get("any", [])
    exclude_terms = rule.get("exclude", [])
    return (
        all(not term or phrase_matches(description, term) for term in all_terms)
        and (not any_terms or any(phrase_matches(description, term) for term in any_terms))
        and not any(phrase_matches(description, term) for term in exclude_terms)
    )


def matching_case_codes(
    eligible_case_codes: Sequence[str],
    description_by_case: Mapping[str, str],
    rule: Mapping[str, Any],
) -> tuple[list[str], int]:
    """Match only mapped descriptions, preserving the eligible-code order.

    The second return value counts eligible result codes that have no usable
    mapped description. They are never matched by their code or group name.
    """
    matched: list[str] = []
    missing_description_count = 0
    for raw_code in eligible_case_codes:
        code = str(raw_code)
        description = description_by_case.get(code)
        if description is None or not str(description).strip():
            missing_description_count += 1
            continue
        if rule_matches_description(str(description), rule):
            matched.append(code)
    return matched, missing_description_count


def rule_expression(rule: Mapping[str, Any]) -> str:
    """Render the supported rule precedence as an explicit readable expression."""
    clauses: list[str] = []
    all_terms = rule.get("all", [])
    any_terms = rule.get("any", [])
    exclude_terms = rule.get("exclude", [])

    if all_terms:
        clauses.extend(f"contains({json.dumps(term, ensure_ascii=False)})" for term in all_terms)
    if any_terms:
        alternatives = " OR ".join(
            f"contains({json.dumps(term, ensure_ascii=False)})" for term in any_terms
        )
        clauses.append(f"({alternatives})")
    if exclude_terms:
        exclusions = " OR ".join(
            f"contains({json.dumps(term, ensure_ascii=False)})" for term in exclude_terms
        )
        clauses.append(f"NOT ({exclusions})")
    return " AND ".join(clauses) if clauses else "No conditions entered"


def rule_summary(rule: Mapping[str, Any], max_length: int = 180) -> str:
    """Build a compact summary suitable for the saved-selection list."""
    parts = []
    for block, label, separator in (
        ("all", "ALL", " AND "),
        ("any", "ANY", " OR "),
        ("exclude", "NOT", " OR "),
    ):
        terms = rule.get(block, [])
        if terms:
            parts.append(f"{label}: {separator.join(terms)}")
    summary = " · ".join(parts) or "No conditions"
    return summary if len(summary) <= max_length else summary[: max_length - 1].rstrip() + "…"


def suggested_rule_name(
    all_terms: Sequence[str],
    any_terms: Sequence[str],
    exclude_terms: Sequence[str],
    existing_rules: Sequence[Mapping[str, Any]] = (),
    *,
    exclude_id: str | None = None,
) -> str:
    """Build a readable, unique rule name from its description conditions."""
    name_parts = []
    if all_terms:
        name_parts.append(" + ".join(str(term).strip() for term in all_terms))
    if any_terms:
        name_parts.append(" or ".join(str(term).strip() for term in any_terms))
    if exclude_terms:
        name_parts.append(
            "excluding " + " or ".join(str(term).strip() for term in exclude_terms)
        )
    base_name = " — ".join(part for part in name_parts if part) or "Custom selection"
    base_name = " ".join(base_name.split())

    existing_names = {
        str(rule.get("name", "")).strip().casefold()
        for rule in existing_rules
        if str(rule.get("id")) != exclude_id
    }

    def fit(candidate: str) -> str:
        if len(candidate) <= MAX_NAME_LENGTH:
            return candidate
        return candidate[: MAX_NAME_LENGTH - 1].rstrip() + "…"

    candidate = fit(base_name)
    suffix_index = 2
    while candidate.casefold() in existing_names:
        suffix = f" ({suffix_index})"
        candidate = fit(base_name[: MAX_NAME_LENGTH - len(suffix)].rstrip()) + suffix
        suffix_index += 1
    return candidate


def _normalise_terms(value: object, field_name: str) -> list[str]:
    if not isinstance(value, list):
        raise ValueError(f"`{field_name}` must be an array of text phrases.")
    if len(value) > MAX_TERMS_PER_BLOCK:
        raise ValueError(
            f"`{field_name}` can contain at most {MAX_TERMS_PER_BLOCK} phrases."
        )
    terms: list[str] = []
    seen: set[tuple[str, ...]] = set()
    for position, raw_term in enumerate(value, start=1):
        if not isinstance(raw_term, str):
            raise ValueError(f"Phrase {position} in `{field_name}` must be text.")
        term = raw_term.strip()
        if not term:
            raise ValueError(f"`{field_name}` cannot contain a blank phrase.")
        if len(term) > MAX_TERM_LENGTH:
            raise ValueError(
                f"Phrases in `{field_name}` must be {MAX_TERM_LENGTH} characters or fewer."
            )
        tokens = normalised_tokens(term)
        if not tokens:
            raise ValueError(f"Phrase {position} in `{field_name}` must contain a word or number.")
        if tokens in seen:
            raise ValueError(f"`{field_name}` contains a duplicate phrase: {term!r}.")
        seen.add(tokens)
        terms.append(term)
    return terms


def validate_rule(
    raw_rule: Mapping[str, Any],
    existing_rules: Sequence[Mapping[str, Any]] = (),
    *,
    exclude_id: str | None = None,
) -> dict[str, Any]:
    """Validate and normalize one saved rule, raising ValueError on invalid input."""
    if not isinstance(raw_rule, Mapping):
        raise ValueError("Each saved selection must be a JSON object.")
    if set(raw_rule) != _RULE_KEYS:
        raise ValueError("A saved selection must contain id, name, all, any and exclude fields.")

    identifier = raw_rule["id"]
    if not isinstance(identifier, str) or not _UUID_RE.fullmatch(identifier):
        raise ValueError("Each selection ID must be a valid UUID.")
    identifier = str(uuid.UUID(identifier))

    name_value = raw_rule["name"]
    if not isinstance(name_value, str):
        raise ValueError("Selection names must be text.")
    name = name_value.strip()
    if not name:
        raise ValueError("Enter a name for this selection.")
    if len(name) > MAX_NAME_LENGTH:
        raise ValueError(f"Selection names must be {MAX_NAME_LENGTH} characters or fewer.")

    normalized = {
        "id": identifier,
        "name": name,
        "all": _normalise_terms(raw_rule["all"], "Must contain ALL"),
        "any": _normalise_terms(raw_rule["any"], "Must contain ANY"),
        "exclude": _normalise_terms(raw_rule["exclude"], "Must NOT contain"),
    }
    if not any(normalized[block] for block in RULE_BLOCKS):
        raise ValueError("Add at least one phrase; an empty rule would select every case.")

    id_conflict = identifier in {
        str(rule.get("id")) for rule in existing_rules if str(rule.get("id")) != exclude_id
    }
    if id_conflict:
        raise ValueError("This selection ID already exists in the current library.")
    name_key = name.casefold()
    if any(
        str(rule.get("name", "")).strip().casefold() == name_key
        and str(rule.get("id")) != exclude_id
        for rule in existing_rules
    ):
        raise ValueError("A selection with this name already exists. Names ignore case and outer spaces.")
    return normalized


def new_rule(
    name: str,
    all_terms: list[str],
    any_terms: list[str],
    exclude_terms: list[str],
    existing_rules: Sequence[Mapping[str, Any]] = (),
    *,
    identifier: str | None = None,
    exclude_id: str | None = None,
) -> dict[str, Any]:
    """Create a validated rule with a stable unique ID."""
    name = name.strip() or suggested_rule_name(
        all_terms,
        any_terms,
        exclude_terms,
        existing_rules,
        exclude_id=exclude_id,
    )
    candidate = {
        "id": identifier or str(uuid.uuid4()),
        "name": name,
        "all": all_terms,
        "any": any_terms,
        "exclude": exclude_terms,
    }
    return validate_rule(candidate, existing_rules, exclude_id=exclude_id)


def validate_library(rules: object) -> list[dict[str, Any]]:
    """Validate a complete in-memory rule library, preserving rule order."""
    if not isinstance(rules, list):
        raise ValueError("Saved selections must be a list.")
    validated: list[dict[str, Any]] = []
    for raw_rule in rules:
        validated.append(validate_rule(raw_rule, validated))
    return validated


def serialise_library(rules: object) -> str:
    """Return a versioned, validated JSON representation of saved selections."""
    document = {
        "schema_version": LIBRARY_SCHEMA_VERSION,
        "selections": validate_library(rules),
    }
    return json.dumps(document, ensure_ascii=False, indent=2) + "\n"


def parse_library(payload: bytes | str) -> list[dict[str, Any]]:
    """Parse and validate an exported selection library without mutating state."""
    if isinstance(payload, str):
        encoded = payload.encode("utf-8")
    elif isinstance(payload, bytes):
        encoded = payload
    else:
        raise ValueError("The selections file must be UTF-8 JSON text.")

    if len(encoded) > MAX_LIBRARY_BYTES:
        raise ValueError("The selections file is larger than the 1 MB limit.")

    try:
        text = encoded.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ValueError("The selections file must use UTF-8 encoding.") from exc

    try:
        document = json.loads(text)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("The selections file is not valid JSON.") from exc

    if not isinstance(document, Mapping) or set(document) != {
        "schema_version",
        "selections",
    }:
        raise ValueError(
            "The file must contain only `schema_version` and `selections`."
        )
    if type(document["schema_version"]) is not int or document[
        "schema_version"
    ] != LIBRARY_SCHEMA_VERSION:
        raise ValueError(
            f"Unsupported selections file version; expected {LIBRARY_SCHEMA_VERSION}."
        )
    return validate_library(document["selections"])
