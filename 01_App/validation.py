"""Structural validation for mapping, result, and limit workbooks."""

from __future__ import annotations

from dataclasses import dataclass, field
import re

import pandas as pd


KNOWN_GROUPS = ("Intact", "Intact energisation", "TX out", "TX out energisation")
REQUIRED_CASE_COLUMNS = ("Case number", "Group", "Description")
REQUIRED_CONDITION_COLUMNS = ("Token", "Description")


@dataclass
class ValidationReport:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.errors


def _blank(value: object) -> bool:
    if pd.isna(value):
        return True
    return isinstance(value, str) and not value.strip()


def _duplicate_values(values: pd.Series) -> list[str]:
    nonblank = values.loc[~values.map(_blank)]
    duplicates = nonblank[nonblank.duplicated(keep=False)].drop_duplicates().tolist()
    return [str(value) for value in duplicates]


def _column_label(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().casefold()


def validate_mapping(cases: pd.DataFrame, conditions: pd.DataFrame) -> ValidationReport:
    report = ValidationReport()
    if cases.columns.duplicated().any():
        report.errors.append("Cases worksheet contains duplicate column names.")
    missing_case_columns = [name for name in REQUIRED_CASE_COLUMNS if name not in cases.columns]
    if missing_case_columns:
        report.errors.append(
            "Cases worksheet is missing required column(s): "
            + ", ".join(missing_case_columns)
            + "."
        )
    if conditions.columns.duplicated().any():
        report.errors.append("Conditions worksheet contains duplicate column names.")
    missing_condition_columns = [
        name for name in REQUIRED_CONDITION_COLUMNS if name not in conditions.columns
    ]
    if missing_condition_columns:
        report.errors.append(
            "Conditions worksheet is missing required column(s): "
            + ", ".join(missing_condition_columns)
            + "."
        )

    if not missing_case_columns:
        active = cases.loc[
            cases[list(REQUIRED_CASE_COLUMNS)].apply(
                lambda row: any(not _blank(value) for value in row), axis=1
            )
        ]
        if active.empty:
            report.errors.append("Cases worksheet contains no case mappings.")
        blank_case = active["Case number"].map(_blank)
        if blank_case.any():
            report.errors.append(f"Cases worksheet has {int(blank_case.sum())} active row(s) with a blank Case number.")
        blank_group = active["Group"].map(_blank)
        if blank_group.any():
            report.errors.append(f"Cases worksheet has {int(blank_group.sum())} active row(s) with a blank Group.")

        duplicates = _duplicate_values(active["Case number"])
        if duplicates:
            report.errors.append("Duplicate case number(s): " + ", ".join(duplicates) + ".")

        unknown_groups = sorted(
            {
                str(value)
                for value in active["Group"].tolist()
                if not _blank(value) and value not in KNOWN_GROUPS
            }
        )
        if unknown_groups:
            report.warnings.append(
                "Unknown case group(s) will appear only in All, not in the standard group tabs: "
                + ", ".join(unknown_groups)
                + "."
            )
        missing_descriptions = active["Description"].map(_blank)
        if missing_descriptions.any():
            report.warnings.append(
                f"Cases worksheet has {int(missing_descriptions.sum())} case(s) without a description."
            )

    if not missing_condition_columns:
        active_conditions = conditions.loc[
            conditions[list(REQUIRED_CONDITION_COLUMNS)].apply(
                lambda row: any(not _blank(value) for value in row), axis=1
            )
        ]
        blank_tokens = active_conditions["Token"].map(_blank)
        if blank_tokens.any():
            report.errors.append(
                f"Conditions worksheet has {int(blank_tokens.sum())} active row(s) with a blank Token."
            )
        duplicate_tokens = _duplicate_values(active_conditions["Token"])
        if duplicate_tokens:
            report.errors.append("Duplicate condition token(s): " + ", ".join(duplicate_tokens) + ".")
        blank_token_descriptions = active_conditions["Description"].map(_blank)
        if blank_token_descriptions.any():
            report.warnings.append(
                "Conditions worksheet has token(s) without a description: "
                + ", ".join(
                    str(value)
                    for value in active_conditions.loc[blank_token_descriptions, "Token"].tolist()
                )
                + "."
            )
    return report


def validate_result(
    result: pd.DataFrame,
    mapped_case_codes: set[str] | None = None,
    sheet_name: str = "result sheet",
) -> ValidationReport:
    report = ValidationReport()
    if result.empty:
        report.errors.append(f"{sheet_name}: no harmonic data rows were found.")
    if result.shape[1] < 2:
        report.errors.append(f"{sheet_name}: at least one case column is required.")
        if result.shape[1] == 0:
            return report

    if _column_label(result.columns[0]) != "harmonic order":
        report.errors.append(f"{sheet_name}: the first column must be named Harmonic Order.")

    case_columns = list(result.columns[1:])
    reserved_headers = [name for name in case_columns if _column_label(name) == "harmonic order"]
    if reserved_headers:
        report.errors.append(
            f"{sheet_name}: case column name conflicts with the Harmonic Order column."
        )
    blank_headers = [index for index, name in enumerate(case_columns, start=2) if _blank(name)]
    if blank_headers:
        report.errors.append(
            f"{sheet_name}: blank case header(s) in column(s) "
            + ", ".join(map(str, blank_headers))
            + "."
        )
    duplicate_cases = _duplicate_values(pd.Series(case_columns, dtype=object))
    if duplicate_cases:
        report.errors.append(
            f"{sheet_name}: duplicate case column(s): " + ", ".join(duplicate_cases) + "."
        )

    orders = pd.to_numeric(result.iloc[:, 0], errors="coerce")
    invalid_orders = orders.isna()
    if invalid_orders.any():
        report.errors.append(
            f"{sheet_name}: {int(invalid_orders.sum())} harmonic order value(s) are blank or non-numeric."
        )
    valid_orders = orders.loc[orders.notna()]
    if valid_orders.duplicated().any():
        duplicates = valid_orders[valid_orders.duplicated(keep=False)].drop_duplicates().tolist()
        report.errors.append(
            f"{sheet_name}: duplicate harmonic order(s): "
            + ", ".join(str(value) for value in duplicates)
            + "."
        )

    for column_index, case_code in enumerate(case_columns, start=1):
        values = result.iloc[:, column_index]
        numeric = pd.to_numeric(values, errors="coerce")
        invalid_values = numeric.isna() & ~values.map(_blank)
        if invalid_values.any():
            report.errors.append(
                f"{sheet_name}: case {case_code!s} has {int(invalid_values.sum())} non-numeric result value(s)."
            )

    unmapped_cases = (
        [str(case) for case in case_columns if not _blank(case) and str(case) not in mapped_case_codes]
        if mapped_case_codes is not None
        else []
    )
    if unmapped_cases:
        report.warnings.append(
            f"{sheet_name}: result case(s) missing from the mapping workbook and available under "
            "Unmapped and All by their exact result codes: "
            + ", ".join(unmapped_cases)
            + "."
        )
    return report


def validate_limits(limits: pd.DataFrame, source_name: str = "Limit worksheet") -> ValidationReport:
    report = ValidationReport()
    if limits.shape[1] < 2:
        report.errors.append(f"{source_name}: at least one limit series is required.")
        if limits.shape[1] == 0:
            return report
    if _column_label(limits.columns[0]) != "harmonic order":
        report.errors.append(f"{source_name}: the first column must be Harmonic Order.")

    series_names = pd.Series(list(limits.columns[1:]), dtype=object)
    if series_names.map(_blank).any():
        report.errors.append(f"{source_name}: one or more limit series have no parsed header.")
    duplicate_series = _duplicate_values(series_names)
    if duplicate_series:
        report.errors.append(
            f"{source_name}: duplicate limit series name(s): "
            + ", ".join(duplicate_series)
            + "."
        )

    orders = pd.to_numeric(limits.iloc[:, 0], errors="coerce")
    invalid_orders = orders.isna()
    if invalid_orders.any():
        report.errors.append(
            f"{source_name}: {int(invalid_orders.sum())} harmonic order value(s) are blank or non-numeric."
        )
    valid_orders = orders.loc[orders.notna()]
    if valid_orders.duplicated().any():
        duplicates = valid_orders[valid_orders.duplicated(keep=False)].drop_duplicates().tolist()
        report.errors.append(
            f"{source_name}: duplicate harmonic order(s): "
            + ", ".join(str(value) for value in duplicates)
            + "."
        )

    for column_index, series_name in enumerate(limits.columns[1:], start=1):
        values = limits.iloc[:, column_index]
        numeric = pd.to_numeric(values, errors="coerce")
        invalid_values = numeric.isna() & ~values.map(_blank)
        if invalid_values.any():
            report.errors.append(
                f"{source_name}: series {series_name!s} has {int(invalid_values.sum())} non-numeric value(s)."
            )
    return report
