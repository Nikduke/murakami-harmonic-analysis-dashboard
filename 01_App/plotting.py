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
PLOT_TEXT_COLOR = "#20283C"
VIOLATION_TEXT_COLOR = "#C00000"
THD_MAX_ORDER = 50
PLOT_HEIGHT = 505
PLOT_TITLE_LEFT_PADDING = 12


def limit_column_name(series_name: str) -> str:
    return f"Limit — {series_name}"


def build_group_data(
    result: pd.DataFrame,
    selected_cases: list[str],
    limits: pd.DataFrame | None = None,
    limit_series: str | None = None,
) -> pd.DataFrame:
    """Select result traces and align an optional limit by harmonic order."""
    source_columns = [result.columns[0], *selected_cases]
    data = result.loc[:, source_columns].apply(pd.to_numeric, errors="coerce")
    data.columns = ["Harmonic Order", *selected_cases]
    data = data.sort_values("Harmonic Order", kind="stable").reset_index(drop=True)

    if limits is not None and limit_series and limit_series in limits.columns:
        limit_orders = pd.to_numeric(limits.iloc[:, 0], errors="coerce")
        limit_values = pd.to_numeric(limits[limit_series], errors="coerce")
        limit_lookup = pd.Series(limit_values.to_numpy(), index=limit_orders.to_numpy())
        column = limit_column_name(limit_series)
        data[column] = data["Harmonic Order"].map(limit_lookup)
    return data


def build_thd_data(
    data: pd.DataFrame,
    case_descriptions: dict[str, str],
    max_order: int = THD_MAX_ORDER,
) -> tuple[pd.DataFrame, tuple[int, int] | None]:
    """Calculate per-case voltage THD from supplied per-order percentages."""
    output_columns = ["Case", "Description", "THD (%)", "Missing orders"]
    if "Harmonic Order" not in data:
        return pd.DataFrame(columns=output_columns), None

    orders = pd.to_numeric(data["Harmonic Order"], errors="coerce")
    integer_orders = orders.notna() & orders.mod(1).eq(0)
    available_orders = orders.loc[integer_orders & orders.ge(2)]
    if available_orders.empty:
        return pd.DataFrame(columns=output_columns), None

    upper_order = min(max_order, int(available_orders.max()))
    expected_orders = set(range(2, upper_order + 1))
    included = integer_orders & orders.between(2, upper_order)
    included_data = data.loc[included].copy()
    included_orders = pd.to_numeric(included_data["Harmonic Order"], errors="coerce").astype(int)
    missing_rows = expected_orders.difference(included_orders.tolist())
    case_columns = [
        column
        for column in included_data.columns
        if column != "Harmonic Order" and not str(column).startswith("Limit — ")
    ]

    rows = []
    for case_code in case_columns:
        values = pd.to_numeric(included_data[case_code], errors="coerce")
        missing_values = set(included_orders.loc[values.isna()].tolist())
        missing_orders = sorted(missing_rows.union(missing_values))
        thd_value = (
            math.sqrt(float(values.pow(2).sum()))
            if not missing_orders and expected_orders
            else float("nan")
        )
        rows.append(
            {
                "Case": case_code,
                "Description": case_descriptions.get(case_code, ""),
                "THD (%)": thd_value,
                "Missing orders": missing_orders,
            }
        )

    return pd.DataFrame(rows, columns=output_columns), (2, upper_order)


def build_thd_figure(
    data: pd.DataFrame,
    selected_cases: list[str],
    title: str,
    y_axis_max: float | None = None,
) -> go.Figure:
    """Create a sorted vertical THD bar chart using the case palette."""
    figure = go.Figure()
    plotted = data.loc[data["THD (%)"].notna()].sort_values(
        "THD (%)", ascending=False, kind="stable"
    )
    color_by_case = {
        case_code: CASE_COLORS[index % len(CASE_COLORS)]
        for index, case_code in enumerate(selected_cases)
    }
    if not plotted.empty:
        figure.add_trace(
            go.Bar(
                x=plotted["Case"].tolist(),
                y=plotted["THD (%)"].tolist(),
                marker={
                    "color": [color_by_case[case] for case in plotted["Case"]],
                    "opacity": 0.86,
                },
                texttemplate="%{y:.2f} %",
                textposition="outside",
                cliponaxis=False,
                textfont={"color": PLOT_TEXT_COLOR},
                customdata=plotted["Description"].fillna("").tolist(),
                hovertemplate=(
                    "<b>%{x}</b><br>Voltage THD: %{y:.5g} %"
                    "<br>%{customdata}<extra></extra>"
                ),
                showlegend=False,
            )
        )

    max_value = float(plotted["THD (%)"].max()) if not plotted.empty else 0
    figure.update_layout(
        title={
            "text": title,
            "x": 0,
            "xanchor": "left",
            "pad": {"l": PLOT_TITLE_LEFT_PADDING},
            "font": {"color": PLOT_TEXT_COLOR},
        },
        template="plotly_white",
        height=PLOT_HEIGHT,
        margin={"l": 66, "r": 24, "t": 48, "b": 112},
        hoverlabel={"bgcolor": "white", "font": {"color": PLOT_TEXT_COLOR}},
        font={"family": "Calibri, Arial, sans-serif", "color": PLOT_TEXT_COLOR, "size": 12},
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    figure.update_xaxes(
        title={"text": "", "font": {"color": PLOT_TEXT_COLOR}},
        categoryorder="array",
        categoryarray=plotted["Case"].tolist(),
        tickangle=-45,
        tickfont={"size": 10, "color": PLOT_TEXT_COLOR},
        showgrid=False,
        zeroline=False,
        automargin=True,
    )
    y_range = (
        [0, float(y_axis_max)]
        if y_axis_max is not None
        else [0, max(max_value * 1.18, 0.1)]
    )
    figure.update_yaxes(
        title={"text": "THD (%)", "font": {"color": PLOT_TEXT_COLOR}},
        tickfont={"color": PLOT_TEXT_COLOR},
        range=y_range,
        showgrid=True,
        gridcolor="#E5E8EE",
        zeroline=False,
        automargin=True,
    )
    return figure


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
    y_axis_max: float | None = None,
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
    case_values = data[case_columns].apply(pd.to_numeric, errors="coerce")
    limit_hover_order = case_values.min(axis=1).fillna(0).tolist()
    limit_values = (
        pd.to_numeric(data[limit_columns[0]], errors="coerce")
        if limit_columns
        else None
    )
    if limit_display == "Bars":
        for column in limit_columns:
            figure.add_trace(
                go.Bar(
                    x=x_values,
                    y=data[column].tolist(),
                    width=1.0,
                    name=column.removeprefix("Limit — "),
                    marker={"color": "rgba(112, 173, 71, 0.08)"},
                    showlegend=False,
                    hoverinfo="skip",
                )
            )

    for index, case_code in enumerate(case_columns):
        description = case_descriptions.get(case_code, "")
        hover_template = (
            "<span style='color:%{customdata}'><b>%{fullData.name}</b> · %{y:.5g} %"
        )
        if description:
            hover_template += " · %{meta}"
        hover_template += "</span><extra></extra>"
        values = case_values[case_code]
        violating = (
            values.gt(limit_values).fillna(False)
            if limit_values is not None
            else pd.Series(False, index=values.index)
        )
        trace_options = {
            "name": case_code,
            "legendgroup": case_code,
            "mode": "markers",
            "marker": {"size": 8, "symbol": "circle", "opacity": 0.72},
            "marker_color": CASE_COLORS[index % len(CASE_COLORS)],
            "connectgaps": False,
            "meta": description if description else None,
            "customdata": [
                VIOLATION_TEXT_COLOR if is_violating else PLOT_TEXT_COLOR
                for is_violating in violating
            ],
            "hovertemplate": hover_template,
        }
        figure.add_trace(
            go.Scatter(
                x=x_values,
                y=values.tolist(),
                hoverlabel={"font": {"color": PLOT_TEXT_COLOR}},
                **trace_options,
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
                hoverinfo="skip",
            )
        )
        figure.add_trace(
            go.Scatter(
                x=x_values,
                y=limit_hover_order,
                customdata=pd.to_numeric(data[column], errors="coerce").tolist(),
                name=column.removeprefix("Limit — "),
                mode="markers",
                marker={
                    "size": 6.5,
                    "symbol": "line-ew",
                    "color": LIMIT_COLOR,
                    "opacity": 0,
                    "line": {"color": LIMIT_COLOR, "width": 1.5},
                },
                connectgaps=False,
                showlegend=False,
                hovertemplate=(
                    "<b>%{fullData.name}</b> · %{customdata:.5g} %<extra></extra>"
                ),
            )
        )

    orders = pd.to_numeric(data.get("Harmonic Order", pd.Series(dtype=float)), errors="coerce").dropna()
    span = float(orders.max() - orders.min()) if not orders.empty else 0
    all_integral = bool(((orders % 1) == 0).all()) if not orders.empty else True
    figure.update_layout(
        title={
            "text": title,
            "x": 0,
            "xanchor": "left",
            "pad": {"l": PLOT_TITLE_LEFT_PADDING},
            "font": {"color": PLOT_TEXT_COLOR},
        },
        template="plotly_white",
        colorway=CASE_COLORS,
        height=PLOT_HEIGHT,
        margin={"l": 66, "r": 18, "t": 48, "b": 125},
        hovermode="x unified",
        hoversort="value descending",
        hoverlabel={"bgcolor": "white", "font": {"color": PLOT_TEXT_COLOR}},
        legend={
            "orientation": "h",
            "x": 0,
            "xanchor": "left",
            "y": -0.34,
            "yanchor": "top",
            "itemsizing": "constant",
            "font": {"size": 11, "color": PLOT_TEXT_COLOR},
        },
        legend2={
            "orientation": "h",
            "x": 0,
            "xanchor": "left",
            "y": -0.22,
            "yanchor": "top",
            "itemsizing": "constant",
            "font": {"size": 11, "color": PLOT_TEXT_COLOR},
        },
        font={"family": "Calibri, Arial, sans-serif", "color": PLOT_TEXT_COLOR, "size": 12},
        paper_bgcolor="white",
        plot_bgcolor="white",
    )
    x_axis_options = {
        "title": {"text": "Harmonic order", "font": {"color": PLOT_TEXT_COLOR}},
        "tickfont": {"color": PLOT_TEXT_COLOR},
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
    y_axis_options = {
        "title": {
            "text": "Harmonic voltage distortion (%)",
            "font": {"color": PLOT_TEXT_COLOR},
        },
        "tickfont": {"color": PLOT_TEXT_COLOR},
        "showgrid": True,
        "gridcolor": "#E5E8EE",
        "zeroline": False,
        "automargin": True,
    }
    if y_axis_max is None:
        y_axis_options["rangemode"] = "tozero"
    else:
        y_axis_options["range"] = [0, float(y_axis_max)]
    figure.update_yaxes(**y_axis_options)
    return figure
