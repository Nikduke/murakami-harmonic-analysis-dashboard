from pathlib import Path

from streamlit.testing.v1 import AppTest


APP_DIR = Path(__file__).resolve().parents[1]
APP_PATH = APP_DIR / "app.py"


def test_dashboard_startup_and_global_controls():
    app = AppTest.from_file(str(APP_PATH), default_timeout=30).run()

    assert not app.exception
    assert app.header[0].value == "Murakami Harmonic Analysis Dashboard"
    assert "52 mapped cases · 52 result traces" in [element.value for element in app.caption]
    context_line = next(
        element.value
        for element in app.markdown
        if "Total distortion UPD" in element.value
    )
    assert "MinFLTSO · InjTSO · Nom · TSO_BB1" in context_line
    assert "Reference: no limit · Harmonic orders 2–50" in context_line
    assert not any(
        "Location: TSO_BB1 · Harmonic order" in element.value for element in app.caption
    )
    assert app.checkbox(key="show_all_harmonic_numbers").value is False
    assert len(app.radio) == 0
    assert len(app.multiselect) == 4
    assert [len(widget.options) for widget in app.multiselect] == [6, 24, 6, 24]
    assert all(widget.value == widget.options[2:] for widget in app.multiselect)

    location_options = app.selectbox(key="result_location").options
    limit_key = "limit_series::Limits_IEC61000_3_6.xlsx"
    limit_options = app.selectbox(key=limit_key).options
    assert location_options == ["TSO_BB1", "BB2_66kV", "BB1_66kV"]
    assert len(limit_options) == 4
    assert limit_options[0] == "No limit"

    app.selectbox(key=limit_key).select(limit_options[1]).run()
    assert len(app.radio) == 1
    assert app.radio(key="limit_display").value == "Bars"
    app.radio(key="limit_display").set_value("Dashes").run()
    app.checkbox(key="show_all_harmonic_numbers").check().run()
    assert app.radio(key="limit_display").value == "Dashes"
    assert app.checkbox(key="show_all_harmonic_numbers").value is True
    assert not app.exception

    for location in location_options:
        app.selectbox(key="result_location").select(location).run()
        assert not app.exception

    for limit_series in limit_options:
        app.selectbox(key=limit_key).select(limit_series).run()
        assert not app.exception

    for widget in list(app.multiselect):
        available_cases = widget.options[2:]
        if len(available_cases) > 1:
            widget.set_value(available_cases[:2]).run()
            assert not app.exception

    group = "Intact"
    case_key = f"cases::Total distortion_MinFLTSO_InjTSO_Nom_UPD.xlsx::BB1_66kV::{group}"
    clear_option = "__dashboard_action_clear_all__"
    select_option = "__dashboard_action_select_all__"
    app.multiselect(key=case_key).set_value([clear_option]).run()
    assert app.multiselect(key=case_key).value == []
    app.multiselect(key=case_key).set_value([select_option]).run()
    assert app.multiselect(key=case_key).value == app.multiselect(key=case_key).options[2:]
    assert not app.exception
