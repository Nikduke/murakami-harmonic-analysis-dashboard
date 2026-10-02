"""Harmonic data alignment and Plotly figure generation."""

from __future__ import annotations

import math

import pandas as pd
import plotly.graph_objects as go


CASE_COLORS = [
    "#4472C4",
    "#ED7D31",
    "#70AD47",
    "#8064A2",
    "#5B9BD5",
    "#C0504D",
    "#00A6A6",
    "#A5A5A5",
    "#FFC000",
    "#365F91",
]
LIMIT_COLOR = "#FF0000"


def limit_column_name(series_name: str) -> str:
    return f"Limit — {series_name}"


def build_group_data(
    result: pd.DataFrame,
    selected_cases: list[str],
    limits: pd.DataFrame | None = None,
    limit_series: str | None = None,
) -> pd.DataFrame:
    """Select result traces and align an optional limit by harmonic order."""
    orders = pd.to_numeric(result.iloc[:, 0], errors="coerce")
    data = pd.DataFrame({"Harmonic Order": orders})
    for case_code in selected_cases:
        data[case_code] = pd.to_numeric(result[case_code], errors="coerce")
    data = data.sort_values("Harmonic Order", kind="stable").reset_index(drop=True)

    if limits is not None and limit_series and limit_series in limits.columns:
        limit_orders = pd.to_numeric(limits.iloc[:, 0], errors="coerce")
        limit_values = pd.to_numeric(limits[limit_series], errors="coerce")
        limit_lookup = pd.Series(limit_values.to_numpy(), index=limit_orders.to_numpy())
        column = limit_column_name(limit_series)
        data[column] = data["Harmonic Order"].map(limit_lookup)
    return data


def _nice_tick_step(span: float) -> float:
    if not math.isfinite(span) or span <= 0:
        return 1
    raw = span / 10
    magnitude = 10 ** math.floor(math.log10(raw))
    scaled = raw / magnitude
    preferred = 1 if scaled <= 1 else 2 if scaled <= 2 else 5 if scaled <= 5 else 10
    return preferred * magnitude


def build_harmonic_figure(
    data: pd.DataFrame,
    case_descriptions: dict[str, str],
    title: str,
    limit_display: str = "Bars",
    show_all_harmonic_numbers: bool = False,
) -> go.Figure:
    """Create a compact, interactive spectrum figure with source descriptions in hover."""
    figure = go.Figure()
    case_columns = [
        column
        for column in data.columns
        if column not in {"Harmonic Order"} and not str(column).startswith("Limit — ")
    ]
    x_values = data["Harmonic Order"].tolist() if "Harmonic Order" in data else []
    limit_columns = [column for column in data.columns if str(column).startswith("Limit — ")]

    if limit_display == "Bars":
        for column in limit_columns:
            figure.add_trace(
                go.Bar(
                    x=x_values,
                    y=data[column].tolist(),
                    width=1.0,
                    name=column.removeprefix("Limit — "),
                    marker={
                        "color": "rgba(255, 255, 255, 0)",
                        "line": {"color": "rgba(255, 0, 0, 0.22)", "width": 1},
                    },
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

    for index, case_code in enumerate(case_columns):
        description = case_descriptions.get(case_code, "")
        figure.add_trace(
            go.Scatter(
                x=x_values,
                y=data[case_code].tolist(),
                name=case_code,
                mode="markers",
                marker={"size": 8, "symbol": "circle", "opacity": 0.72},
                marker_color=CASE_COLORS[index % len(CASE_COLORS)],
                connectgaps=False,
                customdata=[description] * len(data),
                hovertemplate=(
                    "<b>%{fullData.name}</b> · "
                    "%{y:.5g} % · %{customdata}<extra></extra>"
                ),
            )
        )

    for column in limit_columns:
        figure.add_trace(
            go.Scatter(
                x=x_values,
                y=data[column].tolist(),
                name=column.removeprefix("Limit — "),
                mode="markers",
                legend="legend2",
                marker={
                    "size": 6.5,
                    "symbol": "line-ew",
                    "color": LIMIT_COLOR,
                    "line": {"color": LIMIT_COLOR, "width": 1.5},
                },
                connectgaps=False,
                hovertemplate="<b>%{fullData.name}</b> · %{y:.5g} %<extra></extra>",
            )
        )

    orders = pd.to_numeric(data.get("Harmonic Order", pd.Series(dtype=float)), errors="coerce").dropna()
    span = float(orders.max() - orders.min()) if not orders.empty else 0
    all_integral = bool(((orders % 1) == 0).all()) if not orders.empty else True
    figure.update_layout(
        title={"text": title, "x": 0, "xanchor": "left"},
        template="plotly_white",
        colorway=CASE_COLORS,
        height=505,
        margin={"l": 66, "r": 18, "t": 48, "b": 125},
        hovermode="x unified",
        hoverlabel={"bgcolor": "white", "font": {"color": "#20283C"}},
        legend={
            "orientation": "h",
            "x": 0,
            "xanchor": "left",
            "y": -0.34,
            "yanchor": "top",
            "itemsizing": "constant",
            "font": {"size": 11},
        },
        legend2={
            "orientation": "h",
            "x": 0,
            "xanchor": "left",
            "y": -0.22,
            "yanchor": "top",
            "itemsizing": "constant",
            "font": {"size": 11},
        },
        font={"family": "Calibri, Arial, sans-serif", "color": "#20283C", "size": 12},
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    x_axis_options = {
        "title_text": "Harmonic order",
        "showgrid": True,
        "gridcolor": "#E5E8EE",
        "zeroline": False,
        "tickformat": ".0f" if all_integral else ".2f",
        "minallowed": 0,
        "automargin": True,
    }
    if show_all_harmonic_numbers:
        x_axis_options.update(tickmode="array", tickvals=orders.tolist())
    else:
        x_axis_options["dtick"] = _nice_tick_step(span)
    x_axis_options["unifiedhovertitle_text"] = "<b>Harmonic order: %{x}</b>"
    figure.update_xaxes(
        **x_axis_options,
    )
    figure.update_yaxes(
        title_text="Harmonic voltage distortion (%)",
        showgrid=True,
        gridcolor="#E5E8EE",
        rangemode="tozero",
        zeroline=False,
        automargin=True,
    )
    return figure
