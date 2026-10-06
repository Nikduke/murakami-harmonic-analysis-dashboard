from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import plotting


APP_DIR = Path(__file__).resolve().parents[1]
APP_PATH = APP_DIR / "app.py"
DEFAULT_INPUT_DIR = APP_DIR / "Input_files"
SAMPLE_INPUT_DIR = APP_DIR / "Input_files_2"


def _dashboard_with_inputs(initial_state: dict[str, object] | None = None) -> AppTest:
    app = AppTest.from_file(str(APP_PATH), default_timeout=45)
    if initial_state:
        for key, value in initial_state.items():
            app.session_state[key] = value
    app.run()
    if not list(DEFAULT_INPUT_DIR.glob("*.xlsx")):
        sample_files = sorted(SAMPLE_INPUT_DIR.glob("*.xlsx"))
        if not sample_files:
            pytest.skip("Dashboard UI checks need workbooks in Input_files or Input_files_2.")
        app.file_uploader[0].set_value(
            [
                (
                    path.name,
                    path.read_bytes(),
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
                for path in sample_files
            ]
        )
        app.run()
    return app


def test_display_defaults_override_prior_checkbox_state_after_workbook_upload(monkeypatch):
    spectrum_figures = []
    thd_figures = []
    original_spectrum_builder = plotting.build_harmonic_figure
    original_thd_builder = plotting.build_thd_figure

    def capture_spectrum(*args, **kwargs):
        figure = original_spectrum_builder(*args, **kwargs)
        spectrum_figures.append(figure)
        return figure

    def capture_thd(*args, **kwargs):
        figure = original_thd_builder(*args, **kwargs)
        thd_figures.append(figure)
        return figure

    monkeypatch.setattr(plotting, "build_harmonic_figure", capture_spectrum)
    monkeypatch.setattr(plotting, "build_thd_figure", capture_thd)
    app = _dashboard_with_inputs(
        {
            "auto_y_limits": False,
            "auto_y_limits_v2": False,
            "auto_y_limits_v3": False,
            "show_all_harmonic_numbers": False,
            "show_all_harmonic_numbers_v2": False,
        }
    )

    assert not app.exception
    assert app.checkbox(key="auto_y_limits_v4").value is True
    assert app.checkbox(key="show_all_harmonic_numbers_v3").value is True
    assert not app.number_input
    assert spectrum_figures
    assert thd_figures
    assert spectrum_figures[-1].layout.xaxis.tickmode == "array"
    assert len(spectrum_figures[-1].layout.xaxis.tickvals) > 1

    app.checkbox(key="auto_y_limits_v4").uncheck().run()
    assert app.checkbox(key="auto_y_limits_v4").value is False
    assert app.number_input(key="spectrum_y_max_input").value > 0
    assert app.number_input(key="thd_y_max_input").value > 0
    assert list(spectrum_figures[-1].layout.yaxis.range) == [
        0,
        app.session_state["spectrum_y_max_value"],
    ]
    assert list(thd_figures[-1].layout.yaxis.range) == [
        0,
        app.session_state["thd_y_max_value"],
    ]
    app.number_input(key="spectrum_y_max_input").set_value(8.0).run()
    assert list(spectrum_figures[-1].layout.yaxis.range) == [0, 8.0]
    assert app.checkbox(key="show_all_harmonic_numbers_v3").value is True
    assert not app.exception


def test_dashboard_startup_and_global_controls():
    app = _dashboard_with_inputs()

    assert not app.exception
    assert app.header[0].value == "Harmonic Analysis Dashboard"
    case_summary = next(
        element.value
        for element in app.caption
        if "result cases |" in element.value
    )
    assert "result cases |" in case_summary
    if "42 unmapped" in case_summary:
        assert any("42 result cases have no case-mapping entry" in element.value for element in app.warning)
    dashboard_context = next(
        element.value
        for element in app.markdown
        if element.value.startswith("**Dataset conditions:**")
    )
    assert "**Dataset conditions:**" in dashboard_context
    assert "Harmonic orders - 2–50" in dashboard_context
    assert "**Location:** TSO_BB1" in dashboard_context
    assert "**Limit:** None" in dashboard_context
    assert "Interactive harmonic-voltage results viewer" not in [
        element.value for element in app.caption
    ]
    assert app.checkbox(key="show_all_harmonic_numbers_v3").value is True
    assert app.checkbox(key="auto_y_limits_v4").value is True
    app.session_state["auto_y_limits"] = False
    app.run()
    assert app.checkbox(key="auto_y_limits_v4").value is True
    assert not app.number_input
    assert len(app.get("divider")) == 1
    assert len(app.radio) == 3
    assert len(app.multiselect) == 1
    assert len(app.multiselect[0].options) == 6
    assert app.multiselect[0].value == app.multiselect[0].options[2:]

    dataset_selector = app.radio(key="result_dataset")
    assert len(dataset_selector.options) == 2
    location_options = app.radio(key="result_location").options
    limit_key_prefix = "limit_series::Limits_IEC61000_3_6.xlsx::"
    limit_key = f"{limit_key_prefix}{location_options[0]}"
    limit_options = app.radio(key=limit_key).options
    assert location_options == ["TSO_BB1", "BB2_66kV", "BB1_66kV"]
    assert len(limit_options) == 4
    assert limit_options[0] == "No limit"

    app.radio(key=limit_key).set_value(limit_options[1]).run()
    assert (
        app.session_state["limit_series_active::Limits_IEC61000_3_6.xlsx"]
        == limit_options[1]
    )
    assert len(app.radio) == 4
    assert app.radio(key="limit_display").value == "Bars"
    sidebar_children = list(app.sidebar.children.values())
    sidebar_order = {
        child.key: index
        for index, child in enumerate(sidebar_children)
        if getattr(child, "key", None)
    }
    divider_index = next(
        index for index, child in enumerate(sidebar_children) if child.type == "divider"
    )
    assert sidebar_order["limit_display"] < divider_index
    assert divider_index < sidebar_order["auto_y_limits_v4"]
    assert sidebar_order["auto_y_limits_v4"] < sidebar_order["show_all_harmonic_numbers_v3"]
    app.radio(key="limit_display").set_value("Dashes").run()
    app.checkbox(key="auto_y_limits_v4").uncheck().run()
    assert app.number_input(key="spectrum_y_max_input").value > 0
    assert app.number_input(key="thd_y_max_input").value > 0
    app.number_input(key="spectrum_y_max_input").set_value(0.000001).run()
    assert any("Spectrum values reach" in element.value for element in app.warning)
    app.number_input(key="thd_y_max_input").set_value(0.000001).run()
    assert any("THD values reach" in element.value for element in app.warning)
    sidebar_children = list(app.sidebar.children.values())
    sidebar_order = {
        child.key: index
        for index, child in enumerate(sidebar_children)
        if getattr(child, "key", None)
    }
    assert sidebar_order["auto_y_limits_v4"] < sidebar_order["spectrum_y_max_input"]
    assert sidebar_order["spectrum_y_max_input"] < sidebar_order["thd_y_max_input"]
    assert sidebar_order["thd_y_max_input"] < sidebar_order["show_all_harmonic_numbers_v3"]
    app.checkbox(key="auto_y_limits_v4").check().run()
    assert not app.number_input
    assert not any("Spectrum values reach" in element.value for element in app.warning)
    app.checkbox(key="auto_y_limits_v4").uncheck().run()
    assert app.number_input(key="spectrum_y_max_input").value == 0.000001
    assert app.number_input(key="thd_y_max_input").value == 0.000001
    assert any("Spectrum values reach" in element.value for element in app.warning)
    assert any("THD values reach" in element.value for element in app.warning)
    app.checkbox(key="show_all_harmonic_numbers_v3").check().run()
    assert app.radio(key="limit_display").value == "Dashes"
    assert app.checkbox(key="show_all_harmonic_numbers_v3").value is True
    assert not app.exception

    assigned_limits = {}
    for index, location in enumerate(location_options):
        app.radio(key="result_location").set_value(location).run()
        location_limit_key = f"{limit_key_prefix}{location}"
        location_limit = app.radio(key=location_limit_key)
        assert location_limit.options == limit_options
        if index:
            assert location_limit.value == assigned_limits[location_options[index - 1]]
        selected_series = (
            limit_options[index + 1]
            if index + 1 < len(limit_options)
            else limit_options[0]
        )
        app.radio(key=location_limit_key).set_value(selected_series).run()
        assigned_limits[location] = selected_series
        assert not app.exception
    for location in location_options:
        app.radio(key="result_location").set_value(location).run()
        assert (
            app.radio(key=f"{limit_key_prefix}{location}").value
            == assigned_limits[location]
        )
    for widget in list(app.multiselect):
        available_cases = widget.options[2:]
        if len(available_cases) > 1:
            widget.set_value(available_cases[:2]).run()
            assert not app.exception

    group = "Intact"
    case_key = next(
        widget.key for widget in app.multiselect if widget.key.endswith(f"::{group}")
    )
    clear_option = "__dashboard_action_clear_all__"
    select_option = "__dashboard_action_select_all__"
    app.multiselect(key=case_key).set_value([clear_option]).run()
    assert app.multiselect(key=case_key).value == []
    app.multiselect(key=case_key).set_value([select_option]).run()
    assert app.multiselect(key=case_key).value == app.multiselect(key=case_key).options[2:]
    assert not app.exception
    app.button(key="open_chart_download").click().run()
    for location in location_options:
        export_limit_key = f"download_limit_series::Limits_IEC61000_3_6.xlsx::{location}"
        assert app.selectbox(key=export_limit_key).value == assigned_limits[location]


def test_live_limit_selection_carries_forward_and_remembers_bus_choices():
    app = _dashboard_with_inputs()
    locations = app.radio(key="result_location").options
    source_name = "Limits_IEC61000_3_6.xlsx"
    limit_key_prefix = f"limit_series::{source_name}::"
    limit_options = app.radio(key=limit_key_prefix + locations[0]).options

    first_series = limit_options[1]
    app.radio(key=limit_key_prefix + locations[0]).set_value(first_series).run()
    assert app.session_state[f"limit_series_active::{source_name}"] == first_series
    # Older sessions saved an untouched default as if the user had selected it.
    app.session_state[
        f"limit_series_selection::{source_name}::{locations[1]}"
    ] = "No limit"
    app.radio(key="result_location").set_value(locations[1]).run()
    assert app.radio(key=limit_key_prefix + locations[1]).value == first_series

    second_series = limit_options[2]
    app.radio(key=limit_key_prefix + locations[1]).set_value(second_series).run()
    app.radio(key="result_location").set_value(locations[0]).run()
    assert app.radio(key=limit_key_prefix + locations[0]).value == first_series
    app.radio(key="result_location").set_value(locations[1]).run()
    assert app.radio(key=limit_key_prefix + locations[1]).value == second_series
    app.radio(key="result_location").set_value(locations[2]).run()
    assert app.radio(key=limit_key_prefix + locations[2]).value == second_series
    app.radio(key=limit_key_prefix + locations[2]).set_value("No limit").run()
    app.radio(key="result_location").set_value(locations[1]).run()
    app.radio(key="result_location").set_value(locations[2]).run()
    assert app.radio(key=limit_key_prefix + locations[2]).value == "No limit"
    assert not app.exception


def test_clearing_uploaded_files_resets_the_app_without_a_session_state_error():
    app = _dashboard_with_inputs()
    assert not app.exception
    assert app.session_state["uploaded_workbooks"]

    clear_button = next(button for button in app.button if button.label == "Clear uploaded files")
    clear_button.click().run()

    assert not app.exception
    assert app.session_state["uploaded_workbooks"] == []
    assert app.session_state["show_chart_download_dialog"] is False
    if not list(DEFAULT_INPUT_DIR.glob("*.xlsx")):
        assert any("To start, click" in element.value for element in app.warning)


def test_group_tabs_toggle_preserves_case_selection():
    app = _dashboard_with_inputs()

    assert not app.exception
    assert app.checkbox(key="show_group_tabs").value is True
    group_count = len(app.tabs)
    assert group_count >= 5
    if "42 unmapped" in next(
        element.value for element in app.caption if "result cases |" in element.value
    ):
        assert "Unmapped" in [tab.label for tab in app.tabs]
    assert len(app.multiselect) == 1
    assert len(app.get("plotly_chart")) == 2

    first_group_key = app.multiselect[0].key
    first_group_selection = list(app.multiselect[0].value[:2])
    app.multiselect(key=first_group_key).set_value(first_group_selection).run()

    app.session_state["group_tabs"] = "TX out"
    app.run()
    assert len(app.multiselect) == 1
    assert app.multiselect[0].key.endswith("::TX out")
    assert first_group_key not in app.session_state

    app.session_state["group_tabs"] = "Intact"
    app.run()
    assert app.multiselect(key=first_group_key).value == first_group_selection

    app.checkbox(key="show_group_tabs").uncheck().run()
    assert app.checkbox(key="show_group_tabs").value is False
    assert len(app.tabs) == 0
    assert len(app.multiselect) == group_count
    assert len(app.get("plotly_chart")) == group_count * 2
    assert app.multiselect(key=first_group_key).value == first_group_selection

    app.checkbox(key="show_group_tabs").check().run()
    assert app.checkbox(key="show_group_tabs").value is True
    assert len(app.tabs) > 1
    assert app.multiselect(key=first_group_key).value == first_group_selection
    assert not app.exception


def test_download_dialog_exposes_dataset_case_and_output_controls():
    app = _dashboard_with_inputs()
    select_all = "__dashboard_action_select_all__"
    clear_all = "__dashboard_action_clear_all__"

    locations = app.radio(key="result_location").options
    limit_options = app.radio(
        key=f"limit_series::Limits_IEC61000_3_6.xlsx::{locations[0]}"
    ).options
    expected_limits = {}
    for index, location in enumerate(locations):
        app.radio(key="result_location").set_value(location).run()
        selected_series = limit_options[index + 1]
        app.radio(
            key=f"limit_series::Limits_IEC61000_3_6.xlsx::{location}"
        ).set_value(selected_series).run()
        expected_limits[location] = selected_series
    app.radio(key="result_location").set_value(locations[0]).run()

    app.button(key="open_chart_download").click().run()
    assert not app.exception
    assert app.checkbox(key="download_auto_y_limits_v2").value is True
    for location, expected_series in expected_limits.items():
        assert app.selectbox(
            key=f"download_limit_series::Limits_IEC61000_3_6.xlsx::{location}"
        ).value == expected_series
    dataset_selector = app.multiselect(key="download_datasets")
    dataset_labels = dataset_selector.options[2:]
    assert dataset_labels
    assert len(set(dataset_labels)) == len(dataset_labels)
    assert len(dataset_selector.value) == len(dataset_labels)
    app.multiselect(key="download_datasets").set_value([clear_all]).run()
    assert app.multiselect(key="download_datasets").value == []
    app.multiselect(key="download_datasets").set_value([select_all]).run()
    dataset_selector = app.multiselect(key="download_datasets")
    assert len(dataset_selector.value) == len(dataset_selector.options) - 2
    assert len(dataset_selector.value) == len(dataset_labels)
    assert app.checkbox(key="download_include_thd").value is True
    assert app.checkbox(key="download_split_by_folders").value is True

    dataset_name = dataset_selector.value[0].name
    location_key = f"download_locations::{dataset_name}"
    location_selector = app.multiselect(key=location_key)
    assert location_selector.value == location_selector.options[2:]
    app.multiselect(key=location_key).set_value([clear_all]).run()
    assert app.multiselect(key=location_key).value == []
    app.multiselect(key=location_key).set_value([select_all]).run()
    assert app.multiselect(key=location_key).value == app.multiselect(key=location_key).options[2:]

    group_key = f"download_groups::{dataset_name}"
    group_selector = app.multiselect(key=group_key)
    assert group_selector.value == group_selector.options[2:]
    case_groups = group_selector.options[2:]
    if "42 unmapped" in next(
        element.value for element in app.caption if "result cases |" in element.value
    ):
        assert "Unmapped" in case_groups
    app.multiselect(key=group_key).set_value([clear_all]).run()
    assert app.multiselect(key=group_key).value == []
    app.multiselect(key=group_key).set_value([select_all]).run()
    assert app.multiselect(key=group_key).value == app.multiselect(key=group_key).options[2:]

    all_cases_key = f"download_all_cases::{dataset_name}"
    assert app.checkbox(key=all_cases_key).value is True
    app.checkbox(key=all_cases_key).uncheck().run()
    assert not app.exception
    case_pickers = [
        widget for widget in app.multiselect
        if str(widget.key).startswith("download_case_picker::")
    ]
    assert len(case_pickers) == len(case_groups)
    assert all(widget.value == widget.options[2:] for widget in case_pickers)
    first_case_picker = case_pickers[0]
    app.multiselect(key=first_case_picker.key).set_value([clear_all]).run()
    assert app.multiselect(key=first_case_picker.key).value == []
    app.multiselect(key=first_case_picker.key).set_value([select_all]).run()
    assert app.multiselect(key=first_case_picker.key).value == app.multiselect(
        key=first_case_picker.key
    ).options[2:]
    assert app.button(key="prepare_chart_archive").label == "Prepare ZIP"

    limit_selectors = [
        widget for widget in app.selectbox
        if str(widget.key).startswith("download_limit_series::")
    ]
    if limit_selectors and len(limit_selectors[0].options) > 1:
        limit_selectors[0].select(limit_selectors[0].options[1]).run()
        assert not app.exception
        assert app.radio(key="download_limit_display").value == "Bars"


def test_download_y_axis_settings_start_from_live_and_remain_independent():
    app = _dashboard_with_inputs()
    app.checkbox(key="auto_y_limits_v4").uncheck().run()
    live_spectrum_max = app.number_input(key="spectrum_y_max_input").value
    live_thd_max = app.number_input(key="thd_y_max_input").value

    app.button(key="open_chart_download").click().run()
    assert not app.exception
    assert app.checkbox(key="download_auto_y_limits_v2").value is False
    assert app.number_input(key="download_spectrum_y_max_input").value == live_spectrum_max
    assert app.number_input(key="download_thd_y_max_input").value == live_thd_max

    app.number_input(key="download_spectrum_y_max_input").set_value(live_spectrum_max + 1).run()
    assert app.number_input(key="spectrum_y_max_input").value == live_spectrum_max
    assert app.number_input(key="download_spectrum_y_max_input").value == live_spectrum_max + 1
    app.checkbox(key="download_auto_y_limits_v2").check().run()
    assert "download_spectrum_y_max_input" not in [
        widget.key for widget in app.number_input
    ]
    app.checkbox(key="download_auto_y_limits_v2").uncheck().run()
    assert app.number_input(key="download_spectrum_y_max_input").value == live_spectrum_max + 1
    app.number_input(key="download_spectrum_y_max_input").set_value(0.000001).run()
    assert any(
        "The selected maxima crop data in" in element.value for element in app.warning
    )
    assert not app.exception
