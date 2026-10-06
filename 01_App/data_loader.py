"""Input-file discovery and Excel parsing for the Murakami dashboard."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import TypeAlias
from zipfile import BadZipFile, LargeZipFile, ZipFile

import pandas as pd


MAX_ZIP_MEMBERS = 100
MAX_ZIP_UNCOMPRESSED_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class UploadedWorkbook:
    """An Excel workbook held in memory for the current Streamlit session."""

    name: str
    content: bytes
    archive_name: str | None = None
    member_path: str | None = None

    @property
    def stem(self) -> str:
        return Path(self.name).stem


WorkbookSource: TypeAlias = Path | UploadedWorkbook


@dataclass(frozen=True)
class InputFiles:
    mapping: list[WorkbookSource]
    limits: list[WorkbookSource]
    results: list[WorkbookSource]


@dataclass(frozen=True)
class UploadExpansion:
    """Workbook members and user-facing issues found in the current uploads."""

    workbooks: list[UploadedWorkbook]
    archive_members: list[tuple[str, list[str]]]
    archive_errors: list[str]
    archive_warnings: list[str]
    duplicate_names: list[str]


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


def expand_uploaded_files(uploads: list[UploadedWorkbook]) -> UploadExpansion:
    """Expand uploaded ZIP archives into in-memory workbooks without extracting files."""
    workbooks: list[UploadedWorkbook] = []
    archive_members: list[tuple[str, list[str]]] = []
    archive_errors: list[str] = []
    archive_warnings: list[str] = []

    for upload in uploads:
        filename = Path(upload.name).name
        suffix = Path(filename).suffix.casefold()
        if suffix == ".xlsx":
            if not filename.startswith("~$"):
                workbooks.append(UploadedWorkbook(name=filename, content=upload.content))
            continue
        if suffix != ".zip":
            continue

        archive_workbooks: list[UploadedWorkbook] = []
        member_paths: list[str] = []
        try:
            with ZipFile(BytesIO(upload.content)) as archive:
                members = archive.infolist()
                if len(members) > MAX_ZIP_MEMBERS:
                    raise ValueError(
                        f"the archive has {len(members)} entries; the limit is "
                        f"{MAX_ZIP_MEMBERS}."
                    )
                uncompressed_bytes = sum(
                    member.file_size for member in members if not member.is_dir()
                )
                if uncompressed_bytes > MAX_ZIP_UNCOMPRESSED_BYTES:
                    limit_mib = MAX_ZIP_UNCOMPRESSED_BYTES // (1024 * 1024)
                    raise ValueError(
                        f"the archive expands to more than the {limit_mib} MiB limit."
                    )

                for member in members:
                    normalized_path = member.filename.replace("\\", "/")
                    member_path = PurePosixPath(normalized_path)
                    if (
                        member.is_dir()
                        or "__MACOSX" in member_path.parts
                        or member_path.name.startswith("~$")
                        or member_path.suffix.casefold() != ".xlsx"
                    ):
                        continue
                    if member.flag_bits & 0x1:
                        raise ValueError(
                            f"encrypted workbook `{member_path}` is not supported."
                        )

                    archive_workbooks.append(
                        UploadedWorkbook(
                            name=member_path.name,
                            content=archive.read(member),
                            archive_name=filename,
                            member_path=str(member_path),
                        )
                    )
                    member_paths.append(str(member_path))
        except (
            BadZipFile,
            LargeZipFile,
            OSError,
            RuntimeError,
            NotImplementedError,
            EOFError,
            ValueError,
        ) as exc:
            archive_errors.append(f"Could not read ZIP archive `{filename}`: {exc}")
            continue

        archive_members.append((filename, member_paths))
        workbooks.extend(archive_workbooks)
        if not archive_workbooks:
            archive_warnings.append(
                f"ZIP archive `{filename}` contains no supported `.xlsx` workbooks."
            )

    by_casefolded_name: dict[str, list[str]] = {}
    for workbook in workbooks:
        by_casefolded_name.setdefault(workbook.name.casefold(), []).append(workbook.name)
    duplicate_names = sorted(
        values[0]
        for values in by_casefolded_name.values()
        if len(values) > 1
    )

    return UploadExpansion(
        workbooks=workbooks,
        archive_members=archive_members,
        archive_errors=archive_errors,
        archive_warnings=archive_warnings,
        duplicate_names=duplicate_names,
    )


def merge_uploaded_workbooks(
    local_files: InputFiles, uploaded: list[UploadedWorkbook]
) -> InputFiles:
    """Add uploaded workbooks, preferring uploads with a matching filename.

    A single uploaded mapping workbook replaces the local mapping workbook(s).
    Uploaded limits and result workbooks extend their local lists.
    """
    valid_uploads = [
        workbook
        for workbook in uploaded
        if workbook.name.casefold().endswith(".xlsx")
        and not workbook.name.startswith("~$")
    ]
    uploaded_mappings = [
        workbook
        for workbook in valid_uploads
        if workbook.name.casefold().startswith("cases_description")
    ]
    uploaded_limits = [
        workbook
        for workbook in valid_uploads
        if workbook.name.casefold().startswith("limits_")
    ]
    uploaded_results = [
        workbook
        for workbook in valid_uploads
        if workbook not in uploaded_mappings and workbook not in uploaded_limits
    ]

    def combine(
        local: list[WorkbookSource], additions: list[WorkbookSource]
    ) -> list[WorkbookSource]:
        by_name = {workbook.name.casefold(): workbook for workbook in local}
        by_name.update({workbook.name.casefold(): workbook for workbook in additions})
        return sorted(by_name.values(), key=lambda workbook: workbook.name.casefold())

    mapping = uploaded_mappings or local_files.mapping
    return InputFiles(
        mapping=combine([], mapping),
        limits=combine(local_files.limits, uploaded_limits),
        results=combine(local_files.results, uploaded_results),
    )


def _excel_source(source: Path | bytes):
    return BytesIO(source) if isinstance(source, bytes) else source


def load_mapping(source: Path | bytes) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read the Cases and Conditions worksheets without rewriting their values."""
    with pd.ExcelFile(_excel_source(source), engine="openpyxl") as workbook:
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


def load_result_workbook(source: Path | bytes) -> dict[str, pd.DataFrame]:
    """Read each result sheet while retaining duplicate case headers for validation."""
    result_sheets: dict[str, pd.DataFrame] = {}
    with pd.ExcelFile(_excel_source(source), engine="openpyxl") as workbook:
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


def load_limits(source: Path | bytes) -> pd.DataFrame:
    """Parse a limit sheet with one or more rows of headers above its data."""
    raw = pd.read_excel(
        _excel_source(source), sheet_name=0, header=None, dtype=object, engine="openpyxl"
    )
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
