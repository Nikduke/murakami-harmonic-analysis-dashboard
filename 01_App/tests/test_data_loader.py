import os
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd
import pytest

from data_loader import (
    discover_input_files,
    load_limits,
    load_mapping,
    load_result_workbook,
    matched_conditions,
)
from plotting import build_group_data, build_harmonic_figure, limit_column_name


APP_DIR = Path(__file__).resolve().parents[1]
INPUT_DIR = APP_DIR / "Input_files"


def test_discovery_and_mapping_regression():
    files = discover_input_files(INPUT_DIR)
    assert [path.name for path in files.mapping] == ["Cases_description_UPD.xlsx"]
    assert [path.name for path in files.limits] == ["Limits_IEC61000_3_6.xlsx"]
    assert [path.name for path in files.results] == [
        "Total distortion_MinFLTSO_InjTSO_Nom_UPD.xlsx"
    ]

    cases, conditions = load_mapping(files.mapping[0])
    assert len(cases) == 52
    assert cases["Group"].value_counts().to_dict() == {
        "Intact energisation": 22,
        "TX out energisation": 22,
        "Intact": 4,
        "TX out": 4,
    }
    assert matched_conditions(files.results[0].name, conditions) == [
        ("MinFLTSO", "Minimum TSO fault level"),
        ("InjTSO", "TSO harmonic injection"),
        ("Nom", "Nominal parameters"),
    ]


def test_supplied_result_and_limit_regression():
    files = discover_input_files(INPUT_DIR)
    results = load_result_workbook(files.results[0])
    assert list(results) == ["TSO_BB1", "BB2_66kV", "BB1_66kV"]
    assert len(results["TSO_BB1"]) == 49
    assert results["TSO_BB1"].iloc[:, 0].tolist() == list(range(2, 51))

    case_a0 = results["TSO_BB1"].loc[results["TSO_BB1"].iloc[:, 0] == 5, "A.0"].item()
    assert case_a0 == pytest.approx(2.176775042841753)

    limits = load_limits(files.limits[0])
    series = "Planning Levels — HV-EHV (35 kV < Un)"
    assert series in limits.columns
    fifth_order_limit = limits.loc[pd.to_numeric(limits.iloc[:, 0]) == 5, series].item()
    assert fifth_order_limit == pytest.approx(2.0)
    aligned = build_group_data(results["TSO_BB1"], ["A.0"], limits, series)
    fifth_order = aligned.loc[aligned["Harmonic Order"] == 5].iloc[0]
    assert fifth_order["A.0"] == pytest.approx(2.176775042841753)
    assert fifth_order[limit_column_name(series)] == pytest.approx(2.0)


def test_excel_readers_release_file_handles():
    files = discover_input_files(INPUT_DIR)
    expected_cases, expected_conditions = load_mapping(files.mapping[0])
    expected_results = load_result_workbook(files.results[0])

    with TemporaryDirectory(dir=Path(__file__).parent) as temp_dir:
        temp_path = Path(temp_dir)
        mapping_copy = temp_path / files.mapping[0].name
        shutil.copy2(files.mapping[0], mapping_copy)
        actual_cases, actual_conditions = load_mapping(mapping_copy)
        os.replace(mapping_copy, temp_path / "mapping-renamed.xlsx")
        pd.testing.assert_frame_equal(actual_cases, expected_cases)
        pd.testing.assert_frame_equal(actual_conditions, expected_conditions)

        results_copy = temp_path / files.results[0].name
        shutil.copy2(files.results[0], results_copy)
        actual_results = load_result_workbook(results_copy)
        os.replace(results_copy, temp_path / "results-renamed.xlsx")
        assert actual_results.keys() == expected_results.keys()
        for sheet_name in expected_results:
            pd.testing.assert_frame_equal(actual_results[sheet_name], expected_results[sheet_name])


def test_synthetic_data_retains_harmonic_100_and_does_not_extend_limit():
    orders = list(range(2, 101))
    results = pd.DataFrame(
        {"Harmonic Order": orders, "A26": [order / 10 for order in orders]}
    )
    limits = pd.DataFrame(
        {
            "Harmonic Order": list(range(2, 51)),
            "Selected planning limit": [1.5] * 49,
        }
    )

    data = build_group_data(results, ["A26"], limits, "Selected planning limit")
    limit_column = limit_column_name("Selected planning limit")
    assert data["Harmonic Order"].tolist() == orders
    assert data.loc[data["Harmonic Order"] == 100, "A26"].item() == pytest.approx(10.0)
    assert pd.isna(data.loc[data["Harmonic Order"] == 100, limit_column].item())

    figure = build_harmonic_figure(data, {"A26": "Future mapped case"}, "Synthetic test")
    case_trace = next(trace for trace in figure.data if trace.name == "A26")
    limit_trace = next(
        trace
        for trace in figure.data
        if trace.name == "Selected planning limit" and trace.type == "scatter"
    )
    limit_bars = next(trace for trace in figure.data if trace.type == "bar")
    assert max(case_trace.x) == 100
    assert max(case_trace.y) == pytest.approx(10.0)
    assert case_trace.mode == "markers"
    assert case_trace.marker.symbol == "circle"
    assert case_trace.marker.size == 6
    assert limit_bars.width == 1.0
    assert limit_bars.marker.line.color == "rgba(255, 0, 0, 0.22)"
    assert limit_bars.showlegend is False
    assert limit_trace.mode == "markers"
    assert limit_trace.marker.symbol == "line-ew"
    assert limit_trace.marker.color == "#FF0000"
    assert limit_trace.marker.size == pytest.approx(6.5)
    assert limit_trace.legend == "legend2"
    assert figure.layout.legend2.y > figure.layout.legend.y
    assert figure.layout.xaxis.minallowed == 0


def test_figure_supports_short_limit_dashes_and_all_harmonic_ticks():
    data = pd.DataFrame(
        {
            "Harmonic Order": [2, 3, 4],
            "A.0": [0.1, 0.3, 0.6],
            limit_column_name("Selected planning limit"): [0.2, 0.4, 0.5],
        }
    )

    figure = build_harmonic_figure(
        data,
        {"A.0": "Test case"},
        "Synthetic test",
        limit_display="Dashes",
        show_all_harmonic_numbers=True,
    )

    limit_trace = next(trace for trace in figure.data if trace.name == "Selected planning limit")
    assert not any(trace.type == "bar" for trace in figure.data)
    assert limit_trace.marker.symbol == "line-ew"
    assert figure.layout.xaxis.tickmode == "array"
    assert list(figure.layout.xaxis.tickvals) == [2, 3, 4]


def test_file_classification_is_prefix_based():
    with TemporaryDirectory(dir=Path(__file__).parent) as temp_dir:
        input_dir = Path(temp_dir)
        for name in (
            "Cases_description_project.xlsx",
            "Limits_local.xlsx",
            "results_new.xlsx",
            "notes.txt",
            "~$temporary.xlsx",
        ):
            (input_dir / name).touch()
        files = discover_input_files(input_dir)
        assert [path.name for path in files.mapping] == ["Cases_description_project.xlsx"]
        assert [path.name for path in files.limits] == ["Limits_local.xlsx"]
        assert [path.name for path in files.results] == ["results_new.xlsx"]
