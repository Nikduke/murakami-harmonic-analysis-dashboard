from pathlib import Path

import pandas as pd
import pytest

from data_loader import discover_input_files, load_limits, load_mapping, load_result_workbook
from validation import validate_limits, validate_mapping, validate_result


APP_DIR = Path(__file__).resolve().parents[1]
INPUT_DIR = APP_DIR / "Input_files"


def test_supplied_workbooks_pass_validation():
    files = discover_input_files(INPUT_DIR)
    if not files.results:
        files = discover_input_files(APP_DIR / "Input_files_2")
    if not files.results:
        pytest.skip("Supplied Excel workbooks are not present in this checkout.")
    cases, conditions = load_mapping(files.mapping[0])
    mapping_report = validate_mapping(cases, conditions)
    mapped_codes = set(cases["Case number"])

    results = load_result_workbook(files.results[0])
    result_reports = {
        name: validate_result(frame, mapped_codes, name)
        for name, frame in results.items()
    }
    limits = load_limits(files.limits[0])
    limit_report = validate_limits(limits, files.limits[0].name)

    assert mapping_report.is_valid, mapping_report.errors
    assert all(report.is_valid for report in result_reports.values())
    assert limit_report.is_valid, limit_report.errors


def test_result_validation_reports_unmapped_and_duplicate_inputs():
    results = pd.DataFrame(
        [
            [2, 1.0, 1.0, 1.0],
            [3, 2.0, 2.0, "bad"],
            [3, 3.0, 3.0, 3.0],
        ],
        columns=["Harmonic Order", "A.0", "A.0", "A99"],
    )
    report = validate_result(results, {"A.0"}, "Synthetic location")
    messages = " ".join(report.errors)
    assert "duplicate case column" in messages
    assert "duplicate harmonic order" in messages
    assert any("missing from the mapping" in message for message in report.warnings)
    assert "non-numeric result value" in messages


def test_unmapped_case_is_a_nonblocking_warning():
    results = pd.DataFrame(
        [[2, 1.0, 0.5], [3, 0.2, 0.1]],
        columns=["Harmonic Order", "A.0", "A130.1"],
    )

    report = validate_result(results, {"A.0"}, "Synthetic location")

    assert report.is_valid
    assert not report.errors
    assert len(report.warnings) == 1
    assert "Unmapped and All" in report.warnings[0]
    assert "A130.1" in report.warnings[0]


def test_limit_validation_allows_blank_values_but_rejects_duplicate_orders():
    limits = pd.DataFrame(
        {
            "Harmonic Order": [2, 3, 3],
            "Planning level": [1.0, None, 2.0],
        }
    )
    report = validate_limits(limits, "Synthetic limits")
    assert any("duplicate harmonic order" in message for message in report.errors)
    assert not any("non-numeric" in message for message in report.errors)
