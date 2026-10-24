"""Streamlit controls for saved description-based case selections."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import streamlit as st

from custom_selections import (
    matching_case_codes,
    new_rule,
    parse_library,
    rule_expression,
    rule_summary,
    serialise_library,
    suggested_rule_name,
    validate_library,
)


LIBRARY_KEY = "custom_selections::library_v1"
ACTIVE_RULE_KEY = "custom_selections::active_rule_id"
EDITOR_OPEN_KEY = "custom_selections::editor_open"
EDITOR_MODE_KEY = "custom_selections::editor_mode"
EDITOR_RULE_ID_KEY = "custom_selections::editor_rule_id"
DELETE_RULE_ID_KEY = "custom_selections::delete_rule_id"
CASE_CONTEXT_KEY = "custom_selections::case_context"
SAVED_SELECTION_RADIO_GENERATION_KEY = "custom_selections::saved_radio_generation"
SAVED_SELECTION_RADIO_KEY_PREFIX = "custom_selections::saved_radio"
IMPORT_GENERATION_KEY = "custom_selections::import_generation"
IMPORT_STATUS_KEY = "custom_selections::import_status"


@dataclass(frozen=True)
class CustomSelectionView:
    case_codes: list[str]
    active_rule: dict[str, Any] | None
    missing_description_count: int


def custom_case_widget_key(dataset_name: str, location: str) -> str:
    return f"custom-cases::{dataset_name}::{location}"


def custom_case_selection_key(dataset_name: str, location: str) -> str:
    return f"custom-case-selection::{dataset_name}::{location}"


def initialize_custom_selection_state() -> None:
    st.session_state.setdefault(LIBRARY_KEY, [])
    st.session_state.setdefault(ACTIVE_RULE_KEY, None)
    st.session_state.setdefault(EDITOR_OPEN_KEY, False)
    st.session_state.setdefault(EDITOR_MODE_KEY, None)
    st.session_state.setdefault(EDITOR_RULE_ID_KEY, None)
    st.session_state.setdefault(DELETE_RULE_ID_KEY, None)
    st.session_state.setdefault(CASE_CONTEXT_KEY, None)
    st.session_state.setdefault(SAVED_SELECTION_RADIO_GENERATION_KEY, 0)
    st.session_state.setdefault(IMPORT_GENERATION_KEY, 0)
    st.session_state.setdefault(IMPORT_STATUS_KEY, None)


def _clear_import_status() -> None:
    st.session_state[IMPORT_STATUS_KEY] = None


def saved_selection_radio_key() -> str:
    return (
        f"{SAVED_SELECTION_RADIO_KEY_PREFIX}::"
        f"{st.session_state[SAVED_SELECTION_RADIO_GENERATION_KEY]}"
    )


def advance_saved_selection_radio_generation() -> None:
    """Give a changed library a fresh saved-rule radio state key."""
    st.session_state[SAVED_SELECTION_RADIO_GENERATION_KEY] += 1


def _set_saved_selection_radio(active_rule_id: str | None) -> None:
    st.session_state[saved_selection_radio_key()] = active_rule_id


def abandon_custom_selection_editor() -> None:
    """Close an in-progress draft without changing saved or active rules."""
    st.session_state[EDITOR_OPEN_KEY] = False
    st.session_state[EDITOR_MODE_KEY] = None
    st.session_state[EDITOR_RULE_ID_KEY] = None


def _set_case_state(
    widget_key: str,
    selection_key: str,
    case_codes: list[str],
) -> None:
    st.session_state[widget_key] = case_codes.copy()
    st.session_state[selection_key] = case_codes.copy()


def _set_editor_draft(rule: Mapping[str, Any] | None, mode: str) -> None:
    st.session_state[EDITOR_OPEN_KEY] = True
    st.session_state[EDITOR_MODE_KEY] = mode
    st.session_state[EDITOR_RULE_ID_KEY] = rule.get("id") if rule else None
    st.session_state["custom_editor_name"] = rule.get("name", "") if rule else ""
    st.session_state["custom_editor_all"] = list(rule.get("all", [])) if rule else []
    st.session_state["custom_editor_any"] = list(rule.get("any", [])) if rule else []
    st.session_state["custom_editor_exclude"] = (
        list(rule.get("exclude", [])) if rule else []
    )


def _render_rule_editor(
    rules: list[dict[str, Any]],
    eligible_case_codes: list[str],
    description_by_case: Mapping[str, str],
    *,
    dataset_name: str,
    location: str,
) -> None:
    mode = st.session_state.get(EDITOR_MODE_KEY)
    rule_id = st.session_state.get(EDITOR_RULE_ID_KEY)
    existing = next((rule for rule in rules if rule["id"] == rule_id), None)
    if mode == "edit" and existing is None:
        abandon_custom_selection_editor()
        return

    st.subheader("Edit selection" if mode == "edit" else "Create selection")
    name = st.text_input(
        "Name (optional)",
        key="custom_editor_name",
        max_chars=120,
        help="Leave blank to create a readable name from the conditions below.",
    )
    st.caption(
        "A case must pass every non-empty rule. "
        "Entries are matched as phrases in the description."
    )
    all_col, any_col, exclude_col = st.columns(3, gap="small")
    with all_col:
        all_terms = st.multiselect(
            "Must contain ALL",
            options=[],
            key="custom_editor_all",
            accept_new_options=True,
            placeholder="Type a phrase and press Enter",
        )
        st.caption("Every entered phrase must match.")
    with any_col:
        any_terms = st.multiselect(
            "Must contain ANY",
            options=[],
            key="custom_editor_any",
            accept_new_options=True,
            placeholder="Add alternative phrases",
        )
        st.caption("At least one must match; leave empty to skip.")
    with exclude_col:
        exclude_terms = st.multiselect(
            "Must NOT contain",
            options=[],
            key="custom_editor_exclude",
            accept_new_options=True,
            placeholder="Add phrases to exclude",
        )
        st.caption("Any matching phrase excludes the case.")

    draft = {"all": all_terms, "any": any_terms, "exclude": exclude_terms}
    st.markdown("**Resulting rule**")
    st.code(rule_expression(draft), language=None)
    if not name.strip() and any(draft.values()):
        st.caption(
            "Saved as: "
            + suggested_rule_name(
                list(all_terms), list(any_terms), list(exclude_terms), rules,
                exclude_id=rule_id if mode == "edit" else None,
            )
        )
    preview, missing_description_count = matching_case_codes(
        eligible_case_codes, description_by_case, draft
    )
    st.write(f"**Matched cases:** {len(preview)} of {len(eligible_case_codes)}")
    if missing_description_count:
        st.caption(
            f"{missing_description_count} result case(s) have no mapped description "
            "and cannot match this rule."
        )
    if not any(draft.values()):
        st.caption("Add at least one phrase before saving; a blank rule would match all cases.")

    with st.container(horizontal=True):
        save_clicked = st.button(
            "Save selection",
            key="custom_save_selection",
            type="primary",
            icon=":material/save:",
        )
        cancel_clicked = st.button(
            "Cancel",
            key="custom_cancel_editor",
            type="secondary",
        )
    if cancel_clicked:
        abandon_custom_selection_editor()
        st.rerun()
    if not save_clicked:
        return

    try:
        saved_rule = new_rule(
            name,
            list(all_terms),
            list(any_terms),
            list(exclude_terms),
            rules,
            identifier=rule_id if mode == "edit" else None,
            exclude_id=rule_id if mode == "edit" else None,
        )
    except ValueError as exc:
        st.error(str(exc))
        return

    updated_rules = rules.copy()
    if mode == "edit":
        index = next(index for index, rule in enumerate(updated_rules) if rule["id"] == rule_id)
        updated_rules[index] = saved_rule
    else:
        updated_rules.append(saved_rule)
    st.session_state[LIBRARY_KEY] = updated_rules
    st.session_state[ACTIVE_RULE_KEY] = saved_rule["id"]
    advance_saved_selection_radio_generation()
    _set_saved_selection_radio(saved_rule["id"])
    matches, _ = matching_case_codes(
        eligible_case_codes, description_by_case, saved_rule
    )
    case_key = custom_case_widget_key(dataset_name, location)
    selection_key = custom_case_selection_key(dataset_name, location)
    _set_case_state(case_key, selection_key, matches)
    st.session_state[CASE_CONTEXT_KEY] = (
        (dataset_name, location),
        saved_rule["id"],
        tuple(eligible_case_codes),
        tuple(matches),
    )
    abandon_custom_selection_editor()
    st.rerun()


def render_custom_selection_manager(
    eligible_case_codes: list[str],
    description_by_case: Mapping[str, str],
    *,
    dataset_name: str,
    location: str,
) -> CustomSelectionView:
    """Render the rule library and return the cases allowed in the existing plot UI."""
    initialize_custom_selection_state()
    try:
        rules = validate_library(st.session_state[LIBRARY_KEY])
    except ValueError as exc:
        st.error(f"The current selection library is invalid: {exc}")
        rules = []
        st.session_state[LIBRARY_KEY] = []

    context = (dataset_name, location)
    case_key = custom_case_widget_key(dataset_name, location)
    selection_key = custom_case_selection_key(dataset_name, location)
    active_rule_id = st.session_state.get(ACTIVE_RULE_KEY)
    active_rule = next((rule for rule in rules if rule["id"] == active_rule_id), None)
    if active_rule_id is not None and active_rule is None:
        st.session_state[ACTIVE_RULE_KEY] = None
        active_rule_id = None

    rule_matches: dict[str, list[str]] = {}
    missing_description_count = 0
    for rule in rules:
        matches, missing_count = matching_case_codes(
            eligible_case_codes, description_by_case, rule
        )
        rule_matches[rule["id"]] = matches
        missing_description_count = max(missing_description_count, missing_count)

    radio_key = saved_selection_radio_key()
    valid_rule_ids = {rule["id"] for rule in rules}
    if radio_key not in st.session_state:
        st.session_state[radio_key] = active_rule_id
    selected_rule_id = st.session_state[radio_key]
    if selected_rule_id not in valid_rule_ids:
        selected_rule_id = None
        st.session_state[radio_key] = None
    if selected_rule_id != active_rule_id:
        st.session_state[ACTIVE_RULE_KEY] = selected_rule_id
        st.session_state[DELETE_RULE_ID_KEY] = None
        if selected_rule_id is not None:
            abandon_custom_selection_editor()
        active_rule_id = selected_rule_id
        active_rule = next(
            (rule for rule in rules if rule["id"] == active_rule_id), None
        )

    allowed_case_codes = (
        rule_matches.get(active_rule_id, [])
        if active_rule is not None
        else eligible_case_codes.copy()
    )
    context_signature = (
        context,
        active_rule_id,
        tuple(eligible_case_codes),
        tuple(allowed_case_codes),
    )
    previous_context = st.session_state.get(CASE_CONTEXT_KEY)
    if active_rule is not None and previous_context != context_signature:
        _set_case_state(case_key, selection_key, allowed_case_codes)
    elif active_rule is None:
        if case_key not in st.session_state:
            initial = st.session_state.get(selection_key, eligible_case_codes)
            valid = [code for code in eligible_case_codes if code in initial]
            _set_case_state(case_key, selection_key, valid)
        else:
            current = st.session_state.get(case_key, [])
            valid = [code for code in eligible_case_codes if code in current]
            if current != valid:
                _set_case_state(case_key, selection_key, valid)
    st.session_state[CASE_CONTEXT_KEY] = context_signature

    st.subheader("Create or edit selection")
    if not st.session_state[EDITOR_OPEN_KEY]:
        if st.button(
            "New selection",
            key="custom_new_selection",
            icon=":material/add:",
            type="secondary",
        ):
            _set_editor_draft(None, "new")
    if st.session_state[EDITOR_OPEN_KEY]:
        _render_rule_editor(
            rules,
            eligible_case_codes,
            description_by_case,
            dataset_name=dataset_name,
            location=location,
        )

    st.divider()
    st.subheader("Saved selections")
    st.caption(
        f"Choose one rule. Matches use the current dataset and {location}."
    )

    active_rule = next(
        (rule for rule in rules if rule["id"] == st.session_state.get(ACTIVE_RULE_KEY)),
        None,
    )
    active_rule_id = active_rule["id"] if active_rule else None
    if rules:
        rule_by_id = {rule["id"]: rule for rule in rules}
        rule_ids = [rule["id"] for rule in rules]
        st.markdown(
            "<style>"
            ".st-key-custom-saved-selection-list "
            "[data-testid='stRadioGroup'][aria-label='Active rule'] > div, "
            ".st-key-custom-saved-selection-list "
            "label[data-testid='stRadioOption'] { width: 100%; }"
            "</style>",
            unsafe_allow_html=True,
        )
        with st.container(key="custom-saved-selection-list"):
            st.radio(
                "Active rule",
                options=rule_ids,
                index=None,
                format_func=lambda rule_id: (
                    f"**{rule_by_id[rule_id]['name']}** | "
                    f"{rule_summary(rule_by_id[rule_id])} | "
                    f"Matches: {len(rule_matches.get(rule_id, []))} / "
                    f"{len(eligible_case_codes)} cases"
                ),
                key=radio_key,
                width="stretch",
            )
    else:
        st.caption("No saved selections yet. Create one above.")

    active_rule = next(
        (rule for rule in rules if rule["id"] == st.session_state.get(ACTIVE_RULE_KEY)),
        None,
    )
    import_generation = st.session_state[IMPORT_GENERATION_KEY]
    with st.container(horizontal=True, gap="small", vertical_alignment="center"):
        edit_clicked = st.button(
            "Edit",
            key="custom_edit_selection",
            icon=":material/edit:",
            disabled=active_rule is None or st.session_state[EDITOR_OPEN_KEY],
            width="content",
        )
        restore_clicked = st.button(
            "Restore matches",
            key="custom_restore_matches",
            icon=":material/restart_alt:",
            disabled=active_rule is None,
            width="content",
        )
        delete_clicked = st.button(
            "Delete",
            key="custom_delete_selection",
            icon=":material/delete:",
            disabled=active_rule is None or st.session_state[EDITOR_OPEN_KEY],
            width="content",
        )
        clear_clicked = st.button(
            "Clear active",
            key="custom_clear_active_selection",
            icon=":material/close:",
            disabled=active_rule is None,
            width="content",
        )
        st.download_button(
            "Download",
            data=serialise_library(rules),
            file_name="murakami_saved_selections.json",
            mime="application/json",
            key="custom_download_selections",
            help="Download saved selections as a JSON backup.",
            on_click="ignore",
            width="content",
        )
        with st.popover(
            "Upload",
            icon=":material/upload_file:",
            key="custom_upload_popover",
            help="Import a JSON backup and replace this session's saved selections.",
            width="content",
        ):
            uploaded_library = st.file_uploader(
                "Choose a saved-selections JSON file",
                type=["json"],
                max_upload_size=1,
                help="The file must be 1 MB or smaller.",
                key=f"custom_upload_selections::{import_generation}",
                on_change=_clear_import_status,
            )
            import_clicked = st.button(
                "Import selections",
                key=f"custom_import_selections::{import_generation}",
                disabled=uploaded_library is None,
                width="content",
            )
    if edit_clicked and active_rule is not None:
        _set_editor_draft(active_rule, "edit")
        st.rerun()
    if delete_clicked and active_rule is not None:
        st.session_state[DELETE_RULE_ID_KEY] = active_rule["id"]
        abandon_custom_selection_editor()
        st.rerun()
    if restore_clicked and active_rule is not None:
        matches = rule_matches[active_rule["id"]]
        _set_case_state(case_key, selection_key, matches)
        st.session_state[CASE_CONTEXT_KEY] = (
            context,
            active_rule["id"],
            tuple(eligible_case_codes),
            tuple(matches),
        )
        st.rerun()
    if clear_clicked and active_rule is not None:
        st.session_state[ACTIVE_RULE_KEY] = None
        st.session_state[DELETE_RULE_ID_KEY] = None
        abandon_custom_selection_editor()
        _set_case_state(case_key, selection_key, eligible_case_codes)
        st.session_state[CASE_CONTEXT_KEY] = (
            context,
            None,
            tuple(eligible_case_codes),
            tuple(eligible_case_codes),
        )
        advance_saved_selection_radio_generation()
        st.rerun()

    if import_clicked and uploaded_library is not None:
        try:
            imported_rules = parse_library(uploaded_library.getvalue())
        except ValueError as exc:
            st.session_state[IMPORT_STATUS_KEY] = ("error", str(exc))
        else:
            st.session_state[LIBRARY_KEY] = imported_rules
            st.session_state[ACTIVE_RULE_KEY] = None
            st.session_state[DELETE_RULE_ID_KEY] = None
            abandon_custom_selection_editor()
            _set_case_state(case_key, selection_key, eligible_case_codes)
            st.session_state[CASE_CONTEXT_KEY] = (
                context,
                None,
                tuple(eligible_case_codes),
                tuple(eligible_case_codes),
            )
            st.session_state[IMPORT_STATUS_KEY] = (
                "success",
                f"Imported {len(imported_rules)} saved selection(s).",
            )
            st.session_state[IMPORT_GENERATION_KEY] += 1
            advance_saved_selection_radio_generation()
            st.rerun()

    pending_delete_id = st.session_state.get(DELETE_RULE_ID_KEY)
    pending_delete_rule = next(
        (rule for rule in rules if rule["id"] == pending_delete_id), None
    )
    if pending_delete_rule is not None:
        st.warning(
            f"Delete **{pending_delete_rule['name']}** from this session's saved selections?"
        )
        with st.container(horizontal=True):
            confirm_delete = st.button(
                "Confirm delete",
                key="custom_confirm_delete",
                type="primary",
            )
            cancel_delete = st.button("Cancel", key="custom_cancel_delete")
        if cancel_delete:
            st.session_state[DELETE_RULE_ID_KEY] = None
            st.rerun()
        if confirm_delete:
            st.session_state[LIBRARY_KEY] = [
                rule for rule in rules if rule["id"] != pending_delete_id
            ]
            if st.session_state.get(ACTIVE_RULE_KEY) == pending_delete_id:
                st.session_state[ACTIVE_RULE_KEY] = None
                _set_case_state(case_key, selection_key, eligible_case_codes)
                st.session_state[CASE_CONTEXT_KEY] = (
                    context,
                    None,
                    tuple(eligible_case_codes),
                    tuple(eligible_case_codes),
                )
            st.session_state[DELETE_RULE_ID_KEY] = None
            advance_saved_selection_radio_generation()
            st.rerun()

    import_status = st.session_state.get(IMPORT_STATUS_KEY)
    if import_status:
        status_kind, status_message = import_status
        if status_kind == "success":
            st.success(status_message)
        else:
            st.error(f"Could not import selections: {status_message}")

    if missing_description_count:
        st.caption(
            f"{missing_description_count} result case(s) at this location have no mapped "
            "description; custom rules skip them."
        )
    if not description_by_case:
        st.info(
            "Load a `Cases_description*.xlsx` mapping workbook to match case descriptions."
        )

    return CustomSelectionView(
        case_codes=allowed_case_codes,
        active_rule=active_rule,
        missing_description_count=missing_description_count,
    )
