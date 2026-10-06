from chart_selection import cases_from_plot_state


def test_plot_point_selection_uses_case_legendgroup():
    state = {
        "selection": {
            "points": [
                {"curve_number": 2, "legendgroup": "A.1", "point_number": 4}
            ]
        }
    }

    assert cases_from_plot_state(state, ["A.0", "A.1"], {}) == ["A.1"]


def test_plot_point_selection_falls_back_to_case_trace_map():
    state = {"selection": {"points": [{"curve_number": 3}]}}

    assert cases_from_plot_state(state, ["A.0", "A.1"], {3: "A.0"}) == ["A.0"]


def test_plot_selection_ignores_non_case_traces_and_empty_selections():
    state = {
        "selection": {
            "points": [
                {"curve_number": 4},
                {"curve_number": 5, "legendgroup": "not-in-this-group"},
            ]
        }
    }

    assert cases_from_plot_state(state, ["A.0", "A.1"], {4: "A.0"}) == ["A.0"]
    assert cases_from_plot_state(
        {"selection": {"points": [{"curve_number": 5}]}}, ["A.0"], {}
    ) is None
    assert cases_from_plot_state(
        {"selection": {"points": []}}, ["A.0", "A.1"], {}
    ) == ["A.0", "A.1"]
    assert cases_from_plot_state(None, ["A.0"], {}) is None
