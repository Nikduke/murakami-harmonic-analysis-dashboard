import os
import shutil
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd
import pytest

from data_loader import (
    InputFiles,
    UploadedWorkbook,
    discover_input_files,
    expand_uploaded_files,
    load_limits,
    load_mapping,
    load_result_workbook,
    matched_conditions,
    merge_uploaded_workbooks,
)
from plotting import (
    build_group_data,
    build_harmonic_figure,
    build_thd_figure,
    limit_column_name,
)


APP_DIR = Path(__file__).resolve().parents[1]
INPUT_DIR = APP_DIR / "Input_files"
REGRESSION_WORKBOOK_NAMES = {
    "Cases_description_UPD.xlsx",
    "Limits_IEC61000_3_6.xlsx",
    "Total distortion_MinFLTSO_InjTSO_Max.xlsx",
    "Total distortion_MinFLTSO_InjTSO_Min.xlsx",
    "Total distortion_MinFLTSO_InjTSO_Nom.xlsx",
}


def _regression_input_files():
    for directory in (INPUT_DIR, APP_DIR / "Input_files_1"):
        files = discover_input_files(directory)
        workbook_names = {
            path.name for paths in (files.mapping, files.limits, files.results) for path in paths
        }
        if REGRESSION_WORKBOOK_NAMES.issubset(workbook_names):
            return files
    pytest.skip("The regression workbook set is not present in this checkout.")


def _result_workbook_bytes() -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        pd.DataFrame({"Harmonic Order": [2, 3], "A.0": [0.1, 0.2]}).to_excel(
            writer, sheet_name="TSO_BB1", index=False
        )
    return buffer.getvalue()


def _zip_bytes(members: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        for name, content in members.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_discovery_and_mapping_regression():
    files = _regression_input_files()
    assert [path.name for path in files.mapping] == ["Cases_description_UPD.xlsx"]
    assert [path.name for path in files.limits] == ["Limits_IEC61000_3_6.xlsx"]
    assert [path.name for path in files.results] == [
        "Total distortion_MinFLTSO_InjTSO_Max.xlsx",
        "Total distortion_MinFLTSO_InjTSO_Min.xlsx",
        "Total distortion_MinFLTSO_InjTSO_Nom.xlsx",
    ]

    cases, conditions = load_mapping(files.mapping[0])
    assert len(cases) == 52
    assert cases["Group"].value_counts().to_dict() == {
        "Intact energisation": 22,
        "TX out energisation": 22,
        "Intact": 4,
        "TX out": 4,
    }
    nominal_result = next(path for path in files.results if path.stem.endswith("_Nom"))
    assert matched_conditions(nominal_result.name, conditions) == [
        ("MinFLTSO", "Minimum TSO fault level"),
        ("InjTSO", "TSO harmonic injection"),
        ("Nom", "Nominal parameters"),
    ]


def test_supplied_result_and_limit_regression():
    files = _regression_input_files()
    nominal_result = next(path for path in files.results if path.stem.endswith("_Nom"))
    results = load_result_workbook(nominal_result)
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


def test_supplied_limit_hover_has_one_correct_entry_per_case():
    files = _regression_input_files()
    nominal_result = next(path for path in files.results if path.stem.endswith("_Nom"))
    results = load_result_workbook(nominal_result)
    cases, _ = load_mapping(files.mapping[0])
    selected_cases = cases.loc[cases["Group"] == "Intact", "Case number"].astype(str).tolist()
    limits = load_limits(files.limits[0])
    series = "Planning Levels — HV-EHV (35 kV < Un)"
    data = build_group_data(results["TSO_BB1"], selected_cases, limits, series)

    figure = build_harmonic_figure(data, {}, "Supplied-data hover regression")
    case_traces = [trace for trace in figure.data if trace.name in selected_cases]
    order_five = data.loc[data["Harmonic Order"] == 5].iloc[0]
    order_five_limit = order_five[limit_column_name(series)]

    assert len(case_traces) == len(selected_cases)
    for trace in case_traces:
        orders = list(trace.x)
        assert orders.count(5) == 1
        order_index = orders.index(5)
        case_value = order_five[trace.name]
        assert trace.y[order_index] == pytest.approx(case_value)
        assert trace.customdata[order_index] == (
            "#C00000" if case_value > order_five_limit else "#20283C"
        )

    assert figure.layout.hovermode == "x unified"
    assert figure.layout.hoversort == "value descending"
    assert figure.data[-1].name == series
    assert figure.data[-1].marker.symbol == "line-ew"
    assert figure.data[-1].marker.color == "#FF0000"
    assert "─" not in figure.data[-1].hovertemplate


def test_harmonic_and_thd_text_colors_are_explicit_on_white_plot_surfaces():
    harmonic_data = pd.DataFrame(
        {
            "Harmonic Order": [2, 3],
            "A.0": [0.1, 0.3],
        }
    )
    harmonic_figure = build_harmonic_figure(
        harmonic_data, {}, "Harmonic spectrum"
    )
    thd_figure = build_thd_figure(
        pd.DataFrame(
            {
                "Case": ["A.0"],
                "Description": ["Reference"],
                "THD (%)": [0.32],
                "Missing orders": [[]],
            }
        ),
        ["A.0"],
        "Voltage THD",
    )

    for figure in (harmonic_figure, thd_figure):
        assert figure.layout.paper_bgcolor == "white"
        assert figure.layout.plot_bgcolor == "white"
        assert figure.layout.title.font.color == "#20283C"
        assert figure.layout.xaxis.tickfont.color == "#20283C"
        assert figure.layout.yaxis.tickfont.color == "#20283C"
        assert figure.layout.xaxis.title.font.color == "#20283C"
        assert figure.layout.yaxis.title.font.color == "#20283C"

    assert harmonic_figure.layout.legend.font.color == "#20283C"
    assert thd_figure.data[0].textfont.color == "#20283C"


def test_manual_y_axis_maxima_are_shared_as_zero_based_ranges():
    harmonic_figure = build_harmonic_figure(
        pd.DataFrame({"Harmonic Order": [2, 3], "A.0": [0.1, 0.3]}),
        {},
        "Harmonic spectrum",
        y_axis_max=8.0,
    )
    thd_figure = build_thd_figure(
        pd.DataFrame(
            {"Case": ["A.0"], "Description": [""], "THD (%)": [0.32], "Missing orders": [[]]}
        ),
        ["A.0"],
        "Voltage THD",
        y_axis_max=3.5,
    )

    assert list(harmonic_figure.layout.yaxis.range) == [0, 8.0]
    assert list(thd_figure.layout.yaxis.range) == [0, 3.5]


def test_auto_y_axis_ranges_remain_automatic_by_default():
    harmonic_figure = build_harmonic_figure(
        pd.DataFrame({"Harmonic Order": [2, 3], "A.0": [0.1, 0.3]}),
        {},
        "Harmonic spectrum",
    )
    thd_figure = build_thd_figure(
        pd.DataFrame(
            {"Case": ["A.0"], "Description": [""], "THD (%)": [0.32], "Missing orders": [[]]}
        ),
        ["A.0"],
        "Voltage THD",
    )

    assert harmonic_figure.layout.yaxis.range is None
    assert harmonic_figure.layout.yaxis.rangemode == "tozero"
    assert list(thd_figure.layout.yaxis.range) == [0, 0.3776]


def test_excel_readers_release_file_handles():
    files = _regression_input_files()
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


def test_limit_hover_row_uses_red_dash_trace_symbol():
    data = pd.DataFrame(
        {
            "Harmonic Order": [7],
            "A.0": [0.5],
            limit_column_name("Planning Levels"): [4.0],
        }
    )
    figure = build_harmonic_figure(data, {}, "Synthetic test")
    limit_trace = next(
        trace
        for trace in figure.data
        if trace.name == "Planning Levels" and trace.type == "scatter"
    )
    limit_hover_trace = next(
        trace
        for trace in figure.data
        if trace.name == "Planning Levels"
        and trace.type == "scatter"
        and trace.showlegend is False
    )

    assert limit_trace.hoverinfo == "skip"
    assert limit_hover_trace.marker.symbol == "line-ew"
    assert limit_hover_trace.marker.color == "#FF0000"
    assert limit_hover_trace.marker.size == pytest.approx(6.5)
    assert limit_hover_trace.marker.opacity == 0
    assert limit_hover_trace.marker.line.color == "#FF0000"
    assert limit_hover_trace.marker.line.width == pytest.approx(1.5)
    assert limit_hover_trace.y == (0.5,)
    assert limit_hover_trace.hovertemplate == (
        "<b>%{fullData.name}</b> · %{customdata:.5g} %<extra></extra>"
    )
    assert figure.layout.hovermode == "x unified"
    assert figure.layout.hoversort == "value descending"


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
    limit_hover_trace = next(
        trace
        for trace in figure.data
        if trace.name == "Selected planning limit"
        and trace.type == "scatter"
        and trace.showlegend is False
    )
    limit_bars = next(trace for trace in figure.data if trace.type == "bar")
    assert max(case_trace.x) == 100
    assert max(case_trace.y) == pytest.approx(10.0)
    assert case_trace.mode == "markers"
    assert case_trace.marker.symbol == "circle"
    assert case_trace.marker.size == 8
    assert case_trace.marker.opacity == pytest.approx(0.72)
    assert case_trace.hovertemplate == (
        "<span style='color:%{customdata}'><b>%{fullData.name}</b> · "
        "%{y:.5g} % · %{meta}</span><extra></extra>"
    )
    assert case_trace.meta == "Future mapped case"
    assert case_trace.customdata[0] == "#20283C"
    assert case_trace.customdata[14] == "#C00000"
    assert case_trace.customdata[-1] == "#20283C"
    assert limit_bars.width == 1.0
    assert limit_bars.marker.color == "rgba(112, 173, 71, 0.08)"
    assert limit_bars.marker.line.color is None
    assert limit_bars.showlegend is False
    assert limit_trace.mode == "markers"
    assert limit_trace.marker.symbol == "line-ew"
    assert limit_trace.marker.color == "#FF0000"
    assert limit_trace.marker.size == pytest.approx(6.5)
    assert limit_trace.hoverinfo == "skip"
    assert limit_hover_trace.marker.size == pytest.approx(6.5)
    assert limit_hover_trace.marker.opacity == 0
    assert limit_hover_trace.hovertemplate == (
        "<b>%{fullData.name}</b> · %{customdata:.5g} %<extra></extra>"
    )
    assert limit_trace.legend == "legend2"
    assert figure.layout.legend2.y > figure.layout.legend.y
    assert figure.layout.xaxis.minallowed == 0
    assert figure.layout.xaxis.unifiedhovertitle.text == "<b>Harmonic order: %{x}</b>"


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


def test_zip_upload_expands_nested_workbooks_and_matches_individual_uploads():
    result_bytes = _result_workbook_bytes()
    archive_bytes = _zip_bytes(
        {
            "project/Cases_description_project.xlsx": b"mapping workbook",
            "project/Limits_IEC61000_3_6.xlsx": b"limits workbook",
            "project/results/Total distortion_case.xlsx": result_bytes,
            "project/notes.csv": b"ignored",
            "__MACOSX/._hidden.xlsx": b"ignored",
            "project/~$temporary.xlsx": b"ignored",
        }
    )

    direct_expansion = expand_uploaded_files(
        [UploadedWorkbook(name="Total distortion_case.xlsx", content=result_bytes)]
    )
    archive_expansion = expand_uploaded_files(
        [
            UploadedWorkbook(name="workbook_set.zip", content=archive_bytes),
            UploadedWorkbook(name="Total distortion_extra.xlsx", content=result_bytes),
        ]
    )

    assert not direct_expansion.archive_errors
    assert not archive_expansion.archive_errors
    assert not archive_expansion.duplicate_names
    assert [name for _, name in archive_expansion.archive_members] == [
        [
            "project/Cases_description_project.xlsx",
            "project/Limits_IEC61000_3_6.xlsx",
            "project/results/Total distortion_case.xlsx",
        ]
    ]

    empty = InputFiles(mapping=[], limits=[], results=[])
    direct_files = merge_uploaded_workbooks(empty, direct_expansion.workbooks)
    archive_files = merge_uploaded_workbooks(empty, archive_expansion.workbooks)
    assert [workbook.name for workbook in archive_files.mapping] == [
        "Cases_description_project.xlsx"
    ]
    assert [workbook.name for workbook in archive_files.limits] == [
        "Limits_IEC61000_3_6.xlsx"
    ]
    assert [workbook.name for workbook in archive_files.results] == [
        "Total distortion_case.xlsx",
        "Total distortion_extra.xlsx",
    ]
    pd.testing.assert_frame_equal(
        load_result_workbook(direct_files.results[0].content)["TSO_BB1"],
        load_result_workbook(archive_files.results[0].content)["TSO_BB1"],
    )


def test_zip_upload_reports_duplicate_basenames():
    archive_bytes = _zip_bytes(
        {
            "first/Total distortion_case.xlsx": b"first workbook",
            "second/total distortion_case.xlsx": b"second workbook",
        }
    )

    expansion = expand_uploaded_files(
        [UploadedWorkbook(name="workbook_set.zip", content=archive_bytes)]
    )

    assert expansion.duplicate_names == ["Total distortion_case.xlsx"]
    assert len(expansion.workbooks) == 2


def test_zip_upload_reports_invalid_archive_and_size_limits(monkeypatch):
    invalid = expand_uploaded_files(
        [UploadedWorkbook(name="broken.zip", content=b"not a ZIP archive")]
    )
    assert not invalid.workbooks
    assert "Could not read ZIP archive `broken.zip`" in invalid.archive_errors[0]

    monkeypatch.setattr("data_loader.MAX_ZIP_MEMBERS", 1)
    too_many_members = expand_uploaded_files(
        [
            UploadedWorkbook(
                name="large.zip",
                content=_zip_bytes({"one.txt": b"1", "two.txt": b"2"}),
            )
        ]
    )
    assert not too_many_members.workbooks
    assert "the limit is 1" in too_many_members.archive_errors[0]

    monkeypatch.setattr("data_loader.MAX_ZIP_MEMBERS", 100)
    monkeypatch.setattr("data_loader.MAX_ZIP_UNCOMPRESSED_BYTES", 1024 * 1024)
    too_large = expand_uploaded_files(
        [
            UploadedWorkbook(
                name="large.zip",
                content=_zip_bytes({"payload.bin": b"x" * (1024 * 1024 + 1)}),
            )
        ]
    )
    assert not too_large.workbooks
    assert "more than the 1 MiB limit" in too_large.archive_errors[0]
