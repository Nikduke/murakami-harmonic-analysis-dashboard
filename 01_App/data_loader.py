"""Input-file discovery and Excel parsing for the Murakami dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass(frozen=True)
class InputFiles:
    mapping: list[Path]
    limits: list[Path]
    results: list[Path]


def _is_blank(value: object) -> bool:
    if pd.isna(value):
        return True
    return isinstance(value, str) and not value.strip()


def _drop_fully_blank_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.reset_index(drop=True)
    keep = ~frame.apply(lambda row: all(_is_blank(value) for value in row), axis=1)
    return frame.loc[keep].reset_index(drop=True)


def discover_input_files(input_dir: Path) -> InputFiles:
    """Classify supported workbooks by filename prefix."""
    if not input_dir.is_dir():
        return InputFiles(mapping=[], limits=[], results=[])

    workbooks = sorted(
        (
            path
            for path in input_dir.iterdir()
            if path.is_file()
            and path.suffix.casefold() == ".xlsx"
            and not path.name.startswith("~$")
        ),
        key=lambda path: path.name.casefold(),
    )
    mapping = [path for path in workbooks if path.name.casefold().startswith("cases_description")]
    limits = [path for path in workbooks if path.name.casefold().startswith("limits_")]
    results = [path for path in workbooks if path not in mapping and path not in limits]
    return InputFiles(mapping=mapping, limits=limits, results=results)


def load_mapping(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the Cases and Conditions worksheets without rewriting their values."""
    with pd.ExcelFile(path, engine="openpyxl") as workbook:
        missing_sheets = {"Cases", "Conditions"}.difference(workbook.sheet_names)
        if missing_sheets:
            missing = ", ".join(sorted(missing_sheets))
            raise ValueError(f"Missing required worksheet(s): {missing}")

        cases = pd.read_excel(
            workbook, sheet_name="Cases", dtype=str, keep_default_na=False
        )
        conditions = pd.read_excel(
            workbook, sheet_name="Conditions", dtype=str, keep_default_na=False
        )
        cases.columns = [str(column).strip() for column in cases.columns]
        conditions.columns = [str(column).strip() for column in conditions.columns]
    return _drop_fully_blank_rows(cases), _drop_fully_blank_rows(conditions)


def load_result_workbook(path: Path) -> dict[str, pd.DataFrame]:
    """Read each result sheet while retaining duplicate case headers for validation."""
    result_sheets: dict[str, pd.DataFrame] = {}
    with pd.ExcelFile(path, engine="openpyxl") as workbook:
        for sheet_name in workbook.sheet_names:
            raw = pd.read_excel(workbook, sheet_name=sheet_name, header=None, dtype=object)
            if raw.empty:
                result_sheets[sheet_name] = pd.DataFrame()
                continue

            headers = []
            for header in raw.iloc[0].tolist():
                headers.append("" if _is_blank(header) else str(header))
            body = raw.iloc[1:].copy()
            body.columns = headers
            result_sheets[sheet_name] = _drop_fully_blank_rows(body)
    return result_sheets


def load_limits(path: Path) -> pd.DataFrame:
    """Parse a limit sheet with one or more rows of headers above its data."""
    raw = pd.read_excel(path, sheet_name=0, header=None, dtype=object, engine="openpyxl")
    if raw.empty:
        raise ValueError("The limit worksheet is empty.")

    order_header = None
    for row_index in range(min(10, len(raw))):
        for column_index, value in enumerate(raw.iloc[row_index].tolist()):
            if isinstance(value, str) and value.strip().casefold() in {
                "harmonic order",
                "harmonic orders",
            }:
                order_header = (row_index, column_index)
                break
        if order_header:
            break
    if order_header is None:
        raise ValueError("Could not identify a Harmonic Order column in the limit worksheet.")

    header_row, order_column = order_header
    order_values = pd.to_numeric(raw.iloc[header_row + 1 :, order_column], errors="coerce")
    numeric_positions = order_values[order_values.notna()].index
    if len(numeric_positions) == 0:
        raise ValueError("No numeric harmonic orders were found in the limit worksheet.")
    data_start = int(numeric_positions[0])

    header_rows = raw.iloc[:data_start].copy()
    for row_index in range(len(header_rows)):
        previous_label = None
        for column_index in range(raw.shape[1]):
            if column_index == order_column:
                previous_label = None
                continue
            value = header_rows.iat[row_index, column_index]
            if _is_blank(value):
                has_data = any(
                    not _is_blank(cell)
                    for cell in raw.iloc[data_start:, column_index].tolist()
                )
                if previous_label is not None and has_data:
                    header_rows.iat[row_index, column_index] = previous_label
            else:
                previous_label = value

    labels: dict[int, str] = {}
    for column_index in range(raw.shape[1]):
        if column_index == order_column:
            continue
        parts: list[str] = []
        for value in header_rows.iloc[:, column_index].tolist():
            if _is_blank(value):
                continue
            label = str(value).strip()
            if label and not label.casefold().startswith("unnamed") and label not in parts:
                parts.append(label)
        labels[column_index] = " — ".join(parts)

    body = raw.iloc[data_start:].copy()
    body = _drop_fully_blank_rows(body)
    output_columns = ["Harmonic Order"]
    source_columns = [order_column]
    for column_index, label in labels.items():
        source_columns.append(column_index)
        output_columns.append(label)

    parsed = body.iloc[:, source_columns].copy()
    parsed.columns = output_columns
    return parsed.reset_index(drop=True)


def matched_conditions(filename: str, conditions: pd.DataFrame) -> list[tuple[str, str]]:
    """Return filename tokens that exactly match the Conditions worksheet."""
    required = {"Token", "Description"}
    if not required.issubset(conditions.columns):
        return []
    descriptions = dict(zip(conditions["Token"], conditions["Description"]))
    return [
        (token, descriptions[token])
        for token in Path(filename).stem.split("_")
        if token in descriptions and token
    ]
