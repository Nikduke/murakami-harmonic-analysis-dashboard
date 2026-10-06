"""Harmonic Analysis Dashboard."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
import json
from pathlib import Path

import pandas as pd
import streamlit as st

from chart_export import ChartExportItem, build_chart_archive, slug_name
from data_loader import (
    UploadExpansion,
    UploadedWorkbook,
    WorkbookSource,
    discover_input_files,
    expand_uploaded_files,
    load_limits,
    load_mapping,
    load_result_workbook,
    matched_conditions,
    merge_uploaded_workbooks,
)
from plotting import (
    CASE_COLORS,
    build_group_data,
    build_harmonic_figure,
    build_thd_data,
    build_thd_figure,
)
from validation import KNOWN_GROUPS, ValidationReport, validate_limits, validate_mapping, validate_result


APP_DIR = Path(__file__).resolve().parent
INPUT_DIR = APP_DIR / "Input_files"
APP_ICON_PATH = APP_DIR / "assets" / "mpe_app_icon.png"
APP_LOGO_PATH = APP_DIR / "assets" / "mpe_app_wordmark.png"
APP_NAME = "Harmonic Analysis Dashboard"
UPLOAD_WIDGET_KEY_VERSION = 3
SELECT_ALL_OPTION = "__dashboard_action_select_all__"
CLEAR_ALL_OPTION = "__dashboard_action_clear_all__"
AUTO_Y_LIMITS_KEY = "auto_y_limits_v4"
SHOW_ALL_HARMONIC_NUMBERS_KEY = "show_all_harmonic_numbers_v3"
SPECTRUM_Y_CAP_KEY = "spectrum_y_max_value"
THD_Y_CAP_KEY = "thd_y_max_value"
SPECTRUM_Y_INPUT_KEY = "spectrum_y_max_input"
THD_Y_INPUT_KEY = "thd_y_max_input"
DOWNLOAD_AUTO_Y_LIMITS_KEY = "download_auto_y_limits_v2"
DOWNLOAD_SPECTRUM_Y_CAP_KEY = "download_spectrum_y_max_value"
DOWNLOAD_THD_Y_CAP_KEY = "download_thd_y_max_value"
DOWNLOAD_SPECTRUM_Y_INPUT_KEY = "download_spectrum_y_max_input"
DOWNLOAD_THD_Y_INPUT_KEY = "download_thd_y_max_input"

st.set_page_config(
    page_title=APP_NAME,
    page_icon=str(APP_ICON_PATH),
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(show_spinner=False, max_entries=16)
def _cached_mapping(path: str, modified_ns: int, size: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    del modified_ns, size
    return load_mapping(Path(path))


@st.cache_data(show_spinner=False, max_entries=16)
def _cached_results(path: str, modified_ns: int, size: int) -> dict[str, pd.DataFrame]:
    del modified_ns, size
    return load_result_workbook(Path(path))


@st.cache_data(show_spinner=False, max_entries=16)
def _cached_limits(path: str, modified_ns: int, size: int) -> pd.DataFrame:
    del modified_ns, size
    return load_limits(Path(path))


@st.cache_data(show_spinner=False, max_entries=16)
def _cached_uploaded_workbook(
    loader_name: str, filename: str, content: bytes
):
    del filename
    if loader_name == "load_mapping":
        return load_mapping(content)
    if loader_name == "load_result_workbook":
        return load_result_workbook(content)
    if loader_name == "load_limits":
        return load_limits(content)
    raise ValueError(f"Unknown workbook loader: {loader_name}")


@st.cache_data(show_spinner=False, max_entries=4)
def _cached_upload_expansion(
    uploads: tuple[UploadedWorkbook, ...],
) -> UploadExpansion:
    return expand_uploaded_files(list(uploads))


def _load_cached(loader, source: WorkbookSource):
    if isinstance(source, UploadedWorkbook):
        loader_name = {
            "_cached_mapping": "load_mapping",
            "_cached_results": "load_result_workbook",
            "_cached_limits": "load_limits",
        }[loader.__name__]
        return _cached_uploaded_workbook(loader_name, source.name, source.content)
    stat = source.stat()
    return loader(str(source), stat.st_mtime_ns, stat.st_size)


def _reset_analysis_selections() -> None:
    fixed_keys = {
        "result_dataset",
        "result_location",
        "limit_source",
        "show_chart_download_dialog",
    }
    for key in list(st.session_state):
        if key in fixed_keys or key.startswith(
            (
                "cases::",
                "case-selection::",
                "limit_series::",
                "limit_series_selection::",
                "limit_series_active::",
                "limit_series_explicit::",
                "download_",
            )
        ):
            del st.session_state[key]
    st.session_state["show_chart_download_dialog"] = False


def _remember_limit_series(
    widget_key: str, selection_key: str, explicit_selection_key: str
) -> None:
    selected_series = st.session_state.get(widget_key)
    if selected_series is not None:
        st.session_state[selection_key] = selected_series
        st.session_state[explicit_selection_key] = True


def _ensure_positive_number_state(
    state_key: str, legacy_key: str, default: float
) -> None:
    if state_key in st.session_state:
        return
    try:
        value = float(st.session_state.get(legacy_key, default))
    except (TypeError, ValueError):
        value = default
    if pd.isna(value) or value <= 0:
        value = default
    st.session_state[state_key] = value


def _display_report(report: ValidationReport) -> None:
    for message in report.errors:
        st.error(message)
    for message in report.warnings:
        st.warning(message)


def _valid_case_codes(cases: pd.DataFrame) -> set[str]:
    return {
        str(value)
        for value in cases["Case number"].tolist()
        if not pd.isna(value) and str(value).strip()
    }


def _report_summary(report: ValidationReport) -> str:
    if report.errors:
        return f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)"
    if report.warnings:
        return f"Ready with {len(report.warnings)} warning(s)"
    return "Valid"


def _max_numeric_value(values: pd.DataFrame | pd.Series) -> float:
    if isinstance(values, pd.DataFrame):
        values = values.drop(columns=["Harmonic Order"], errors="ignore")
    numeric = (
        values.apply(pd.to_numeric, errors="coerce")
        if isinstance(values, pd.DataFrame)
        else pd.to_numeric(values, errors="coerce")
    )
    maximum = numeric.max().max() if isinstance(numeric, pd.DataFrame) else numeric.max()
    return float(maximum) if pd.notna(maximum) else 0.0


def _suggested_y_axis_max(maximum: float) -> float:
    return max(float(maximum) * 1.15, 0.001)


def _y_axis_input_step(value: float) -> float:
    return max(abs(float(value)) * 0.05, 0.0001)


def _handle_case_dropdown_action(
    case_key: str,
    selection_key: str,
    available_cases: list[str],
) -> None:
    selected = st.session_state.get(case_key, [])
    if SELECT_ALL_OPTION in selected:
        selected = available_cases.copy()
    elif CLEAR_ALL_OPTION in selected:
        selected = []
    else:
        selected = [case for case in selected if case in available_cases]
    st.session_state[case_key] = selected
    st.session_state[selection_key] = selected.copy()


def _handle_multiselect_dropdown_action(
    widget_key: str,
    available_options: list[object],
) -> None:
    selected = st.session_state.get(widget_key, [])
    if SELECT_ALL_OPTION in selected:
        st.session_state[widget_key] = available_options.copy()
    elif CLEAR_ALL_OPTION in selected:
        st.session_state[widget_key] = []


def _handle_download_case_selection(
    widget_key: str,
    selection_key: str,
    available_cases: list[str],
) -> None:
    selected = st.session_state.get(widget_key, [])
    if SELECT_ALL_OPTION in selected:
        selected = available_cases.copy()
    elif CLEAR_ALL_OPTION in selected:
        selected = []
    else:
        selected = [case for case in selected if case in available_cases]
    st.session_state[widget_key] = selected
    st.session_state[selection_key] = selected.copy()


def _close_chart_download_dialog() -> None:
    st.session_state["show_chart_download_dialog"] = False


def _export_group_cases(
    result_sheets: dict[str, pd.DataFrame],
    locations: list[str],
    cases: pd.DataFrame,
    has_mapping: bool,
) -> dict[str, list[str]]:
    if not locations:
        return {}
    case_sets = [
        {str(column) for column in result_sheets[location].columns[1:]}
        for location in locations
    ]
    available_case_codes = set.intersection(*case_sets) if case_sets else set()
    if has_mapping:
        groups: dict[str, list[str]] = {}
        for group in KNOWN_GROUPS:
            group_rows = cases.loc[cases["Group"] == group]
            codes = [
                str(code)
                for code in group_rows["Case number"].tolist()
                if str(code).strip() and str(code) in available_case_codes
            ]
            if codes:
                groups[group] = codes
        mapped_codes = _valid_case_codes(cases)
        first_location_codes = [
            str(column) for column in result_sheets[locations[0]].columns[1:]
        ]
        unmapped_codes = [
            code
            for code in first_location_codes
            if code in available_case_codes and code not in mapped_codes
        ]
        if unmapped_codes:
            groups["Unmapped"] = unmapped_codes
        return groups

    first_location_codes = [
        str(column) for column in result_sheets[locations[0]].columns[1:]
    ]
    common_codes = [code for code in first_location_codes if code in available_case_codes]
    return {"Cases": common_codes} if common_codes else {}


def _case_option_label(value: str) -> str:
    if value == SELECT_ALL_OPTION:
        return "Select all"
    if value == CLEAR_ALL_OPTION:
        return "Clear all"
    return value


def _dropdown_option_label(value: object) -> str:
    if value == SELECT_ALL_OPTION:
        return "Select all"
    if value == CLEAR_ALL_OPTION:
        return "Clear all"
    return getattr(value, "name", str(value))


def _result_dataset_option_labels(
    sources: list[WorkbookSource], conditions: pd.DataFrame
) -> dict[str, str]:
    """Show the filename's distinguishing tokens without its shared result prefix."""
    parsed: list[tuple[str, str]] = []
    for source in sources:
        name = source.name
        filename_parts = source.stem.split("_")
        has_shared_prefix = bool(
            filename_parts
            and filename_parts[0].casefold() == "total distortion"
        )
        if has_shared_prefix:
            filename_parts = filename_parts[1:]
        elif len(filename_parts) >= 2 and [
            part.casefold() for part in filename_parts[:2]
        ] == ["total", "distortion"]:
            has_shared_prefix = True
            filename_parts = filename_parts[2:]

        if has_shared_prefix:
            condition_tokens = [part for part in filename_parts if part]
            label = " · ".join(condition_tokens) or "Result workbook"
        else:
            condition_tokens = [token for token, _ in matched_conditions(name, conditions)]
            label = " · ".join(condition_tokens) or name
        parsed.append((name, label))

    labels = dict(parsed)
    duplicate_labels = {
        label for label, count in Counter(labels.values()).items() if count > 1
    }
    for name, _ in parsed:
        if labels[name] in duplicate_labels:
            labels[name] = name
    return labels


def _result_dataset_option_label(value: object, labels: dict[str, str]) -> str:
    if value == SELECT_ALL_OPTION:
        return "Select all"
    if value == CLEAR_ALL_OPTION:
        return "Clear all"
    name = getattr(value, "name", str(value))
    return labels.get(name, name)


def _case_chip_styles(container_key: str, selected_cases: list[str]) -> str:
    """Tint selected case chips with the same palette order used by the plots."""
    rules = []
    for index, _case_code in enumerate(selected_cases):
        color = CASE_COLORS[index % len(CASE_COLORS)]
        channels = tuple(int(color[offset : offset + 2], 16) for offset in (1, 3, 5))
        tint = "#" + "".join(
            f"{round(channel * 0.16 + 255 * 0.84):02X}" for channel in channels
        )
        rules.append(
            f".st-key-{container_key} [data-testid='stMultiSelectTagsContainer'] "
            f"[data-tag-index='{index}'] "
            f"{{ background-color: {tint} !important; border: 1px solid {color} !important; "
            f"color: #273349 !important; }}"
        )
        rules.append(
            f".st-key-{container_key} [data-testid='stMultiSelectTagsContainer'] "
            f"[data-tag-index='{index}'] * "
            f"{{ color: #273349 !important; -webkit-text-fill-color: #273349 !important; }}"
        )
    return f"<style>{''.join(rules)}</style>" if rules else ""


def _uploaded_role(name: str) -> str:
    folded = name.casefold()
    if folded.startswith("cases_description"):
        return "mapping"
    if folded.startswith("limits_"):
        return "limit"
    return "result"


st.session_state.setdefault("uploaded_workbooks", [])
st.session_state.setdefault("uploaded_duplicate_names", [])
st.session_state.setdefault("upload_widget_version", 0)
st.session_state.setdefault("show_chart_download_dialog", False)
local_files = discover_input_files(INPUT_DIR)

st.header(APP_NAME)

with st.sidebar:
    st.image(str(APP_LOGO_PATH), width=210)
    st.header("Analysis setup")
    with st.popover(
        "Add Excel workbooks",
        icon=":material/upload_file:",
        width="stretch",
        help="Upload or remove workbooks for this session.",
    ):
        st.caption(
            "Choose `.xlsx` workbooks, a `.zip` bundle, or both. ZIP members are read "
            "from the archive without extracting files. Workbooks are identified by "
            "their own filenames:\n\n"
            "- `Total distortion` — harmonic results (required)\n"
            "- `Cases_description` — case groups and descriptions (optional)\n"
            "- `Limits_` — harmonic limits (optional)"
        )
        uploaded_widget = st.file_uploader(
            "Choose .xlsx files or .zip bundles",
            type=["xlsx", "zip"],
            accept_multiple_files=True,
            key=(
                f"input_workbooks::v{UPLOAD_WIDGET_KEY_VERSION}::"
                f"{st.session_state['upload_widget_version']}"
            ),
            help=(
                "Upload individual workbooks, one or more ZIP bundles, or combine them. "
                "A ZIP may contain workbooks in folders. Uploads stay in this session; "
                "files on disk are not changed."
            ),
        )
        raw_uploads: list[UploadedWorkbook] = []
        for uploaded_file in uploaded_widget or []:
            filename = Path(uploaded_file.name).name
            raw_uploads.append(
                UploadedWorkbook(
                    name=filename,
                    content=uploaded_file.getvalue(),
                )
            )
        upload_expansion = _cached_upload_expansion(tuple(raw_uploads))
        current_uploads = upload_expansion.workbooks
        if raw_uploads:
            with st.expander("Show selected workbook files", expanded=False):
                if current_uploads:
                    workbook_lines = []
                    for workbook in current_uploads:
                        role = _uploaded_role(workbook.name).capitalize()
                        display_name = workbook.member_path or workbook.name
                        source = (
                            f" · from {workbook.archive_name}"
                            if workbook.archive_name
                            else ""
                        )
                        workbook_lines.append(f"{role} · {display_name}{source}")
                    st.text("\n".join(workbook_lines))
                else:
                    st.caption("No supported `.xlsx` workbooks found in the selected files.")

    previous_uploads = st.session_state["uploaded_workbooks"]
    previous_duplicate_names = st.session_state["uploaded_duplicate_names"]
    if current_uploads != previous_uploads:
        previous_by_name = {workbook.name.casefold(): workbook for workbook in previous_uploads}
        current_by_name = {workbook.name.casefold(): workbook for workbook in current_uploads}
        changed_names = {
            name
            for name in previous_by_name.keys() | current_by_name.keys()
            if previous_by_name.get(name) != current_by_name.get(name)
        }
        local_names = {
            workbook.name.casefold()
            for group in (local_files.mapping, local_files.limits, local_files.results)
            for workbook in group
        }
        selection_may_be_stale = any(
            name.startswith("cases_description")
            or name in local_names
            or (name in previous_by_name and name in current_by_name)
            for name in changed_names
        )
        selection_may_be_stale = selection_may_be_stale or bool(
            previous_duplicate_names or upload_expansion.duplicate_names
        )
        st.session_state["uploaded_workbooks"] = current_uploads
        st.session_state["uploaded_duplicate_names"] = upload_expansion.duplicate_names
        if selection_may_be_stale or (previous_uploads and not current_uploads):
            _reset_analysis_selections()
    elif upload_expansion.duplicate_names != previous_duplicate_names:
        st.session_state["uploaded_duplicate_names"] = upload_expansion.duplicate_names
        _reset_analysis_selections()

    if raw_uploads:
        if current_uploads:
            upload_counts = {role: 0 for role in ("mapping", "limit", "result")}
            for workbook in current_uploads:
                upload_counts[_uploaded_role(workbook.name)] += 1
            role_labels = {"mapping": "mapping", "limit": "limit", "result": "result"}
            upload_summary = " · ".join(
                f"{count} {role_labels[role]}{'s' if count != 1 else ''}"
                for role, count in upload_counts.items()
                if count
            )
            st.caption(f"Uploads: {upload_summary}")
        else:
            st.caption("Uploads: no supported workbooks found")
        if st.button(
            "Clear uploaded files",
            icon=":material/delete_sweep:",
            width="stretch",
        ):
            st.session_state["uploaded_workbooks"] = []
            st.session_state["uploaded_duplicate_names"] = []
            st.session_state["upload_widget_version"] += 1
            _reset_analysis_selections()
            st.cache_data.clear()
            st.rerun()

    if st.button(
        "Reload project workbooks",
        icon=":material/refresh:",
        width="stretch",
        type="tertiary",
        help=(
            "Re-scan the project's default workbooks after replacing them. "
            "Session uploads remain active."
        ),
    ):
        st.cache_data.clear()
        st.rerun()

for message in upload_expansion.archive_errors:
    st.error(message)
for message in upload_expansion.archive_warnings:
    st.warning(message)
if upload_expansion.duplicate_names:
    names = ", ".join(f"`{name}`" for name in upload_expansion.duplicate_names)
    st.error(
        "The uploaded files contain duplicate workbook filenames: "
        f"{names}. Remove or rename duplicates before continuing."
    )
    st.stop()

files = merge_uploaded_workbooks(local_files, st.session_state["uploaded_workbooks"])

if len(files.mapping) > 1:
    st.error(
        "Use at most one `Cases_description*.xlsx` mapping workbook. Found: "
        + ", ".join(path.name for path in files.mapping)
        + "."
    )
    st.stop()

if not files.results:
    st.warning(
        "To start, click **Add Excel workbooks** in the left sidebar and upload a result "
        "workbook or a ZIP bundle containing one:\n\n"
        "- `Total distortion` — harmonic results (required)\n"
        "- `Cases_description` — case groups and descriptions (optional)\n"
        "- `Limits_` — harmonic limits (optional; choose **No limit** if omitted)"
    )
    st.stop()

mapping_report: ValidationReport | None = None
if files.mapping:
    try:
        cases, conditions = _load_cached(_cached_mapping, files.mapping[0])
    except Exception as exc:
        st.error(f"Could not read mapping workbook `{files.mapping[0].name}`: {exc}")
        st.stop()

    mapping_report = validate_mapping(cases, conditions)
    if mapping_report.errors:
        with st.expander("Input data status", expanded=True):
            st.write(f"Mapping workbook: `{files.mapping[0].name}`")
            _display_report(mapping_report)
        st.stop()
else:
    cases = pd.DataFrame(columns=["Case number", "Group", "Description"])
    conditions = pd.DataFrame(columns=["Token", "Description"])

result_dataset_labels = _result_dataset_option_labels(files.results, conditions)
if st.session_state.get("result_dataset") not in files.results:
    st.session_state["result_dataset"] = files.results[0]

with st.sidebar:
    if len(files.results) <= 5:
        selected_dataset = st.radio(
            "Result dataset",
            options=files.results,
            format_func=lambda source: _result_dataset_option_label(
                source, result_dataset_labels
            ),
            key="result_dataset",
        )
    else:
        selected_dataset = st.selectbox(
            "Result dataset",
            options=files.results,
            format_func=lambda source: _result_dataset_option_label(
                source, result_dataset_labels
            ),
            key="result_dataset",
        )
recognized_conditions = matched_conditions(selected_dataset.name, conditions)

try:
    result_sheets = _load_cached(_cached_results, selected_dataset)
except Exception as exc:
    st.error(f"Could not read result workbook `{selected_dataset.name}`: {exc}")
    st.stop()

if not result_sheets:
    st.error(f"Result workbook `{selected_dataset.name}` contains no worksheets.")
    st.stop()

location_options = list(result_sheets)
if st.session_state.get("result_location") not in location_options:
    st.session_state["result_location"] = location_options[0]

mapped_case_codes = _valid_case_codes(cases)
result_reports = {
    sheet_name: validate_result(
        data, mapped_case_codes if files.mapping else None, sheet_name
    )
    for sheet_name, data in result_sheets.items()
}

with st.sidebar:
    if len(location_options) <= 5:
        selected_location = st.radio(
            "Busbar / location",
            options=location_options,
            key="result_location",
        )
    else:
        selected_location = st.selectbox(
            "Busbar / location",
            options=location_options,
            key="result_location",
        )

    selected_limit_file: WorkbookSource | None = None
    limits: pd.DataFrame | None = None
    limit_report: ValidationReport | None = None
    limit_load_error: str | None = None
    if files.limits:
        if len(files.limits) > 1:
            selected_limit_file = st.selectbox(
                "Limit source",
                options=files.limits,
                format_func=lambda path: path.name,
                key="limit_source",
            )
        else:
            selected_limit_file = files.limits[0]
        try:
            limits = _load_cached(_cached_limits, selected_limit_file)
            limit_report = validate_limits(limits, selected_limit_file.name)
        except Exception as exc:
            limit_load_error = str(exc)

    valid_limit_series = (
        list(limits.columns[1:])
        if limits is not None and limit_report is not None and limit_report.is_valid
        else []
    )
    limit_options = ["No limit", *valid_limit_series]
    legacy_limit_widget_key = (
        f"limit_series::{selected_limit_file.name}"
        if selected_limit_file
        else None
    )
    limit_widget_key = (
        f"limit_series::{selected_limit_file.name}::{selected_location}"
        if selected_limit_file
        else "limit_series::no-source"
    )
    limit_selection_key = (
        f"limit_series_selection::{selected_limit_file.name}::{selected_location}"
        if selected_limit_file
        else "limit_series_selection::no-source"
    )
    active_limit_selection_key = (
        f"limit_series_active::{selected_limit_file.name}"
        if selected_limit_file
        else "limit_series_active::no-source"
    )
    explicit_limit_selection_key = (
        f"limit_series_explicit::{selected_limit_file.name}::{selected_location}"
        if selected_limit_file
        else "limit_series_explicit::no-source"
    )
    if legacy_limit_widget_key:
        legacy_limit = st.session_state.pop(legacy_limit_widget_key, None)
        if legacy_limit is not None and limit_selection_key not in st.session_state:
            st.session_state[limit_selection_key] = legacy_limit
            if legacy_limit != "No limit":
                st.session_state[explicit_limit_selection_key] = True
    remembered_limit = st.session_state.get(limit_selection_key)
    if (
        remembered_limit in limit_options
        and remembered_limit != "No limit"
        and explicit_limit_selection_key not in st.session_state
    ):
        # Older sessions auto-saved No limit defaults but only stored other series
        # after the user changed the selector.
        st.session_state[explicit_limit_selection_key] = True
    if (
        st.session_state.get(explicit_limit_selection_key)
        and remembered_limit in limit_options
    ):
        saved_limit = remembered_limit
    else:
        saved_limit = st.session_state.get(active_limit_selection_key, "No limit")
        if saved_limit not in limit_options:
            saved_limit = "No limit"
    if st.session_state.get(limit_widget_key) != saved_limit:
        st.session_state[limit_widget_key] = saved_limit
    limit_selector = st.radio if len(limit_options) <= 5 else st.selectbox
    selected_limit = limit_selector(
        "Limit series",
        options=limit_options,
        help=(
            "A new location starts with the current series. Each location then keeps "
            "its own selection."
        ),
        key=limit_widget_key,
        on_change=_remember_limit_series,
        args=(limit_widget_key, limit_selection_key, explicit_limit_selection_key),
    )
    st.session_state[active_limit_selection_key] = selected_limit
    if not files.limits:
        st.caption("No limit workbook loaded. Upload `Limits_*.xlsx` to add limit series.")
    limit_display = (
        st.radio(
            "Limit display",
            options=["Bars", "Dashes"],
            horizontal=True,
            key="limit_display",
            help="Dashes are short, separate markers at each harmonic order.",
        )
        if selected_limit != "No limit"
        else "Bars"
    )
    if (
        SPECTRUM_Y_CAP_KEY not in st.session_state
        or THD_Y_CAP_KEY not in st.session_state
    ):
        if result_reports[selected_location].is_valid:
            axis_seed_data = build_group_data(
                result_sheets[selected_location],
                [str(column) for column in result_sheets[selected_location].columns[1:]],
                limits=limits if selected_limit != "No limit" else None,
                limit_series=selected_limit if selected_limit != "No limit" else None,
            )
            seed_thd_data, _ = build_thd_data(axis_seed_data, {})
            spectrum_seed = _max_numeric_value(axis_seed_data)
            thd_seed = _max_numeric_value(seed_thd_data["THD (%)"])
        else:
            spectrum_seed = thd_seed = 1.0
        _ensure_positive_number_state(
            SPECTRUM_Y_CAP_KEY,
            "spectrum_y_max",
            _suggested_y_axis_max(spectrum_seed),
        )
        _ensure_positive_number_state(
            THD_Y_CAP_KEY,
            "thd_y_max",
            _suggested_y_axis_max(thd_seed),
        )
    st.divider()
    auto_y_limits = st.checkbox(
        "Auto y-axis limits",
        value=True,
        key=AUTO_Y_LIMITS_KEY,
        help="Use automatic y-axis ranges, or set fixed maxima shared across all charts of each type.",
    )
    if not auto_y_limits:
        st.caption("Values above a fixed maximum are clipped. Spectrum and THD use separate maxima.")
        st.session_state.setdefault(
            SPECTRUM_Y_INPUT_KEY, st.session_state[SPECTRUM_Y_CAP_KEY]
        )
        st.number_input(
            "Spectrum maximum (%)",
            min_value=0.000001,
            step=_y_axis_input_step(st.session_state[SPECTRUM_Y_CAP_KEY]),
            format="%.6g",
            key=SPECTRUM_Y_INPUT_KEY,
        )
        st.session_state[SPECTRUM_Y_CAP_KEY] = st.session_state[
            SPECTRUM_Y_INPUT_KEY
        ]
        st.session_state.setdefault(THD_Y_INPUT_KEY, st.session_state[THD_Y_CAP_KEY])
        st.number_input(
            "THD maximum (%)",
            min_value=0.000001,
            step=_y_axis_input_step(st.session_state[THD_Y_CAP_KEY]),
            format="%.6g",
            key=THD_Y_INPUT_KEY,
        )
        st.session_state[THD_Y_CAP_KEY] = st.session_state[THD_Y_INPUT_KEY]
    show_all_harmonic_numbers = st.checkbox(
        "Show all harmonic numbers",
        value=True,
        key=SHOW_ALL_HARMONIC_NUMBERS_KEY,
        help="Label each harmonic order present in the selected result data.",
    )
    show_group_tabs = (
        st.checkbox(
            "Show groups as tabs",
            value=True,
            key="show_group_tabs",
            help="Turn this off to show each case group one below another.",
        )
        if files.mapping
        else False
    )
    open_chart_download = st.button(
        "Download charts",
        key="open_chart_download",
        icon=":material/download:",
        width="stretch",
        disabled=bool(result_reports[selected_location].errors),
        help="Choose datasets, locations, groups, cases, and limits for a ZIP chart set.",
    )

selected_result = result_sheets[selected_location]
selected_result_report = result_reports[selected_location]

available_case_count = max(0, selected_result.shape[1] - 1)
all_case_codes = [str(code) for code in selected_result.columns[1:]]
mapped_result_case_codes = [
    code for code in all_case_codes if code in mapped_case_codes
]
unmapped_result_case_codes = [
    code for code in all_case_codes if files.mapping and code not in mapped_case_codes
]
order_values = pd.to_numeric(selected_result.iloc[:, 0], errors="coerce").dropna() if selected_result.shape[1] else pd.Series(dtype=float)
order_range = (
    f"{order_values.min():g}–{order_values.max():g}" if not order_values.empty else "Unavailable"
)
selected_limit_for_plot = selected_limit if selected_limit != "No limit" else None

if files.mapping:
    case_summary = (
        f"{available_case_count} result cases | {len(mapped_result_case_codes)} mapped | "
        f"{len(unmapped_result_case_codes)} unmapped"
    )
else:
    case_summary = f"{available_case_count} result cases | no mapping loaded"
st.caption(case_summary)
if unmapped_result_case_codes:
    st.warning(
        f"{len(unmapped_result_case_codes)} result cases have no case-mapping entry. "
        "They remain available under Unmapped and All, identified by their exact result codes."
    )

status_has_errors = (
    any(report.errors for report in result_reports.values())
    or bool(limit_report and limit_report.errors)
    or bool(limit_load_error)
)


def render_data_status() -> None:
    with st.expander("Data validation and sources", expanded=status_has_errors):
        if files.mapping:
            st.write(
                f"**Case mapping:** `{files.mapping[0].name}` · "
                f"{len(mapped_case_codes)} mapping entries"
            )
        else:
            st.write("**Case mapping:** none · cases use result column names")
        st.write(f"**Dataset:** `{selected_dataset.name}` · {len(result_sheets)} location(s)")
        if selected_limit_file:
            st.write(f"**Limit source:** `{selected_limit_file.name}`")
        else:
            st.write("**Limit source:** none found; plots can be viewed without a limit.")

        location_status = []
        for sheet_name, report in result_reports.items():
            frame = result_sheets[sheet_name]
            count = max(0, frame.shape[1] - 1)
            row_count = len(frame)
            location_status.append(
                {
                    "Location": sheet_name,
                    "Cases": count,
                    "Harmonic orders": row_count,
                    "Validation": _report_summary(report),
                }
            )
        st.dataframe(pd.DataFrame(location_status), hide_index=True, width="stretch")

        other_location_errors = [
            (sheet_name, message)
            for sheet_name, report in result_reports.items()
            if sheet_name != selected_location
            for message in report.errors
        ]
        other_location_warnings = [
            (sheet_name, message)
            for sheet_name, report in result_reports.items()
            if sheet_name != selected_location
            for message in report.warnings
        ]
        if selected_result_report.errors:
            st.markdown(f"**{selected_location} issues**")
            for message in selected_result_report.errors:
                st.error(message)
        if other_location_errors:
            st.markdown("**Other location issues**")
            for _, message in other_location_errors:
                st.error(message)
        if other_location_warnings:
            st.markdown("**Other location warnings**")
            for _, message in other_location_warnings:
                st.warning(message)
        if selected_result_report.warnings:
            st.markdown(f"**{selected_location} warnings**")
            for message in selected_result_report.warnings:
                st.warning(message)
        if mapping_report and mapping_report.warnings:
            st.markdown("**Mapping workbook warnings**")
            for message in mapping_report.warnings:
                st.warning(message)
        if limit_report and limit_report.errors:
            st.markdown("**Limit workbook issues**")
            for message in limit_report.errors:
                st.error(message)
        if limit_report and limit_report.warnings:
            for message in limit_report.warnings:
                st.warning(message)
        if limit_load_error:
            st.error(
                f"Could not read limit workbook `{selected_limit_file.name}`: "
                f"{limit_load_error}"
            )

if selected_result_report.errors:
    st.error(f"Plotting is disabled for `{selected_location}` until its result sheet is corrected.")
    render_data_status()
    st.stop()

if selected_limit_for_plot and (limit_report is None or not limit_report.is_valid):
    st.error("The selected limit workbook is invalid. Choose another source or select No limit.")
    render_data_status()
    st.stop()

description_by_case = {
    str(row["Case number"]): str(row["Description"])
    for _, row in cases.iterrows()
    if str(row["Case number"]).strip()
}
result_case_codes = {str(column) for column in selected_result.columns[1:]}

selected_dataset_label = result_dataset_labels[selected_dataset.name]
if recognized_conditions:
    dataset_conditions_text = " | ".join(
        f"{token} - {description}" for token, description in recognized_conditions
    )
else:
    dataset_conditions_text = "Not specified in the file name"
dataset_context = (
    f"**Dataset conditions:** {dataset_conditions_text} | "
    f"Harmonic orders - {order_range}"
)
location_context = f"**Location:** {selected_location}"
limit_context = f"**Limit:** {selected_limit_for_plot or 'None'}"
st.markdown(f"{dataset_context}  \n{location_context}  \n{limit_context}")

if files.mapping:
    case_groups = []
    for group in KNOWN_GROUPS:
        group_rows = cases.loc[cases["Group"] == group]
        group_case_codes = [
            str(code)
            for code in group_rows["Case number"].tolist()
            if str(code).strip() and str(code) in result_case_codes
        ]
        case_groups.append((group, group_rows, group_case_codes))
    if unmapped_result_case_codes:
        unmapped_rows = pd.DataFrame(
            {
                "Case number": unmapped_result_case_codes,
                "Group": ["Unmapped"] * len(unmapped_result_case_codes),
                "Description": ["No mapping entry"] * len(unmapped_result_case_codes),
            }
        )
        case_groups.append(("Unmapped", unmapped_rows, unmapped_result_case_codes))
        all_group_rows = pd.concat([cases, unmapped_rows], ignore_index=True)
    else:
        all_group_rows = cases
    case_groups.append(("All", all_group_rows, all_case_codes))
else:
    case_groups = [
        ("All", cases, all_case_codes)
    ]


@st.dialog(
    "Download chart set",
    width="large",
    on_dismiss=_close_chart_download_dialog,
)
def render_chart_download_dialog() -> None:
    st.session_state.setdefault(
        DOWNLOAD_AUTO_Y_LIMITS_KEY,
        st.session_state.get(AUTO_Y_LIMITS_KEY, True),
    )
    _ensure_positive_number_state(
        DOWNLOAD_SPECTRUM_Y_CAP_KEY,
        "download_spectrum_y_max",
        st.session_state[SPECTRUM_Y_CAP_KEY],
    )
    _ensure_positive_number_state(
        DOWNLOAD_THD_Y_CAP_KEY,
        "download_thd_y_max",
        st.session_state[THD_Y_CAP_KEY],
    )
    st.caption(
        "Choose result datasets, locations, groups, and cases. Each selected "
        "dataset/location/group becomes one spectrum chart."
    )
    dataset_options = files.results
    dataset_key = "download_datasets"
    if dataset_key in st.session_state:
        stored_datasets = st.session_state[dataset_key]
        valid_datasets = [dataset for dataset in stored_datasets if dataset in dataset_options]
        if valid_datasets != stored_datasets:
            st.session_state[dataset_key] = valid_datasets
        selected_datasets = st.multiselect(
            "Result datasets",
            options=[SELECT_ALL_OPTION, CLEAR_ALL_OPTION, *dataset_options],
            format_func=lambda source: _result_dataset_option_label(source, result_dataset_labels),
            select_all=False,
            key=dataset_key,
            on_change=_handle_multiselect_dropdown_action,
            args=(dataset_key, dataset_options),
        )
    else:
        selected_datasets = st.multiselect(
            "Result datasets",
            options=[SELECT_ALL_OPTION, CLEAR_ALL_OPTION, *dataset_options],
            default=dataset_options,
            format_func=lambda source: _result_dataset_option_label(source, result_dataset_labels),
            select_all=False,
            key=dataset_key,
            on_change=_handle_multiselect_dropdown_action,
            args=(dataset_key, dataset_options),
        )
    if not selected_datasets:
        st.info("Select at least one result dataset to prepare a chart set.")
        return

    locations_by_dataset: dict[str, list[str]] = {}
    result_sheets_by_dataset: dict[str, dict[str, pd.DataFrame]] = {}
    groups_by_dataset: dict[str, dict[str, list[str]]] = {}
    selected_groups_by_dataset: dict[str, list[str]] = {}
    case_selections_by_dataset: dict[str, dict[str, list[str]]] = {}
    invalid_selected_locations: list[str] = []

    st.markdown("**Dataset locations and case selection**")
    for dataset in selected_datasets:
        with st.expander(
            result_dataset_labels[dataset.name],
            expanded=(dataset == selected_dataset),
        ):
            dataset_conditions = matched_conditions(dataset.name, conditions)
            if dataset_conditions:
                st.caption(
                    " · ".join(
                        f"{token}: {description}"
                        for token, description in dataset_conditions
                    )
                )
            try:
                dataset_sheets = _load_cached(_cached_results, dataset)
            except Exception as exc:
                st.error(f"Could not read `{dataset.name}`: {exc}")
                invalid_selected_locations.append(dataset.name)
                continue
            result_sheets_by_dataset[dataset.name] = dataset_sheets
            if not dataset_sheets:
                st.error(f"`{dataset.name}` contains no worksheets.")
                invalid_selected_locations.append(dataset.name)
                continue

            location_options = list(dataset_sheets)
            location_key = f"download_locations::{dataset.name}"
            location_column, group_column = st.columns(2, gap="medium")
            with location_column:
                if location_key in st.session_state:
                    stored_locations = st.session_state[location_key]
                    valid_locations = [
                        location for location in stored_locations if location in location_options
                    ]
                    if valid_locations != stored_locations:
                        st.session_state[location_key] = valid_locations
                    selected_locations = st.multiselect(
                        "Locations",
                        options=[SELECT_ALL_OPTION, CLEAR_ALL_OPTION, *location_options],
                        format_func=_case_option_label,
                        select_all=False,
                        key=location_key,
                        on_change=_handle_multiselect_dropdown_action,
                        args=(location_key, location_options),
                    )
                else:
                    selected_locations = st.multiselect(
                        "Locations",
                        options=[SELECT_ALL_OPTION, CLEAR_ALL_OPTION, *location_options],
                        default=location_options,
                        format_func=_case_option_label,
                        select_all=False,
                        key=location_key,
                        on_change=_handle_multiselect_dropdown_action,
                        args=(location_key, location_options),
                    )
            locations_by_dataset[dataset.name] = selected_locations

            for location in selected_locations:
                report = validate_result(
                    dataset_sheets[location],
                    mapped_case_codes if files.mapping else None,
                    location,
                )
                if report.errors:
                    invalid_selected_locations.append(f"{dataset.name} / {location}")
                    st.error(
                        f"`{location}` cannot be exported until its result data are corrected: "
                        + " ".join(report.errors)
                    )

            group_cases = _export_group_cases(
                dataset_sheets,
                selected_locations,
                cases,
                bool(files.mapping),
            )
            groups_by_dataset[dataset.name] = group_cases
            group_options = list(group_cases)
            with group_column:
                if group_options:
                    group_key = f"download_groups::{dataset.name}"
                    if group_key in st.session_state:
                        stored_groups = st.session_state[group_key]
                        valid_groups = [group for group in stored_groups if group in group_options]
                        if valid_groups != stored_groups:
                            st.session_state[group_key] = valid_groups
                        selected_groups = st.multiselect(
                            "Case groups",
                            options=[SELECT_ALL_OPTION, CLEAR_ALL_OPTION, *group_options],
                            format_func=_case_option_label,
                            select_all=False,
                            key=group_key,
                            on_change=_handle_multiselect_dropdown_action,
                            args=(group_key, group_options),
                        )
                    else:
                        selected_groups = st.multiselect(
                            "Case groups",
                            options=[SELECT_ALL_OPTION, CLEAR_ALL_OPTION, *group_options],
                            default=group_options,
                            format_func=_case_option_label,
                            select_all=False,
                            key=group_key,
                            on_change=_handle_multiselect_dropdown_action,
                            args=(group_key, group_options),
                        )
                else:
                    selected_groups = []
                    st.info("No mapped cases are available at all selected locations.")
            selected_groups_by_dataset[dataset.name] = selected_groups

            selected_cases_for_groups: dict[str, list[str]] = {}
            if selected_groups:
                all_cases_key = f"download_all_cases::{dataset.name}"
                all_cases = st.checkbox(
                    "All cases",
                    value=True,
                    key=all_cases_key,
                    help="Clear this to choose cases separately for each selected group.",
                )
                case_columns = st.columns(2, gap="medium")
                for group_index, group in enumerate(selected_groups):
                    available_cases = group_cases[group]
                    if all_cases:
                        selected_cases_for_groups[group] = available_cases.copy()
                        continue

                    selection_key = f"download_case_selection::{dataset.name}::{group}"
                    widget_key = f"download_case_picker::{dataset.name}::{group}"
                    saved_cases = st.session_state.get(selection_key, available_cases)
                    saved_cases = [case for case in saved_cases if case in available_cases]
                    st.session_state[selection_key] = saved_cases.copy()
                    widget_cases = st.session_state.get(widget_key, saved_cases)
                    st.session_state[widget_key] = [
                        case
                        for case in widget_cases
                        if case in available_cases or case in {SELECT_ALL_OPTION, CLEAR_ALL_OPTION}
                    ]
                    with case_columns[group_index % 2]:
                        st.multiselect(
                            f"{group} cases",
                            options=[SELECT_ALL_OPTION, CLEAR_ALL_OPTION, *available_cases],
                            select_all=False,
                            format_func=_case_option_label,
                            key=widget_key,
                            on_change=_handle_download_case_selection,
                            args=(widget_key, selection_key, available_cases),
                        )
                    selected_cases_for_groups[group] = st.session_state[selection_key].copy()
            case_selections_by_dataset[dataset.name] = selected_cases_for_groups
            if selected_locations:
                st.caption("Case choices include codes present in every selected location.")

    st.subheader("Limits")
    export_limit_source: WorkbookSource | None = None
    export_limits: pd.DataFrame | None = None
    export_limit_series_by_location: dict[str, str] = {}
    export_limit_display = "Bars"
    export_locations = sorted(
        {
            location
            for dataset in selected_datasets
            for location in locations_by_dataset.get(dataset.name, [])
        },
        key=str.casefold,
    )
    if files.limits:
        default_limit_source = (
            selected_limit_file
            if selected_limit_file in files.limits
            else files.limits[0]
        )
        if len(files.limits) > 1:
            export_limit_source = st.selectbox(
                "Limit source",
                options=files.limits,
                index=files.limits.index(default_limit_source),
                format_func=lambda source: source.name,
                key="download_limit_source",
            )
        else:
            export_limit_source = files.limits[0]
            st.caption(f"Limit source: `{export_limit_source.name}`")
        try:
            export_limits = _load_cached(_cached_limits, export_limit_source)
            export_limit_report = validate_limits(export_limits, export_limit_source.name)
            if export_limit_report.is_valid:
                limit_series_options = ["No limit", *export_limits.columns[1:].tolist()]
            else:
                limit_series_options = ["No limit"]
                st.warning("This limit workbook is invalid; chart export can continue without limits.")
        except Exception as exc:
            limit_series_options = ["No limit"]
            st.warning(f"Could not read `{export_limit_source.name}`; chart export can continue without limits. {exc}")

        if len(limit_series_options) > 1 and export_locations:
            st.caption(
                "Choose a series for each location. A location’s choice applies to every selected dataset containing it."
            )
            limit_columns = st.columns(2, gap="medium")
            for location_index, location in enumerate(export_locations):
                limit_series_key = (
                    f"download_limit_series::{export_limit_source.name}::{location}"
                )
                main_limit_key = (
                    f"limit_series_selection::{export_limit_source.name}::{location}"
                )
                preferred_series = st.session_state.get(main_limit_key, "No limit")
                if (
                    location == selected_location
                    and export_limit_source == selected_limit_file
                ):
                    preferred_series = selected_limit
                if preferred_series not in limit_series_options:
                    preferred_series = "No limit"
                if st.session_state.get(limit_series_key) not in limit_series_options:
                    st.session_state[limit_series_key] = preferred_series
                with limit_columns[location_index % 2]:
                    export_limit_series_by_location[location] = st.selectbox(
                        location,
                        options=limit_series_options,
                        key=limit_series_key,
                        help=f"Limit curve applied to {location} in every selected dataset.",
                    )
        elif export_locations:
            st.caption("No valid limit series are available. These charts will use No limit.")
        else:
            st.caption("Select locations above to assign a limit series.")

        if any(series != "No limit" for series in export_limit_series_by_location.values()):
            display_index = 1 if limit_display == "Dashes" else 0
            export_limit_display = st.radio(
                "Limit display",
                options=["Bars", "Dashes"],
                index=display_index,
                horizontal=True,
                key="download_limit_display",
            )
    else:
        st.caption("No limit workbook loaded. Chart sets will be exported without limits.")

    st.subheader("Y-axis scale")
    st.caption("Starts with the live-chart settings. Changes here affect this ZIP only.")
    download_auto_y_limits = st.checkbox(
        "Auto y-axis limits",
        key=DOWNLOAD_AUTO_Y_LIMITS_KEY,
        help="Use automatic ranges or fixed maxima shared across all exported charts of each type.",
    )
    if not download_auto_y_limits:
        st.caption("Values above a fixed maximum are clipped. Spectrum and THD use separate maxima.")
        export_scale_left, export_scale_right = st.columns(2, gap="medium")
        with export_scale_left:
            st.session_state.setdefault(
                DOWNLOAD_SPECTRUM_Y_INPUT_KEY,
                st.session_state[DOWNLOAD_SPECTRUM_Y_CAP_KEY],
            )
            st.number_input(
                "Spectrum maximum (%)",
                min_value=0.000001,
                step=_y_axis_input_step(
                    st.session_state[DOWNLOAD_SPECTRUM_Y_CAP_KEY]
                ),
                format="%.6g",
                key=DOWNLOAD_SPECTRUM_Y_INPUT_KEY,
            )
            st.session_state[DOWNLOAD_SPECTRUM_Y_CAP_KEY] = st.session_state[
                DOWNLOAD_SPECTRUM_Y_INPUT_KEY
            ]
        with export_scale_right:
            st.session_state.setdefault(
                DOWNLOAD_THD_Y_INPUT_KEY,
                st.session_state[DOWNLOAD_THD_Y_CAP_KEY],
            )
            st.number_input(
                "THD maximum (%)",
                min_value=0.000001,
                step=_y_axis_input_step(st.session_state[DOWNLOAD_THD_Y_CAP_KEY]),
                format="%.6g",
                key=DOWNLOAD_THD_Y_INPUT_KEY,
            )
            st.session_state[DOWNLOAD_THD_Y_CAP_KEY] = st.session_state[
                DOWNLOAD_THD_Y_INPUT_KEY
            ]

    st.subheader("Output")
    output_left, output_right = st.columns(2, gap="medium")
    with output_left:
        include_thd = st.checkbox(
            "Include THD",
            value=True,
            key="download_include_thd",
            help="Add a separate vertical THD chart for each selected group when its data are complete.",
        )
        include_case_descriptions = st.checkbox(
            "Add CSV case descriptions",
            value=True,
            key="download_include_case_descriptions",
            help="Include a case_descriptions.csv with Case and Description columns for each chart group.",
        )
    with output_right:
        split_by_folders = st.checkbox(
            "Split files into folders",
            value=True,
            key="download_split_by_folders",
            help="Organize files by dataset, location, and case group inside the ZIP.",
        )

    export_plan: list[tuple[WorkbookSource, str, str, list[str]]] = []
    for dataset in selected_datasets:
        for location in locations_by_dataset.get(dataset.name, []):
            for group in selected_groups_by_dataset.get(dataset.name, []):
                selected_cases = case_selections_by_dataset.get(dataset.name, {}).get(group, [])
                if selected_cases:
                    export_plan.append((dataset, location, group, selected_cases))

    if export_plan and not download_auto_y_limits and not invalid_selected_locations:
        spectrum_clipped = 0
        thd_clipped = 0
        max_spectrum_value = 0.0
        max_thd_value = 0.0
        for dataset, location, _group, selected_cases in export_plan:
            selected_limit_for_export = export_limit_series_by_location.get(
                location, "No limit"
            )
            export_data = build_group_data(
                result_sheets_by_dataset[dataset.name][location],
                selected_cases,
                limits=export_limits if selected_limit_for_export != "No limit" else None,
                limit_series=selected_limit_for_export,
            )
            spectrum_max = _max_numeric_value(export_data)
            max_spectrum_value = max(max_spectrum_value, spectrum_max)
            if spectrum_max > st.session_state[DOWNLOAD_SPECTRUM_Y_CAP_KEY]:
                spectrum_clipped += 1
            if include_thd:
                export_thd_data, _ = build_thd_data(export_data, description_by_case)
                thd_max = _max_numeric_value(export_thd_data["THD (%)"])
                max_thd_value = max(max_thd_value, thd_max)
                if thd_max > st.session_state[DOWNLOAD_THD_Y_CAP_KEY]:
                    thd_clipped += 1
        if spectrum_clipped or thd_clipped:
            clipped_messages = []
            if spectrum_clipped:
                clipped_messages.append(
                    f"{spectrum_clipped} spectrum chart(s), up to {max_spectrum_value:.5g}%"
                )
            if thd_clipped:
                clipped_messages.append(
                    f"{thd_clipped} THD chart(s), up to {max_thd_value:.5g}%"
                )
            st.warning(
                "The selected maxima crop data in "
                + " and ".join(clipped_messages)
                + ". Increase the maxima or continue knowing those PNG values will be clipped."
            )

    if export_plan:
        expected_thd_count = len(export_plan) if include_thd else 0
        st.info(
            f"{len(export_plan)} dataset/location/group combinations · "
            f"{len(export_plan)} harmonic charts · up to {expected_thd_count} THD charts."
        )
    else:
        st.warning("Select at least one location, group, and case to prepare a chart set.")

    signature_data = {
        "datasets": [
            {
                "name": dataset.name,
                "locations": locations_by_dataset.get(dataset.name, []),
                "groups": {
                    group: case_selections_by_dataset.get(dataset.name, {}).get(group, [])
                    for group in selected_groups_by_dataset.get(dataset.name, [])
                },
            }
            for dataset in selected_datasets
        ],
        "limit_source": export_limit_source.name if export_limit_source else None,
        "limit_series_by_location": export_limit_series_by_location,
        "limit_display": export_limit_display,
        "include_thd": include_thd,
        "include_case_descriptions": include_case_descriptions,
        "split_by_folders": split_by_folders,
        "show_all_harmonic_numbers": show_all_harmonic_numbers,
        "auto_y_limits": download_auto_y_limits,
        "spectrum_y_max": st.session_state[DOWNLOAD_SPECTRUM_Y_CAP_KEY],
        "thd_y_max": st.session_state[DOWNLOAD_THD_Y_CAP_KEY],
    }
    signature = json.dumps(signature_data, sort_keys=True)
    if st.session_state.get("download_archive_signature") != signature:
        st.session_state.pop("download_archive_bytes", None)
        st.session_state.pop("download_archive_name", None)
        st.session_state.pop("download_archive_file_count", None)
        st.session_state.pop("download_archive_thd_omissions", None)

    can_prepare = bool(export_plan) and not invalid_selected_locations
    prepare_clicked = st.button(
        "Prepare ZIP",
        key="prepare_chart_archive",
        type="primary",
        disabled=not can_prepare,
    )
    if prepare_clicked:
        progress_bar = st.progress(0.0, text="Preparing selected charts…")
        status_container = st.status("Preparing chart set", expanded=True)
        thd_omissions: list[str] = []
        try:
            with status_container:
                total_groups = len(export_plan)
                def export_items():
                    loaded_dataset: WorkbookSource | None = None
                    dataset_sheets: dict[str, pd.DataFrame] = {}
                    for plan_index, (
                        dataset,
                        location,
                        group,
                        selected_cases,
                    ) in enumerate(export_plan):
                        if dataset != loaded_dataset:
                            dataset_sheets = _load_cached(_cached_results, dataset)
                            loaded_dataset = dataset
                        group_data = build_group_data(
                            dataset_sheets[location],
                            selected_cases,
                            limits=export_limits
                            if export_limit_series_by_location.get(location, "No limit")
                            != "No limit"
                            else None,
                            limit_series=export_limit_series_by_location.get(
                                location, "No limit"
                            ),
                        )
                        spectrum_figure = build_harmonic_figure(
                            group_data,
                            description_by_case,
                            f"{group} · {location}",
                            limit_display=export_limit_display,
                            show_all_harmonic_numbers=show_all_harmonic_numbers,
                            y_axis_max=(
                                None
                                if download_auto_y_limits
                                else st.session_state[DOWNLOAD_SPECTRUM_Y_CAP_KEY]
                            ),
                        )
                        thd_figure = None
                        thd_order_range = None
                        if include_thd:
                            thd_data, thd_order_range = build_thd_data(
                                group_data,
                                description_by_case,
                            )
                            if thd_order_range and thd_data["THD (%)"].notna().any():
                                lower_order, upper_order = thd_order_range
                                thd_figure = build_thd_figure(
                                    thd_data,
                                    selected_cases,
                                    f"Voltage THD · orders {lower_order}–{upper_order}",
                                    y_axis_max=(
                                        None
                                        if download_auto_y_limits
                                        else st.session_state[DOWNLOAD_THD_Y_CAP_KEY]
                                    ),
                                )
                            else:
                                thd_omissions.append(
                                    f"{dataset.name} / {location} / {group}"
                                )

                        if files.mapping:
                            case_descriptions = pd.DataFrame(
                                {
                                    "Case": selected_cases,
                                    "Description": [
                                        description_by_case.get(case, "No mapping entry")
                                        for case in selected_cases
                                    ],
                                }
                            )
                        else:
                            case_descriptions = pd.DataFrame(
                                {
                                    "Case": selected_cases,
                                    "Description": [""] * len(selected_cases),
                                }
                            )
                        progress_bar.progress(
                            0.05 + 0.3 * (plan_index + 1) / total_groups,
                            text=f"Preparing chart data {plan_index + 1} of {total_groups}…",
                        )
                        yield ChartExportItem(
                            dataset=result_dataset_labels[dataset.name],
                            location=location,
                            group=group,
                            spectrum_figure=spectrum_figure,
                            case_descriptions=case_descriptions,
                            thd_figure=thd_figure,
                            thd_order_range=thd_order_range,
                        )

                def update_archive_progress(fraction: float, message: str) -> None:
                    progress_bar.progress(0.35 + 0.65 * fraction, text=message)

                archive_bytes, file_count = build_chart_archive(
                    export_items(),
                    split_by_folders=split_by_folders,
                    include_case_descriptions=include_case_descriptions,
                    on_progress=update_archive_progress,
                    total_items=total_groups,
                )
                archive_name = (
                    f"murakami_chart_set_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
                )
                st.session_state["download_archive_bytes"] = archive_bytes
                st.session_state["download_archive_name"] = archive_name
                st.session_state["download_archive_file_count"] = file_count
                st.session_state["download_archive_thd_omissions"] = thd_omissions
                st.session_state["download_archive_signature"] = signature
                progress_bar.progress(1.0, text="Chart set is ready.")
            status_container.update(
                label="Chart set is ready",
                state="complete",
                expanded=False,
            )
        except Exception as exc:
            status_container.update(
                label="Could not prepare chart set",
                state="error",
                expanded=True,
            )
            st.error(f"Could not prepare the chart ZIP: {exc}")

    if (
        st.session_state.get("download_archive_signature") == signature
        and st.session_state.get("download_archive_bytes")
    ):
        archive_bytes = st.session_state["download_archive_bytes"]
        st.caption(
            f"Ready · {st.session_state['download_archive_file_count']} files · "
            f"{len(archive_bytes) / (1024 * 1024):.1f} MB"
        )
        st.download_button(
            "Download ZIP",
            data=archive_bytes,
            file_name=st.session_state["download_archive_name"],
            mime="application/zip",
            key="download_chart_archive",
            icon=":material/download:",
            type="primary",
            on_click="ignore",
            width="stretch",
        )
        thd_omissions = st.session_state.get("download_archive_thd_omissions", [])
        if thd_omissions:
            st.caption(
                f"THD charts were omitted for {len(thd_omissions)} combination(s) "
                "because complete values were unavailable."
            )


if show_group_tabs:
    st.markdown(
        "<style>"
        "div[role='tablist']::before {"
        "content:'Groups:'; display:inline-flex; align-items:center; "
        "flex:0 0 auto; margin-right:0.75rem; white-space:nowrap; "
        "font-weight:600; color:var(--text-color);"
        "}"
        "</style>",
        unsafe_allow_html=True,
    )
    group_containers = st.tabs(
        [group for group, _, _ in case_groups],
        key="group_tabs",
        on_change="rerun",
    )
else:
    st.markdown("#### Groups:")
    group_containers = [
        st.expander(group, expanded=(group == "Intact" or not files.mapping))
        for group, _, _ in case_groups
    ]

for (group, group_rows, group_case_codes), group_container in zip(
    case_groups, group_containers
):
    if show_group_tabs and not group_container.open:
        continue
    with group_container:
        if not group_case_codes:
            st.info("No cases from this group are present in the selected location.")
            continue

        case_key = f"cases::{selected_dataset.name}::{selected_location}::{group}"
        selection_key = f"case-selection::{selected_dataset.name}::{selected_location}::{group}"
        if selection_key not in st.session_state:
            st.session_state[selection_key] = group_case_codes.copy()
        saved_cases = st.session_state[selection_key]
        valid_saved_cases = [case for case in group_case_codes if case in saved_cases]
        if saved_cases != valid_saved_cases:
            st.session_state[selection_key] = valid_saved_cases.copy()
        if case_key not in st.session_state:
            st.session_state[case_key] = valid_saved_cases.copy()
        case_control_key = f"case-selector-{slug_name(group)}"
        with st.container(key=case_control_key):
            selected_cases = st.multiselect(
                "Cases to compare",
                options=[SELECT_ALL_OPTION, CLEAR_ALL_OPTION, *group_case_codes],
                select_all=False,
                format_func=_case_option_label,
                key=case_key,
                on_change=_handle_case_dropdown_action,
                args=(case_key, selection_key, group_case_codes),
                help=(
                    "Select one or more cases. Use Select all or Clear all in the dropdown. "
                    + (
                        "Hover over a point for its full description."
                        if files.mapping
                        else "Cases are identified by their result column names."
                    )
                ),
            )
            chip_styles = _case_chip_styles(case_control_key, selected_cases)
            if chip_styles:
                st.html(chip_styles)

        if not selected_cases:
            st.info("Select at least one case to display the spectrum and THD summary.")
            continue

        group_data = build_group_data(
            selected_result,
            selected_cases,
            limits=limits if selected_limit_for_plot else None,
            limit_series=selected_limit_for_plot,
        )
        if not auto_y_limits:
            spectrum_data_max = _max_numeric_value(group_data)
            if spectrum_data_max > st.session_state[SPECTRUM_Y_CAP_KEY]:
                st.warning(
                    f"Spectrum values reach {spectrum_data_max:.5g}%, above the fixed "
                    f"maximum of {st.session_state[SPECTRUM_Y_CAP_KEY]:.5g}%. Higher values are clipped."
                )
        figure = build_harmonic_figure(
            group_data,
            description_by_case,
            f"{group} · {selected_location}",
            limit_display=limit_display,
            show_all_harmonic_numbers=show_all_harmonic_numbers,
            y_axis_max=None if auto_y_limits else st.session_state[SPECTRUM_Y_CAP_KEY],
        )
        st.plotly_chart(
            figure,
            width="stretch",
            theme=None,
            config={
                "displaylogo": False,
                "displayModeBar": True,
                "scrollZoom": True,
                "toImageButtonOptions": {
                    "format": "png",
                    "filename": slug_name(
                        f"{selected_dataset_label}_{selected_location}_{group}"
                    ),
                    "scale": 2,
                },
            },
            key=f"plot::{selected_dataset.name}::{selected_location}::{group}",
        )

        thd_data, thd_order_range = build_thd_data(group_data, description_by_case)
        if thd_order_range is None:
            st.info("THD cannot be calculated because the selected data has no harmonic orders from 2 onward.")
        else:
            lower_order, upper_order = thd_order_range
            st.caption(
                f"One vertical bar per case · root-sum-square of voltage-distortion "
                f"values at orders {lower_order}–{upper_order}."
            )
            incomplete_cases = thd_data.loc[thd_data["THD (%)"].isna()]
            if thd_data["THD (%)"].notna().any():
                thd_data_max = _max_numeric_value(thd_data["THD (%)"])
                if (
                    not auto_y_limits
                    and thd_data_max > st.session_state[THD_Y_CAP_KEY]
                ):
                    st.warning(
                        f"THD values reach {thd_data_max:.5g}%, above the fixed "
                        f"maximum of {st.session_state[THD_Y_CAP_KEY]:.5g}%. Higher values are clipped."
                    )
                thd_figure = build_thd_figure(
                    thd_data,
                    selected_cases,
                    f"Voltage THD · orders {lower_order}–{upper_order}",
                    y_axis_max=None if auto_y_limits else st.session_state[THD_Y_CAP_KEY],
                )
                st.plotly_chart(
                    thd_figure,
                    width="stretch",
                    theme=None,
                    config={
                        "displaylogo": False,
                        "displayModeBar": True,
                        "toImageButtonOptions": {
                            "format": "png",
                            "filename": slug_name(
                                f"thd_{selected_dataset_label}_{selected_location}_{group}"
                            ),
                            "scale": 2,
                        },
                    },
                    key=f"thd_plot::{selected_dataset.name}::{selected_location}::{group}",
                )
            else:
                st.info(
                    f"THD is unavailable because no selected case has complete values "
                    f"for orders {lower_order}–{upper_order}."
                )
            if not incomplete_cases.empty:
                missing_details = "; ".join(
                    f"{row['Case']} (orders {', '.join(map(str, row['Missing orders']))})"
                    for _, row in incomplete_cases.iterrows()
                )
                st.caption(f"THD omitted for cases with missing harmonic values: {missing_details}.")

        if files.mapping:
            case_details = group_rows.loc[
                group_rows["Case number"].isin(selected_cases), ["Case number", "Description"]
            ].rename(columns={"Case number": "Case"})
            with st.expander(f"Selected case descriptions ({len(case_details)})", expanded=False):
                st.dataframe(
                    case_details,
                    column_order=["Case", "Description"],
                    hide_index=True,
                    width="stretch",
                )

        csv_name = (
            slug_name(f"{selected_dataset_label}_{selected_location}_{group}") + ".csv"
        )
        st.download_button(
            "Download plotted data (CSV)",
            data=group_data.to_csv(index=False).encode("utf-8-sig"),
            file_name=csv_name,
            mime="text/csv",
            icon=":material/download:",
            type="secondary",
            key=f"csv::{selected_dataset.name}::{selected_location}::{group}",
        )

render_data_status()
if open_chart_download:
    st.session_state["show_chart_download_dialog"] = True
if st.session_state["show_chart_download_dialog"]:
    render_chart_download_dialog()
