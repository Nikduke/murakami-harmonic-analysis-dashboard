"""Map native Plotly point selections to case codes."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


def cases_from_plot_state(
    chart_state: Any,
    available_cases: Iterable[str],
    trace_case_codes: Mapping[int, str],
) -> list[str] | None:
    """Map point selection to one case, or restore the group after it is cleared."""
    if chart_state is None:
        return None

    available = list(available_cases)
    available_set = set(available)
    points = chart_state.get("selection", {}).get("points", [])
    for point in reversed(points):
        case_code = point.get("legendgroup")
        if case_code not in available_set:
            case_code = trace_case_codes.get(point.get("curve_number"))
        if case_code in available_set:
            return [case_code]
    if points:
        return None
    return available
