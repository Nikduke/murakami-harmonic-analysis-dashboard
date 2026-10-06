import warnings

import numpy as np
import pandas as pd

from plotting import build_group_data, build_harmonic_figure


def test_large_spectrum_compacts_hover_context_without_fragmentation():
    case_count = 125
    order_count = 1000
    orders = np.arange(2, order_count + 2)
    case_codes = [f"Case {index:03}" for index in range(case_count)]
    source = pd.DataFrame(
        {
            "Harmonic Order": orders,
            **{
                case_code: (index + np.arange(order_count)) % 31 / 7
                for index, case_code in enumerate(case_codes)
            },
        }
    )
    limits = pd.DataFrame(
        {"Harmonic Order": orders, "Planning Levels": np.full(order_count, 2.5)}
    )
    descriptions = {case: f"Description for {case}" for case in case_codes}

    with warnings.catch_warnings():
        warnings.simplefilter("error", pd.errors.PerformanceWarning)
        data = build_group_data(source, case_codes, limits, "Planning Levels")

    figure = build_harmonic_figure(data, descriptions, "Large synthetic spectrum")
    case_traces = [item for item in figure.data if item.name == case_codes[0]]

    assert len(case_traces) == 1
    assert case_traces[0].hoverlabel.font.color == "#20283C"
    assert sum(len(item.x) for item in case_traces) == order_count
    assert len(case_traces[0].customdata) == order_count
    assert {point[0] for point in case_traces[0].customdata} == {"#20283C", "#C00000"}
    assert isinstance(case_traces[0].customdata[0][1], int)
    assert all(item.meta == descriptions[case_codes[0]] for item in case_traces)
    assert "%{meta}" in case_traces[0].hovertemplate
    assert "<span style='color:%{customdata[0]}'" in case_traces[0].hovertemplate
    assert sum(
        item.showlegend is not False
        for item in figure.data
        if item.name in case_codes
    ) == case_count
    assert len(figure.to_json().encode("utf-8")) < 6 * 1024 * 1024
