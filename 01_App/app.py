"""Murakami Harmonic Analysis Dashboard."""

from __future__ import annotations

from pathlib import Path
import re

import pandas as pd
import streamlit as st

from data_loader import (
    discover_input_files,
    load_limits,
    load_mapping,
    load_result_workbook,
    matched_conditions,
)
from plotting import build_group_data, build_harmonic_figure
from validation import KNOWN_GROUPS, ValidationReport, validate_limits, validate_mapping, validate_result


APP_DIR = Path(__file__).resolve().parent
INPUT_DIR = APP_DIR / "Input_files"
APP_NAME = "Murakami Harmonic Analysis Dashboard"
SELECT_ALL_OPTION = "__dashboard_action_select_all__"
CLEAR_ALL_OPTION = "__dashboard_action_clear_all__"

st.set_page_config(
    page_title=APP_NAME,
    page_icon=":material/graphic_eq:",
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


def _load_cached(loader, path: Path):
    stat = path.stat()
    return loader(str(path), stat.st_mtime_ns, stat.st_size)


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


def _slug(value: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "_", value).strip("_").lower()
    return slug or "harmonics"


def _report_summary(report: ValidationReport) -> str:
    if report.errors:
        return f"{len(report.errors)} error(s), {len(report.warnings)} warning(s)"
    if report.warnings:
        return f"Ready with {len(report.warnings)} warning(s)"
    return "Valid"


def _handle_case_dropdown_action(case_key: str, available_cases: list[str]) -> None:
    selected = st.session_state.get(case_key, [])
    if SELECT_ALL_OPTION in selected:
        st.session_state[case_key] = available_cases.copy()
    elif CLEAR_ALL_OPTION in selected:
        st.session_state[case_key] = []


def _case_option_label(value: str) -> str:
    if value == SELECT_ALL_OPTION:
        return "Select all"
    if value == CLEAR_ALL_OPTION:
        return "Clear all"
    return value


files = discover_input_files(INPUT_DIR)

st.header(APP_NAME)
st.caption("Interactive harmonic-voltage results viewer")

with st.sidebar:
    st.header("Analysis setup")
    if st.button("Reload input files", icon=":material/refresh:", width="stretch"):
        st.cache_data.clear()
        st.rerun()

    st.caption(f"Input folder: `{INPUT_DIR.name}/`")

if len(files.mapping) != 1:
    if not files.mapping:
        st.error("No `Cases_description*.xlsx` mapping workbook was found in `01_App/Input_files`.")
    else:
        st.error(
            "Exactly one `Cases_description*.xlsx` mapping workbook is required. Found: "
            + ", ".join(path.name for path in files.mapping)
            + "."
        )
    st.stop()

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

if not files.results:
    st.error("No result workbooks were found in `01_App/Input_files`.")
    st.stop()

with st.sidebar:
    selected_dataset = st.selectbox(
        "Result dataset",
        options=files.results,
        format_func=lambda path: path.name,
        key="result_dataset",
    )

try:
    result_sheets = _load_cached(_cached_results, selected_dataset)
except Exception as exc:
    st.error(f"Could not read result workbook `{selected_dataset.name}`: {exc}")
    st.stop()

if not result_sheets:
    st.error(f"Result workbook `{selected_dataset.name}` contains no worksheets.")
    st.stop()

mapped_case_codes = _valid_case_codes(cases)
result_reports = {
    sheet_name: validate_result(data, mapped_case_codes, sheet_name)
    for sheet_name, data in result_sheets.items()
}

with st.sidebar:
    selected_location = st.selectbox(
        "Busbar / location",
        options=list(result_sheets),
        key="result_location",
    )

    selected_limit_file: Path | None = None
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
    limit_widget_key = (
        f"limit_series::{selected_limit_file.name}"
        if selected_limit_file
        else "limit_series::no-source"
    )
    selected_limit = st.selectbox(
        "Limit series",
        options=limit_options,
        help="Choose a reference series explicitly. No series is selected automatically.",
        key=limit_widget_key,
    )
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
    show_all_harmonic_numbers = st.checkbox(
        "Show all harmonic numbers",
        key="show_all_harmonic_numbers",
        help="Label each harmonic order present in the selected result data.",
    )

    recognized_conditions = matched_conditions(selected_dataset.name, conditions)
    with st.expander("Dataset filename conditions", expanded=False):
        if recognized_conditions:
            for token, description in recognized_conditions:
                st.caption(f"**{token}** — {description}")
        else:
            st.caption("No filename tokens matched the Conditions worksheet.")

selected_result = result_sheets[selected_location]
selected_result_report = result_reports[selected_location]

available_case_count = max(0, selected_result.shape[1] - 1)
order_values = pd.to_numeric(selected_result.iloc[:, 0], errors="coerce").dropna() if selected_result.shape[1] else pd.Series(dtype=float)
order_range = (
    f"{order_values.min():g}–{order_values.max():g}" if not order_values.empty else "Unavailable"
)
selected_limit_for_plot = selected_limit if selected_limit != "No limit" else None

st.caption(f"{len(mapped_case_codes)} mapped cases · {available_case_count} result traces")

status_has_errors = (
    bool(selected_result_report.errors)
    or bool(limit_report and limit_report.errors)
    or bool(limit_load_error)
)
with st.expander("Input data status", expanded=status_has_errors):
    st.write(f"**Mapping:** `{files.mapping[0].name}` · {len(mapped_case_codes)} mapped cases")
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
                "Case columns": count,
                "Harmonic rows": row_count,
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
    if other_location_errors:
        st.markdown("**Other location issues**")
        for sheet_name, message in other_location_errors:
            st.error(f"{sheet_name}: {message}")
    if selected_result_report.warnings:
        st.markdown(f"**{selected_location} warnings**")
        for message in selected_result_report.warnings:
            st.warning(message)
    if limit_report and limit_report.errors:
        st.markdown("**Limit workbook issues**")
        for message in limit_report.errors:
            st.error(message)
    if limit_report and limit_report.warnings:
        for message in limit_report.warnings:
            st.warning(message)
    if limit_load_error:
        st.error(f"Could not read limit workbook `{selected_limit_file.name}`: {limit_load_error}")

if selected_result_report.errors:
    st.error(f"Plotting is disabled for `{selected_location}` until its result sheet is corrected.")
    st.stop()

if selected_limit_for_plot and (limit_report is None or not limit_report.is_valid):
    st.error("The selected limit workbook is invalid. Choose another source or select No limit.")
    st.stop()

if mapping_report.warnings:
    for message in mapping_report.warnings:
        st.warning(message)

description_by_case = {
    str(row["Case number"]): str(row["Description"])
    for _, row in cases.iterrows()
    if str(row["Case number"]).strip()
}
result_case_codes = {str(column) for column in selected_result.columns[1:]}

dataset_condition_text = " · ".join(token for token, _ in recognized_conditions)
condition_tokens = {token for token, _ in recognized_conditions}
dataset_label = " ".join(
    token for token in selected_dataset.stem.split("_") if token and token not in condition_tokens
)
context_line = f"**{dataset_label or selected_dataset.stem.replace('_', ' ')}**"
if dataset_condition_text:
    context_line += f" · {dataset_condition_text}"
context_line += f" · {selected_location}"
if selected_limit_for_plot:
    context_line += f" · Reference: {selected_limit_for_plot}"
else:
    context_line += " · Reference: no limit"
context_line += f" · Harmonic orders {order_range}"
st.markdown(context_line)

for group in KNOWN_GROUPS:
    group_rows = cases.loc[cases["Group"] == group]
    group_case_codes = [
        str(code)
        for code in group_rows["Case number"].tolist()
        if str(code).strip() and str(code) in result_case_codes
    ]
    with st.expander(group, expanded=(group == "Intact")):
        if not group_case_codes:
            st.info("No mapped cases from this group are present in the selected location.")
            continue

        case_key = f"cases::{selected_dataset.name}::{selected_location}::{group}"
        if case_key not in st.session_state:
            st.session_state[case_key] = group_case_codes.copy()
        selected_cases = st.multiselect(
            "Cases to compare",
            options=[SELECT_ALL_OPTION, CLEAR_ALL_OPTION, *group_case_codes],
            select_all=False,
            format_func=_case_option_label,
            key=case_key,
            on_change=_handle_case_dropdown_action,
            args=(case_key, group_case_codes),
            help=(
                "Select one or more cases. Use Select all or Clear all in the dropdown. "
                "Hover over a point for its full description."
            ),
        )
        if not selected_cases:
            st.info("Select at least one case to display the spectrum.")
            continue

        group_data = build_group_data(
            selected_result,
            selected_cases,
            limits=limits if selected_limit_for_plot else None,
            limit_series=selected_limit_for_plot,
        )
        figure = build_harmonic_figure(
            group_data,
            description_by_case,
            f"{group} · {selected_location}",
            limit_display=limit_display,
            show_all_harmonic_numbers=show_all_harmonic_numbers,
        )
        st.plotly_chart(
            figure,
            width="stretch",
            config={
                "displaylogo": False,
                "displayModeBar": True,
                "scrollZoom": True,
                "toImageButtonOptions": {
                    "format": "png",
                    "filename": _slug(f"{selected_dataset.stem}_{selected_location}_{group}"),
                    "scale": 2,
                },
            },
            key=f"plot::{selected_dataset.name}::{selected_location}::{group}",
        )

        case_details = group_rows.loc[
            group_rows["Case number"].isin(selected_cases), ["Case number", "Description"]
        ].rename(columns={"Case number": "Case"})
        with st.expander(f"Selected case descriptions ({len(case_details)})", expanded=False):
            st.dataframe(case_details, hide_index=True, width="stretch")

        csv_name = _slug(f"{selected_dataset.stem}_{selected_location}_{group}") + ".csv"
        st.download_button(
            "Download plotted data (CSV)",
            data=group_data.to_csv(index=False).encode("utf-8-sig"),
            file_name=csv_name,
            mime="text/csv",
            icon=":material/download:",
            type="secondary",
            key=f"csv::{selected_dataset.name}::{selected_location}::{group}",
        )
