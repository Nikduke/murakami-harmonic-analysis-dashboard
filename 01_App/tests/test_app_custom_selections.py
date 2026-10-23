from custom_selection_ui import (
    ACTIVE_RULE_KEY,
    CASE_CONTEXT_KEY,
    IMPORT_STATUS_KEY,
    LIBRARY_KEY,
    SAVED_TABLE_GENERATION_KEY,
    SAVED_TABLE_KEY_PREFIX,
    custom_case_selection_key,
    custom_case_widget_key,
    render_custom_selection_manager,
)
from custom_selections import matching_case_codes, new_rule, serialise_library
from data_loader import load_mapping
from test_app_ui import SAMPLE_INPUT_DIR, _dashboard_with_inputs


def _custom_dashboard():
    app = _dashboard_with_inputs()
    assert "Custom selections" in [tab.label for tab in app.tabs]
    app.checkbox(key="show_group_tabs").uncheck().run()
    assert not app.exception
    return app


def _description_by_case():
    mapping_path = next(SAMPLE_INPUT_DIR.glob("Cases_description*.xlsx"))
    cases, _ = load_mapping(mapping_path)
    return dict(zip(cases["Case number"], cases["Description"]))


def _custom_chart_keys(app):
    dataset = app.session_state["result_dataset"].name
    location = app.session_state["result_location"]
    return {
        f"plot::{dataset}::{location}::Custom selections",
        f"thd_plot::{dataset}::{location}::Custom selections",
    }


def _create_filter(app, name="No 154 kV filters", phrase="no 154 kV Filters"):
    app.button(key="custom_new_selection").click().run()
    app.text_input(key="custom_editor_name").set_value(name).run()
    app.multiselect(key="custom_editor_all").set_value([phrase]).run()
    app.button(key="custom_save_selection").click().run()
    assert not app.exception
    return app.session_state[LIBRARY_KEY][0]


def test_custom_filter_updates_existing_chips_charts_and_context_selection():
    app = _custom_dashboard()
    rule = _create_filter(app)
    assert app.session_state[ACTIVE_RULE_KEY] == rule["id"]

    dataset = app.session_state["result_dataset"].name
    location = app.session_state["result_location"]
    case_key = custom_case_widget_key(dataset, location)
    selection_key = custom_case_selection_key(dataset, location)
    picker = app.multiselect(key=case_key)
    eligible = picker.options[2:]
    expected, _ = matching_case_codes(
        eligible,
        _description_by_case(),
        {"all": rule["all"], "any": rule["any"], "exclude": rule["exclude"]},
    )
    assert expected
    assert picker.value == expected
    assert app.session_state[selection_key] == expected
    assert _custom_chart_keys(app).issubset(
        {chart.key for chart in app.get("plotly_chart")}
    )

    narrowed = expected[:-1]
    app.multiselect(key=case_key).set_value(narrowed).run()
    assert app.multiselect(key=case_key).value == narrowed
    assert app.session_state[selection_key] == narrowed
    assert app.session_state[LIBRARY_KEY][0] == rule

    app.button(key="custom_restore_matches").click().run()
    assert app.multiselect(key=case_key).value == expected

    datasets = app.radio(key="result_dataset").options
    if len(datasets) > 1:
        app.multiselect(key=case_key).set_value(expected[:-1]).run()
        app.radio(key="result_dataset").set_value(datasets[1]).run()
        assert app.session_state[ACTIVE_RULE_KEY] == rule["id"]
        dataset = app.session_state["result_dataset"].name
        location = app.session_state["result_location"]
        case_key = custom_case_widget_key(dataset, location)
        eligible = app.multiselect(key=case_key).options[2:]
        expected_for_dataset, _ = matching_case_codes(
            eligible,
            _description_by_case(),
            {"all": rule["all"], "any": rule["any"], "exclude": rule["exclude"]},
        )
        assert app.multiselect(key=case_key).value == expected_for_dataset
        assert _custom_chart_keys(app).issubset(
            {chart.key for chart in app.get("plotly_chart")}
        )

    locations = app.radio(key="result_location").options
    if len(locations) > 1:
        app.multiselect(key=case_key).set_value(expected_for_dataset[:-1]).run()
        app.radio(key="result_location").set_value(locations[1]).run()
        assert app.session_state[ACTIVE_RULE_KEY] == rule["id"]
        dataset = app.session_state["result_dataset"].name
        location = app.session_state["result_location"]
        case_key = custom_case_widget_key(dataset, location)
        eligible = app.multiselect(key=case_key).options[2:]
        expected_for_location, _ = matching_case_codes(
            eligible,
            _description_by_case(),
            {"all": rule["all"], "any": rule["any"], "exclude": rule["exclude"]},
        )
        assert app.multiselect(key=case_key).value == expected_for_location
        assert _custom_chart_keys(app).issubset(
            {chart.key for chart in app.get("plotly_chart")}
        )
    assert not app.exception


def test_saved_table_row_activates_rule_and_blank_name_uses_rule_conditions():
    app = _custom_dashboard()
    first_rule = _create_filter(app, name="No filters", phrase="no 154 kV Filters")
    second_rule = _create_filter(app, name="No WTGs", phrase="no WTGs")

    table_key = (
        f"{SAVED_TABLE_KEY_PREFIX}::"
        f"{app.session_state[SAVED_TABLE_GENERATION_KEY]}"
    )
    app.session_state[table_key] = {"selection": {"rows": [0]}}
    app.run()
    assert app.session_state[ACTIVE_RULE_KEY] == first_rule["id"]
    assert app.dataframe(key=table_key) is not None
    dataset = app.session_state["result_dataset"].name
    location = app.session_state["result_location"]
    case_key = custom_case_widget_key(dataset, location)
    eligible = app.multiselect(key=case_key).options[2:]
    expected, _ = matching_case_codes(
        eligible,
        _description_by_case(),
        {
            "all": first_rule["all"],
            "any": first_rule["any"],
            "exclude": first_rule["exclude"],
        },
    )
    assert app.multiselect(key=case_key).value == expected

    app.button(key="custom_new_selection").click().run()
    app.multiselect(key="custom_editor_all").set_value(["5 strings"]).run()
    app.button(key="custom_save_selection").click().run()
    generated = app.session_state[LIBRARY_KEY][-1]
    assert generated["name"] == "5 strings"
    assert app.session_state[ACTIVE_RULE_KEY] == generated["id"]
    assert second_rule["id"] in {rule["id"] for rule in app.session_state[LIBRARY_KEY]}
    assert not app.exception


def test_edit_cancel_save_delete_and_clear_active_selection():
    app = _custom_dashboard()
    rule = _create_filter(app)
    original = app.session_state[LIBRARY_KEY][0].copy()

    app.button(key="custom_edit_selection").click().run()
    app.multiselect(key="custom_editor_all").set_value(["no WTGs"]).run()
    app.button(key="custom_cancel_editor").click().run()
    assert app.session_state[LIBRARY_KEY][0] == original
    assert app.session_state[ACTIVE_RULE_KEY] == rule["id"]

    app.button(key="custom_edit_selection").click().run()
    app.text_input(key="custom_editor_name").set_value("No WTGs").run()
    app.multiselect(key="custom_editor_all").set_value(["no WTGs"]).run()
    app.button(key="custom_save_selection").click().run()
    updated = app.session_state[LIBRARY_KEY][0]
    assert updated["id"] == rule["id"]
    assert updated["name"] == "No WTGs"
    assert updated["all"] == ["no WTGs"]

    app.button(key="custom_delete_selection").click().run()
    assert any("Delete" in item.value for item in app.warning)
    app.button(key="custom_cancel_delete").click().run()
    assert app.session_state[LIBRARY_KEY] == [updated]

    app.button(key="custom_delete_selection").click().run()
    app.button(key="custom_confirm_delete").click().run()
    assert app.session_state[LIBRARY_KEY] == []
    assert app.session_state[ACTIVE_RULE_KEY] is None

    rule = _create_filter(app, name="Five strings", phrase="5 strings")
    app.button(key="custom_clear_active_selection").click().run()
    assert app.session_state[ACTIVE_RULE_KEY] is None
    assert app.session_state[LIBRARY_KEY] == [rule]
    dataset = app.session_state["result_dataset"].name
    location = app.session_state["result_location"]
    case_key = custom_case_widget_key(dataset, location)
    assert app.multiselect(key=case_key).value == app.multiselect(key=case_key).options[2:]
    assert _custom_chart_keys(app).issubset(
        {chart.key for chart in app.get("plotly_chart")}
    )
    assert not app.exception


def test_import_replaces_library_only_after_valid_json_and_clears_active_rule():
    app = _custom_dashboard()
    assert app.get_by_key("custom_download_selections") is not None
    existing = _create_filter(app)
    replacement = new_rule("Imported rule", [], ["no WTGs"], [])
    upload_key = "custom_upload_selections::0"
    import_key = "custom_import_selections::0"

    app.file_uploader(key=upload_key).set_value(
        (
            "saved-selections.json",
            serialise_library([replacement]).encode("utf-8"),
            "application/json",
        )
    ).run()
    assert app.session_state[LIBRARY_KEY] == [existing]
    app.button(key=import_key).click().run()

    assert app.session_state[LIBRARY_KEY] == [replacement]
    assert app.session_state[ACTIVE_RULE_KEY] is None
    assert app.session_state[IMPORT_STATUS_KEY] == (
        "success",
        "Imported 1 saved selection(s).",
    )
    dataset = app.session_state["result_dataset"].name
    location = app.session_state["result_location"]
    case_key = custom_case_widget_key(dataset, location)
    assert app.multiselect(key=case_key).value == app.multiselect(key=case_key).options[2:]

    unchanged_library = app.session_state[LIBRARY_KEY].copy()
    app.file_uploader(key="custom_upload_selections::1").set_value(
        ("invalid.json", b"{not-json", "application/json")
    ).run()
    app.button(key="custom_import_selections::1").click().run()

    assert app.session_state[LIBRARY_KEY] == unchanged_library
    assert app.session_state[ACTIVE_RULE_KEY] is None
    assert any("not valid JSON" in item.value for item in app.error)
    assert not app.exception


def test_no_matches_has_no_stale_charts_and_stacked_layout_exposes_custom_view():
    app = _custom_dashboard()
    _create_filter(app, name="No matching description", phrase="not present in mapping")
    assert _custom_chart_keys(app).isdisjoint(
        {chart.key for chart in app.get("plotly_chart")}
    )
    assert any("No cases match" in item.value for item in app.info)

    app.button(key="custom_clear_active_selection").click().run()
    assert _custom_chart_keys(app).issubset(
        {chart.key for chart in app.get("plotly_chart")}
    )
    assert len(app.tabs) == 0
    assert app.button(key="custom_new_selection") is not None
    assert not app.exception


def test_active_rule_refreshes_when_case_codes_change_in_same_dataset_location():
    from streamlit.testing.v1 import AppTest

    rule = new_rule("Matching cases", ["match"], [], [])
    case_key = custom_case_widget_key("same-dataset", "same-location")
    selection_key = custom_case_selection_key("same-dataset", "same-location")

    def selection_app():
        import streamlit as st
        from custom_selection_ui import (
            custom_case_widget_key as app_case_widget_key,
            render_custom_selection_manager as app_selection_manager,
        )

        view = app_selection_manager(
            st.session_state["eligible_codes"],
            {"A": "match", "B": "other", "C": "match"},
            dataset_name="same-dataset",
            location="same-location",
        )
        st.multiselect(
            "Cases",
            options=view.case_codes,
            key=app_case_widget_key("same-dataset", "same-location"),
        )

    app = AppTest.from_function(selection_app)
    app.session_state[LIBRARY_KEY] = [rule]
    app.session_state[ACTIVE_RULE_KEY] = rule["id"]
    app.session_state["eligible_codes"] = ["A", "B"]
    app.run()
    assert app.multiselect(key=case_key).value == ["A"]

    app.session_state["eligible_codes"] = ["A", "B", "C"]
    app.run()
    assert app.multiselect(key=case_key).value == ["A", "C"]
    assert app.session_state[selection_key] == ["A", "C"]
    assert app.session_state[CASE_CONTEXT_KEY][0] == (
        "same-dataset",
        "same-location",
    )
    assert not app.exception
