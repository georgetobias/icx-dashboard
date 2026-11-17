from __future__ import annotations

import html
from typing import Literal

import numpy as np
import pandas as pd
import plotly.graph_objects as go

try:
    from .icx_data import (
        BLUE_QUEUE_ORDER,
        CRITICALITY_REPORT_ORDER,
        FREQUENCY_REPORT_ORDER,
        NPS_THRESHOLD,
        SMALL_N_THRESHOLD,
        classify_icx_score_band,
    )
except ImportError:
    from icx_data import (
        BLUE_QUEUE_ORDER,
        CRITICALITY_REPORT_ORDER,
        FREQUENCY_REPORT_ORDER,
        NPS_THRESHOLD,
        SMALL_N_THRESHOLD,
        classify_icx_score_band,
    )

PlotKind = Literal["criticality", "frequency"]
AxisView = Literal["auto", "full"]
CHART_FONT = "DM Sans, Arial, sans-serif"

COLORS = {
    "background": "#F5F8FF",
    "surface": "#FFFFFF",
    "soft": "#EAF3FF",
    "border": "#D7E3F2",
    "grid": "#D9E6F7",
    "text": "#102A56",
    "muted": "#6B7F99",
    "blue": "#155EEF",
    "deep": "#29348F",
    "cyan": "#00A6E8",
    "alert": "#D92D20",
    "warning": "#F59E0B",
    "good": "#10A37F",
    "gray": "#9AAEC7",
}

ICX_COLORSCALE = [
    [0.00, "#FF00AC"],
    [0.24, "#C96EE3"],
    [0.52, "#0305C6"],
    [0.78, "#A9D1FF"],
    [1.00, "#EFF8FF"],
]

FREQUENCY_SHORT_LABELS = {
    "Annual": "Annual",
    "Quarterly": "Quarterly",
    "Monthly": "Monthly",
    "Weekly": "Weekly",
    "Daily": "Daily",
    "Ad hoc / Upon request": "Ad hoc",
}

FREQUENCY_DISPLAY_LABELS = {
    "Daily": "Daily",
    "Weekly": "Weekly",
    "Monthly": "Monthly",
    "Quarterly": "Quarterly",
    "Annual": "Annually",
    "Ad hoc / Upon request": "Ad Hoc or Upon Request",
}

FREQUENCY_COMPARISON_COLORS = {
    "Daily": "#155EEF",
    "Weekly": "#10A37F",
    "Monthly": "#E17A00",
    "Quarterly": "#7A3FF2",
    "Annual": "#D63C8D",
    "Ad hoc / Upon request": "#3B4758",
}

BLUE_CATEGORY_COLORS = {
    "Busted": "#D92D20",
    "Leveled": "#B6E880",
    "Uplifted": "#0E7A5F",
    "Exceptional": "#155EEF",
}

BLUE_SCATTER_BASE_MARKER_SIZE = 18.0
BLUE_SCATTER_BASE_LABEL_FONT_SIZE = 12.5
BLUE_SCATTER_BASE_BAND_LABEL_FONT_SIZE = 17.0
BLUE_SCATTER_SCALE_MIN = 0.85
BLUE_SCATTER_SCALE_MAX = 1.25
BLUE_SCATTER_LABEL_MAX_OFFSET_PX = 145
QUEUE_HEADER_FONT_SIZE = 15
QUEUE_PRIMARY_FONT_SIZE = 16
QUEUE_DETAIL_FONT_SIZE = 15
QUEUE_PILL_FONT_SIZE = 14
QUEUE_ROW_HEIGHT = 32
QUEUE_ROW_HALF_HEIGHT = 0.42
QUEUE_PILL_HALF_HEIGHT = 0.29
QUEUE_BAR_HALF_HEIGHT = 0.24


def blue_band_color(nps: float) -> str:
    band = classify_icx_score_band(nps)
    return BLUE_CATEGORY_COLORS.get(str(band), COLORS["gray"])


def _blue_band_visual_range(band: str) -> tuple[float, float]:
    if band == "Busted":
        return -100, 0
    if band == "Leveled":
        return 0, 30
    if band == "Uplifted":
        return 30, NPS_THRESHOLD
    return NPS_THRESHOLD, 100


def _interpolate_hex(start: str, end: str, ratio: float) -> str:
    ratio = float(np.clip(ratio, 0, 1))
    start_rgb = tuple(int(start[index : index + 2], 16) for index in (1, 3, 5))
    end_rgb = tuple(int(end[index : index + 2], 16) for index in (1, 3, 5))
    blended = tuple(
        round(start_value + (end_value - start_value) * ratio)
        for start_value, end_value in zip(start_rgb, end_rgb)
    )
    return "#" + "".join(f"{value:02X}" for value in blended)


def icx_color(nps: float, minimum: float = 0, maximum: float = 100) -> str:
    if pd.isna(nps):
        return COLORS["gray"]
    if maximum <= minimum:
        return ICX_COLORSCALE[-1][1]

    ratio = float(np.clip((float(nps) - minimum) / (maximum - minimum), 0, 1))
    for (start_pos, start_color), (end_pos, end_color) in zip(
        ICX_COLORSCALE,
        ICX_COLORSCALE[1:],
    ):
        if ratio <= end_pos:
            local_ratio = 0.0 if end_pos == start_pos else (ratio - start_pos) / (end_pos - start_pos)
            return _interpolate_hex(start_color, end_color, local_ratio)
    return ICX_COLORSCALE[-1][1]


def _contrast_text_color(fill_color: str) -> str:
    red = int(fill_color[1:3], 16)
    green = int(fill_color[3:5], 16)
    blue = int(fill_color[5:7], 16)
    luminance = 0.299 * red + 0.587 * green + 0.114 * blue
    return "#FFFFFF" if luminance < 160 else COLORS["text"]


def icx_text_color(nps: float) -> str:
    return _contrast_text_color(blue_band_color(nps))


def frequency_comparison_color(label: str) -> str:
    return FREQUENCY_COMPARISON_COLORS.get(str(label), COLORS["deep"])


def text_color(marker_color: str) -> str:
    return _contrast_text_color(marker_color)


def _dot_sizes(ratings: pd.Series, size_add: float = 0) -> pd.Series:
    return (ratings.clip(lower=1) ** 0.5 * 0.42).clip(lower=10, upper=25) + size_add


def _clamp_scatter_size_scale(value: float) -> float:
    try:
        scale = float(value)
    except (TypeError, ValueError):
        scale = 1.05
    return float(np.clip(scale, BLUE_SCATTER_SCALE_MIN, BLUE_SCATTER_SCALE_MAX))


def _nps_y_range(nps_values: pd.Series, y_axis_view: AxisView) -> list[float]:
    if y_axis_view == "full" or nps_values.empty:
        return [-105, 110]
    minimum = float(nps_values.min())
    y_min = -10 if minimum >= -10 else max(-105, minimum - 10)
    return [y_min, 105]


def _nps_tickvals(y_range: list[float]) -> list[int]:
    candidates = [-100, -50, -10, 0, 30, 70, 100]
    return [value for value in candidates if y_range[0] <= value <= y_range[1]]


def _criticality_x_range(
    plot_df: pd.DataFrame,
    x_axis_view: AxisView,
    reference_x: float | None = None,
) -> list[float]:
    if x_axis_view == "full" or plot_df.empty:
        return [1.0, 4.05]
    values = plot_df["avg_criticality"].dropna()
    if values.empty:
        if reference_x is None:
            return [2.7, 4.12]
        values = pd.Series([reference_x])
    elif reference_x is not None:
        values = pd.concat([values, pd.Series([reference_x])], ignore_index=True)
    x_min = float(values.min()) - 0.12
    x_max = float(values.max()) + 0.12
    return [max(1.0, x_min), min(4.12, x_max)]


def _criticality_tickvals(x_range: list[float]) -> list[float]:
    candidates = [1.0, 1.5, 2.0, 2.5, 2.8, 3.0, 3.2, 3.4, 3.5, 3.6, 3.8, 4.0]
    return [value for value in candidates if x_range[0] <= value <= x_range[1]]


def build_blue_band_scatter(
    data: pd.DataFrame,
    kind: PlotKind,
    title: str,
    subtitle: str,
    highlighted_label: str | None = None,
    x_axis_view: AxisView = "auto",
    y_axis_view: AxisView = "full",
    show_labels: bool = True,
    use_full_labels: bool = False,
    scatter_size_scale: float = 1.05,
    global_mean_criticality: float | None = None,
    show_global_mean_criticality: bool = True,
    global_mean_label: str = "global service-cluster mean criticality",
) -> go.Figure:
    if kind == "frequency":
        raise ValueError(
            "Frequency views use the heatmap, attention queue, and gap finder panels."
        )

    fig = go.Figure()
    if data.empty:
        return empty_figure(title, "No aggregate rows are available for this view.")

    plot_df = data.copy()
    if use_full_labels:
        if "service_cluster" in plot_df.columns:
            plot_df["label_short"] = plot_df["service_cluster"].astype(str)
        elif "label_full" in plot_df.columns:
            plot_df["label_short"] = plot_df["label_full"].astype(str)
    plot_df["line_width"] = [
        3 if str(label) == str(highlighted_label) else 1.3
        for label in plot_df["label_full"]
    ]
    plot_df["line_color"] = [
        COLORS["deep"] if str(label) == str(highlighted_label) else "#FFFFFF"
        for label in plot_df["label_full"]
    ]
    plot_df["small_n_note"] = plot_df["small_n"].map(
        {True: f"Small sample: n < {SMALL_N_THRESHOLD}", False: "Sample size OK"}
    )
    plot_df["hover_title"] = (
        plot_df["slice_full"].astype(str)
        if "slice_full" in plot_df.columns
        else plot_df["label_full"].astype(str)
    )
    plot_df["hover_frequency"] = (
        plot_df["frequency_normalized"].astype(str)
        if "frequency_normalized" in plot_df.columns
        else plot_df["dominant_frequency"].astype(str)
    )
    if {"provider_group", "service_cluster", "service_cluster_code"}.issubset(plot_df.columns):
        plot_df["hover_context"] = (
            "Provider: "
            + plot_df["provider_group"].astype(str)
            + "<br>Service cluster: "
            + plot_df["service_cluster"].astype(str)
            + "<br>Code: "
            + plot_df["service_cluster_code"].astype(str)
        )
    elif "point_type" in plot_df.columns:
        plot_df["hover_context"] = (
            "Point type: "
            + plot_df["point_type"].fillna("Point").astype(str)
            + "<br>Item: "
            + plot_df["label_full"].astype(str)
        )
    else:
        plot_df["hover_context"] = "Item: " + plot_df["label_full"].astype(str)

    plot_df = plot_df.dropna(subset=["avg_criticality"])
    global_mean_x = None
    if show_global_mean_criticality and global_mean_criticality is not None:
        try:
            candidate_mean = float(global_mean_criticality)
        except (TypeError, ValueError):
            candidate_mean = float("nan")
        if np.isfinite(candidate_mean):
            global_mean_x = candidate_mean
    scatter_size_scale = _clamp_scatter_size_scale(scatter_size_scale)
    marker_size = BLUE_SCATTER_BASE_MARKER_SIZE * scatter_size_scale
    label_font_size = max(
        11,
        int(round(BLUE_SCATTER_BASE_LABEL_FONT_SIZE * scatter_size_scale)),
    )
    x_metric = plot_df["avg_criticality"]
    x_axis_title = "Criticality Score"
    x_range = _criticality_x_range(plot_df, x_axis_view, reference_x=global_mean_x)
    x_reference = x_range[0] + (x_range[1] - x_range[0]) / 2
    x_tickvals = _criticality_tickvals(x_range)
    x_ticktext = [f"{value:.1f}" for value in x_tickvals]
    y_range = _nps_y_range(plot_df["nps"], y_axis_view)
    shapes = _blue_band_shapes(y_range=y_range)
    if global_mean_x is not None:
        shapes.append(
            {
                "type": "line",
                "xref": "x",
                "yref": "paper",
                "x0": global_mean_x,
                "x1": global_mean_x,
                "y0": 0,
                "y1": 1,
                "line": {"color": "rgba(83, 101, 125, 0.38)", "width": 1.4, "dash": "dot"},
                "layer": "below",
            }
        )
    annotations = _blue_band_annotations(
        y_range=y_range,
        label_scale=scatter_size_scale,
    )

    plot_df["marker_size"] = marker_size
    plot_df["icx_score_band"] = plot_df["nps"].map(classify_icx_score_band)
    plot_df["marker_color"] = plot_df["nps"].map(blue_band_color)
    plot_df["text_color"] = plot_df["marker_color"].map(text_color)
    plot_df["marker_symbol"] = "circle"
    if "is_territory_point" in plot_df.columns:
        territory_mask = plot_df["is_territory_point"].fillna(False).astype(bool)
        plot_df.loc[territory_mask, "marker_symbol"] = "diamond"
    plot_df["marker_opacity"] = 0.9
    plot_df["blue_mix"] = plot_df.apply(
        lambda row: (
            "BLUE mix: not supplied for this territory cut"
            if row.get("blue_counts_reconciled", True) is False
            or any(
                pd.isna(row.get(column))
                for column in ("busted", "leveled", "uplifted", "exceptional")
            )
            else (
                f"Busted: {row['busted']:,.0f}<br>"
                f"Leveled: {row['leveled']:,.0f}<br>"
                f"Uplifted: {row['uplifted']:,.0f}<br>"
                f"Exceptional: {row['exceptional']:,.0f}"
            )
        ),
        axis=1,
    )

    x_values, y_values = _packed_positions(
        plot_df=plot_df,
        kind=kind,
        x_metric=x_metric,
        x_range=x_range,
        y_range=y_range,
        vertical_line=x_reference,
        score_threshold=50,
    )
    dense_label_view = show_labels and len(plot_df) > 22

    fig.add_trace(
        go.Scatter(
            x=x_values,
            y=y_values,
            mode="markers",
            marker={
                "size": plot_df["marker_size"],
                "color": plot_df["marker_color"],
                "symbol": plot_df["marker_symbol"],
                "line": {
                    "width": plot_df["line_width"],
                    "color": plot_df["line_color"],
                },
                "opacity": plot_df["marker_opacity"],
            },
            customdata=plot_df[
                [
                    "hover_title",
                    "hover_context",
                    "ratings",
                    "nps",
                    "icx_score_band",
                    "avg_criticality",
                    "hover_frequency",
                    "blue_mix",
                    "small_n_note",
                ]
            ],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "%{customdata[1]}<br>"
                "Ratings: %{customdata[2]:,.0f}<br>"
                "iCX score: %{customdata[3]:.2f}<br>"
                "BLUE band: %{customdata[4]}<br>"
                "Avg criticality: %{customdata[5]:.2f}<br>"
                "Frequency: %{customdata[6]}<br>"
                "%{customdata[7]}<br>"
                "%{customdata[8]}<extra></extra>"
            ),
        )
    )

    fig.update_layout(
        height=1120 if dense_label_view else 1040 if kind == "frequency" else 980,
        margin=(
            {"l": 170, "r": 240, "t": 58, "b": 190}
            if dense_label_view
            else {"l": 150, "r": 220, "t": 44, "b": 170}
        ),
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["surface"],
        showlegend=False,
        shapes=shapes,
        annotations=annotations,
        font={"family": CHART_FONT, "color": COLORS["text"]},
    )
    fig.update_xaxes(
        title=x_axis_title,
        range=x_range,
        tickmode="array",
        tickvals=x_tickvals,
        ticktext=x_ticktext,
        showgrid=False,
        zeroline=False,
        linecolor=COLORS["border"],
        title_font={"size": 22, "color": COLORS["text"]},
        tickfont={"size": 18, "color": COLORS["text"]},
        title_standoff=28,
        automargin=True,
    )
    fig.update_yaxes(
        title="iCX score",
        range=y_range,
        tickmode="array",
        tickvals=_nps_tickvals(y_range),
        showgrid=False,
        zeroline=False,
        linecolor=COLORS["border"],
        title_font={"size": 22, "color": COLORS["text"]},
        tickfont={"size": 18, "color": COLORS["text"]},
        title_standoff=42,
        automargin=True,
    )
    if show_labels:
        _add_external_scatter_labels(
            fig=fig,
            plot_df=plot_df,
            x_values=x_values,
            y_values=y_values,
            x_range=x_range,
            y_range=y_range,
            vertical_line=x_reference,
            score_threshold=50,
            label_font_size=label_font_size,
            label_scale=scatter_size_scale,
        )
    note_text = (
        "BLUE thresholds: 70 Exceptional, 30 Uplifted, 0 Busted boundary. "
        "Criticality is context only."
    )
    if global_mean_x is not None:
        note_text += f" Gray vertical line = {global_mean_label} ({global_mean_x:.2f})."
    if "is_territory_point" in plot_df.columns:
        territory_mask = plot_df["is_territory_point"].fillna(False).astype(bool)
        if bool(territory_mask.any()) and bool((~territory_mask).any()):
            note_text += " Circle = Division. Diamond = Territory."
    fig.add_annotation(
        x=0.01,
        y=-0.10,
        xref="paper",
        yref="paper",
        text=note_text,
        showarrow=False,
        align="left",
        font={"size": 15, "color": COLORS["muted"]},
    )
    return fig


def build_frequency_criticality_heatmap(
    data: pd.DataFrame,
    title: str,
    subtitle: str,
) -> go.Figure:
    if data.empty:
        return empty_figure(title, "No frequency and criticality rows are available.")

    grid_index = pd.MultiIndex.from_product(
        [CRITICALITY_REPORT_ORDER, FREQUENCY_REPORT_ORDER],
        names=["criticality_normalized", "frequency_normalized"],
    )
    plot_df = (
        data.set_index(["criticality_normalized", "frequency_normalized"])
        .reindex(grid_index)
        .reset_index()
    )
    nps_grid = _matrix_values(plot_df, "nps", CRITICALITY_REPORT_ORDER, FREQUENCY_REPORT_ORDER)
    responses_grid = _matrix_values(
        plot_df, "responses", CRITICALITY_REPORT_ORDER, FREQUENCY_REPORT_ORDER
    )
    small_n_grid = _matrix_values(
        plot_df, "small_n", CRITICALITY_REPORT_ORDER, FREQUENCY_REPORT_ORDER
    )
    busted_grid = _matrix_values(plot_df, "busted", CRITICALITY_REPORT_ORDER, FREQUENCY_REPORT_ORDER)
    leveled_grid = _matrix_values(plot_df, "leveled", CRITICALITY_REPORT_ORDER, FREQUENCY_REPORT_ORDER)
    uplifted_grid = _matrix_values(
        plot_df, "uplifted", CRITICALITY_REPORT_ORDER, FREQUENCY_REPORT_ORDER
    )
    exceptional_grid = _matrix_values(
        plot_df, "exceptional", CRITICALITY_REPORT_ORDER, FREQUENCY_REPORT_ORDER
    )

    x_labels = [FREQUENCY_DISPLAY_LABELS.get(value, value) for value in FREQUENCY_REPORT_ORDER]
    y_labels = CRITICALITY_REPORT_ORDER
    sample_grid = np.where(small_n_grid == 1, "Small sample", "Stable sample")
    sample_grid[np.isnan(nps_grid)] = ""
    customdata = np.empty((*nps_grid.shape, 7), dtype=object)
    customdata[:, :, 0] = nps_grid
    customdata[:, :, 1] = responses_grid
    customdata[:, :, 2] = sample_grid
    customdata[:, :, 3] = busted_grid
    customdata[:, :, 4] = leveled_grid
    customdata[:, :, 5] = uplifted_grid
    customdata[:, :, 6] = exceptional_grid
    fig = go.Figure(
        data=[
            go.Heatmap(
                x=x_labels,
                y=y_labels,
                z=nps_grid,
                zmin=0,
                zmax=100,
                colorscale=ICX_COLORSCALE,
                colorbar={
                    "title": "iCX",
                    "tickmode": "array",
                    "tickvals": [0, 30, 70, 100],
                    "ticktext": ["0", "30", "70", "100"],
                    "len": 0.48,
                    "thickness": 16,
                },
                customdata=customdata,
                hovertemplate=(
                    "<b>%{y} | %{x}</b><br>"
                    "iCX: %{customdata[0]:.2f}<br>"
                    "Responses: %{customdata[1]:,.0f}<br>"
                    "Sample: %{customdata[2]}<br>"
                    "Busted: %{customdata[3]:,.0f}<br>"
                    "Leveled: %{customdata[4]:,.0f}<br>"
                    "Uplifted: %{customdata[5]:,.0f}<br>"
                    "Exceptional: %{customdata[6]:,.0f}<extra></extra>"
                ),
                xgap=9,
                ygap=9,
            )
        ]
    )
    for row_index, criticality in enumerate(y_labels):
        for col_index, frequency in enumerate(x_labels):
            nps_value = nps_grid[row_index, col_index]
            responses = responses_grid[row_index, col_index]
            if np.isnan(nps_value) or np.isnan(responses):
                continue
            fig.add_annotation(
                x=frequency,
                y=criticality,
                text=(
                    f"<b>iCX {nps_value:.1f}</b><br>"
                    f"<span style='font-size:13px'>{responses:,.0f} Responses</span>"
                ),
                showarrow=False,
                align="left",
                font={
                    "size": 17,
                    "color": icx_text_color(float(nps_value)),
                    "family": CHART_FONT,
                },
            )

    fig.update_layout(
        height=760,
        margin={"l": 170, "r": 120, "t": 56, "b": 120},
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["surface"],
        font={"family": CHART_FONT, "color": COLORS["text"]},
    )
    fig.update_xaxes(
        side="top",
        tickfont={"size": 16, "color": COLORS["text"]},
        showgrid=False,
        zeroline=False,
        linecolor=COLORS["border"],
        fixedrange=True,
    )
    fig.update_yaxes(
        autorange="reversed",
        tickfont={"size": 18, "color": COLORS["text"]},
        showgrid=False,
        zeroline=False,
        linecolor=COLORS["border"],
        fixedrange=True,
    )
    return fig


def build_frequency_attention_queue(
    data: pd.DataFrame,
    title: str,
    subtitle: str,
    top_n: int | None = 20,
) -> go.Figure:
    if data.empty:
        return empty_figure(title, "No group-frequency rows are available.")

    plot_df = data.copy()
    if top_n is not None:
        plot_df = plot_df.head(top_n)
    if plot_df.empty:
        return empty_figure(title, "No rows match the selected attention filters.")

    row_count = len(plot_df)
    height = max(460, 140 + row_count * 40)
    max_attention = max(float(plot_df["attention_score"].max()), 1.0)
    fig = go.Figure()
    shapes: list[dict] = []
    annotations: list[dict] = []

    headers = [
        ("Frequency", 0.015),
        ("Group", 0.12),
        ("Responses", 0.46),
        ("iCX Score", 0.59),
        ("Criticality", 0.68),
        ("Attention Score", 0.77),
    ]
    header_y = row_count + 0.95
    shapes.append(
        {
            "type": "rect",
            "xref": "x",
            "yref": "y",
            "x0": 0.005,
            "x1": 0.995,
            "y0": row_count + 0.2,
            "y1": row_count + 1.18,
            "fillcolor": "#F8FBFF",
            "line": {"color": COLORS["border"], "width": 1},
            "layer": "below",
        }
    )
    for text, x_pos in headers:
        annotations.append(
            {
                "x": x_pos,
                "y": header_y,
                "text": text,
                "showarrow": False,
                "xanchor": "left",
                "font": {"size": QUEUE_HEADER_FONT_SIZE, "color": COLORS["muted"]},
            }
        )

    for display_index, row in enumerate(plot_df.itertuples(index=False)):
        y_pos = row_count - display_index
        fill = "#FFFFFF" if display_index % 2 == 0 else "#F8FBFF"
        shapes.append(
            {
                "type": "rect",
                "xref": "x",
                "yref": "y",
                "x0": 0.005,
                "x1": 0.995,
                "y0": y_pos - QUEUE_ROW_HALF_HEIGHT,
                "y1": y_pos + QUEUE_ROW_HALF_HEIGHT,
                "fillcolor": fill,
                "line": {"width": 0},
                "layer": "below",
            }
        )
        shapes.append(
            {
                "type": "rect",
                "xref": "x",
                "yref": "y",
                "x0": 0.005,
                "x1": 0.011,
                "y0": y_pos - QUEUE_ROW_HALF_HEIGHT,
                "y1": y_pos + QUEUE_ROW_HALF_HEIGHT,
                "fillcolor": COLORS["blue"],
                "line": {"width": 0},
                "layer": "above",
            }
        )
        frequency_label = _wrap_annotation_text(
            str(
                FREQUENCY_DISPLAY_LABELS.get(
                    row.frequency_normalized,
                    row.frequency_normalized,
                )
            ),
            limit=14,
        )
        group_label = _wrap_annotation_text(str(row.label_full), limit=42)
        annotations.extend(
            [
                _table_annotation(
                    0.015,
                    y_pos,
                    str(frequency_label),
                    size=13,
                    allow_html=True,
                ),
                _table_annotation(
                    0.12,
                    y_pos,
                    group_label,
                    size=13,
                    color=COLORS["text"],
                    allow_html=True,
                ),
            ]
        )
        response_count = int(row.ratings)
        response_text = (
            f"{response_count:,} Response"
            if response_count == 1
            else f"{response_count:,} Responses"
        )
        annotations.append(
            _table_annotation(
                0.46,
                y_pos,
                response_text,
                size=QUEUE_DETAIL_FONT_SIZE,
                color=COLORS["text"],
            )
        )

        pill_x0, pill_x1 = 0.585, 0.645
        pill_color = _icx_status_color(float(row.nps))
        shapes.append(
            {
                "type": "rect",
                "xref": "x",
                "yref": "y",
                "x0": pill_x0,
                "x1": pill_x1,
                "y0": y_pos - QUEUE_PILL_HALF_HEIGHT,
                "y1": y_pos + QUEUE_PILL_HALF_HEIGHT,
                "fillcolor": pill_color,
                "line": {"color": pill_color},
                "layer": "above",
            }
        )
        annotations.append(
            {
                "x": (pill_x0 + pill_x1) / 2,
                "y": y_pos,
                "text": f"{float(row.nps):.1f}",
                "showarrow": False,
                "font": {
                    "size": QUEUE_PILL_FONT_SIZE,
                    "color": _pill_text_color(float(row.nps)),
                },
            }
        )
        annotations.append(
            _table_annotation(
                0.68,
                y_pos,
                f"{float(row.avg_criticality):.2f}",
                size=QUEUE_PRIMARY_FONT_SIZE,
            )
        )

        bar_track_x0, bar_track_x1 = 0.77, 0.92
        shapes.append(
            {
                "type": "line",
                "xref": "x",
                "yref": "y",
                "x0": bar_track_x0,
                "x1": bar_track_x1,
                "y0": y_pos,
                "y1": y_pos,
                "line": {"color": "#E7EEF8", "width": 6},
                "layer": "below",
            }
        )
        bar_x1 = bar_track_x0 + (bar_track_x1 - bar_track_x0) * (
            float(row.attention_score) / max_attention
        )
        if float(row.attention_score) > 0:
            bar_color = _icx_status_color(float(row.nps))
            shapes.append(
                {
                    "type": "line",
                    "xref": "x",
                    "yref": "y",
                    "x0": bar_track_x0,
                    "x1": bar_x1,
                    "y0": y_pos,
                    "y1": y_pos,
                    "line": {"color": bar_color, "width": 5},
                    "layer": "above",
                }
            )
            shapes.append(
                {
                    "type": "circle",
                    "xref": "x",
                    "yref": "y",
                    "x0": bar_x1 - 0.006,
                    "x1": bar_x1 + 0.006,
                    "y0": y_pos - 0.18,
                    "y1": y_pos + 0.18,
                    "fillcolor": bar_color,
                    "line": {"color": bar_color, "width": 1},
                    "layer": "above",
                }
            )
        annotations.append(
            _table_annotation(
                0.945,
                y_pos,
                f"{float(row.attention_score):,.0f}",
                size=QUEUE_PRIMARY_FONT_SIZE,
                color=COLORS["muted"],
            )
        )

    annotations.append(
        _table_annotation(
            0.77,
            row_count + 0.48,
            "Higher priority →",
            size=11,
            color=COLORS["muted"],
        )
    )

    fig.update_layout(
        height=height,
        margin={"l": 12, "r": 34, "t": 18, "b": 18},
        paper_bgcolor=COLORS["surface"],
        plot_bgcolor=COLORS["surface"],
        showlegend=False,
        shapes=shapes,
        annotations=annotations,
        font={"family": CHART_FONT, "color": COLORS["text"]},
        xaxis={"visible": False, "range": [0, 1], "fixedrange": True},
        yaxis={"visible": False, "range": [0.55, row_count + 1.25], "fixedrange": True},
    )
    return fig


def build_blue_attention_queue(
    data: pd.DataFrame,
    title: str,
    subtitle: str,
    top_n: int | None = None,
    item_label_header: str = "Group",
    show_code_column: bool = True,
) -> go.Figure:
    if data.empty:
        return empty_figure(title, "No rows match this BLUE score band.")

    plot_df = data.copy()
    if top_n is not None:
        plot_df = plot_df.head(top_n)
    if plot_df.empty:
        return empty_figure(title, "No rows match this BLUE score band.")

    row_count = len(plot_df)
    height = max(560, 250 + row_count * QUEUE_ROW_HEIGHT)
    max_attention = max(float(plot_df["attention_score"].max()), 1.0)
    fig = go.Figure()
    fig.update_layout(
        height=height,
        margin={"l": 70, "r": 110, "t": 56, "b": 90},
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["surface"],
        showlegend=False,
        font={"family": CHART_FONT, "color": COLORS["text"]},
        xaxis={"visible": False, "range": [0, 1], "fixedrange": True},
        yaxis={"visible": False, "range": [0, row_count + 2.4], "fixedrange": True},
    )
                                                                                             
    fig.add_trace(
        go.Scatter(
            x=[0],
            y=[0],
            mode="markers",
            marker={"size": 0.1, "color": "rgba(0,0,0,0)"},
            hoverinfo="skip",
            showlegend=False,
            opacity=0,
        )
    )

    is_service_cluster_queue = {"service_cluster_code", "service_cluster"}.issubset(plot_df.columns)
    if is_service_cluster_queue:
        headers = [
            ("Code", 0.04),
            ("Service Cluster", 0.15),
            ("# Responses", 0.55),
            ("iCX", 0.65),
            ("Crit.", 0.73),
            ("Attention Score", 0.81),
        ]
        code_x = 0.04
        detail_x = 0.15
        responses_x = 0.55
        pill_x0, pill_x1 = 0.64, 0.69
        crit_x = 0.73
        detail_limit = 54
    elif show_code_column:
        headers = [
            ("Code", 0.04),
            (item_label_header, 0.15),
            ("# Responses", 0.55),
            ("iCX", 0.65),
            ("Crit.", 0.73),
            ("Attention Score", 0.81),
        ]
        code_x = 0.04
        detail_x = 0.15
        responses_x = 0.55
        pill_x0, pill_x1 = 0.64, 0.69
        crit_x = 0.73
        detail_limit = 46
    else:
        headers = [
            (item_label_header, 0.04),
            ("# Responses", 0.54),
            ("iCX", 0.64),
            ("Crit.", 0.72),
            ("Attention Score", 0.80),
        ]
        code_x = None
        detail_x = 0.04
        responses_x = 0.54
        pill_x0, pill_x1 = 0.63, 0.68
        crit_x = 0.72
        detail_limit = 58

    header_y = row_count + 1.2
    for text, x_pos in headers:
        fig.add_annotation(
            x=x_pos,
            y=header_y,
            text=text,
            showarrow=False,
            xanchor="left",
            font={"size": QUEUE_HEADER_FONT_SIZE, "color": COLORS["muted"]},
        )

    for display_index, row in enumerate(plot_df.itertuples(index=False)):
        y_pos = row_count - display_index
        fill = "#EAF3FF" if display_index % 2 == 0 else "#FFFFFF"
        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=0.03,
            x1=0.98,
            y0=y_pos - QUEUE_ROW_HALF_HEIGHT,
            y1=y_pos + QUEUE_ROW_HALF_HEIGHT,
            fillcolor=fill,
            line={"width": 0},
            layer="below",
        )

        if is_service_cluster_queue:
            code_text = str(row.service_cluster_code)
            detail_text = _truncate_annotation_text(str(row.service_cluster), detail_limit)
        else:
            code_text = str(row.label_short)
            detail_text = _truncate_annotation_text(str(row.label_full), detail_limit)
        if code_x is not None:
            _add_table_annotation(fig, code_x, y_pos, code_text, size=QUEUE_PRIMARY_FONT_SIZE)
        _add_table_annotation(fig, detail_x, y_pos, detail_text, size=QUEUE_DETAIL_FONT_SIZE)
        _add_table_annotation(
            fig,
            responses_x,
            y_pos,
            f"{int(row.ratings):,}",
            size=QUEUE_PRIMARY_FONT_SIZE,
        )

        pill_color = _icx_status_color(float(row.nps))
        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=pill_x0,
            x1=pill_x1,
            y0=y_pos - QUEUE_PILL_HALF_HEIGHT,
            y1=y_pos + QUEUE_PILL_HALF_HEIGHT,
            fillcolor=pill_color,
            line={"color": pill_color},
            layer="above",
        )
        fig.add_annotation(
            x=(pill_x0 + pill_x1) / 2,
            y=y_pos,
            text=f"{float(row.nps):.1f}",
            showarrow=False,
            font={
                "size": QUEUE_PILL_FONT_SIZE,
                "color": _pill_text_color(float(row.nps)),
            },
        )
        _add_table_annotation(
            fig,
            crit_x,
            y_pos,
            f"{float(row.avg_criticality):.2f}",
            size=QUEUE_PRIMARY_FONT_SIZE,
        )

        bar_track_x0, bar_track_x1 = 0.81, 0.92
        fig.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=bar_track_x0,
            x1=bar_track_x1,
            y0=y_pos - QUEUE_BAR_HALF_HEIGHT,
            y1=y_pos + QUEUE_BAR_HALF_HEIGHT,
            fillcolor="#E7EEF8",
            line={"color": "#E7EEF8"},
            layer="below",
        )
        bar_x1 = bar_track_x0 + (bar_track_x1 - bar_track_x0) * (
            float(row.attention_score) / max_attention
        )
        if float(row.attention_score) > 0:
            bar_color = _icx_status_color(float(row.nps))
            fig.add_shape(
                type="rect",
                xref="x",
                yref="y",
                x0=bar_track_x0,
                x1=bar_x1,
                y0=y_pos - QUEUE_BAR_HALF_HEIGHT,
                y1=y_pos + QUEUE_BAR_HALF_HEIGHT,
                fillcolor=bar_color,
                line={"color": bar_color},
                layer="above",
            )
        _add_table_annotation(
            fig,
            0.945,
            y_pos,
            f"{float(row.attention_score):,.0f}",
            size=QUEUE_PRIMARY_FONT_SIZE,
            color=COLORS["muted"],
        )

    return fig


def build_xfn_division_mix_pie(
    data: pd.DataFrame,
    title: str,
    subtitle: str,
) -> go.Figure:
    if data.empty:
        return empty_figure(title, "No Cross-Functional Teams division rows are available.")

    plot_df = data.copy()
    color_steps = max(len(plot_df) - 1, 1)
    colors = [
        _interpolate_hex("#0A3FB8", "#EDF4FF", index / color_steps)
        for index in range(len(plot_df))
    ]
    first_share = (
        float(plot_df["ratings"].iloc[0]) / float(plot_df["ratings"].sum())
        if float(plot_df["ratings"].sum()) > 0
        else 0
    )
    first_span = first_share * 360
    rotation = 90 - (first_span / 2)
    share_labels = (
        plot_df["ratings"].astype(int).astype(str)
        + "/"
        + str(int(plot_df["ratings"].sum()))
        + " ("
        + ((plot_df["ratings"] / plot_df["ratings"].sum()) * 100).round(0).astype(int).astype(str)
        + "%)"
    )
    fig = go.Figure(
        data=[
            go.Pie(
                labels=plot_df["label_full"],
                values=plot_df["ratings"],
                hole=0,
                sort=False,
                direction="clockwise",
                rotation=rotation,
                marker={"colors": colors[: len(plot_df)], "line": {"color": "#FFFFFF", "width": 2}},
                textinfo="text",
                textposition="outside",
                texttemplate="<b>%{label}</b><br>%{customdata[1]}",
                textfont={"size": 13},
                automargin=True,
                customdata=np.stack(
                    [
                        plot_df["ratings"].astype(int),
                        share_labels.astype(str),
                    ],
                    axis=-1,
                ),
                hovertemplate=(
                    "<b>%{label}</b><br>"
                    "Responses: %{customdata[0]:,.0f}<br>"
                    "Share: %{customdata[1]}<extra></extra>"
                ),
            )
        ]
    )
    fig.update_layout(
        height=680,
        margin={"l": 210, "r": 210, "t": 20, "b": 40},
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["surface"],
        font={"family": CHART_FONT, "color": COLORS["text"]},
        showlegend=False,
        uniformtext={"mode": "hide", "minsize": 10},
    )
    return fig


def build_frequency_gap_finder(
    data: pd.DataFrame,
    title: str,
    subtitle: str,
    frequency_a: str,
    frequency_b: str,
    top_n: int | None = 15,
) -> go.Figure:
    if data.empty:
        return empty_figure(title, "No frequency gap rows match the current filters.")

    plot_df = data.copy()
    if top_n is not None:
        plot_df = plot_df.head(top_n)
    if plot_df.empty:
        return empty_figure(title, "No frequency gap rows match the current filters.")

    row_count = len(plot_df)
    y_positions = list(range(row_count, 0, -1))
    fig = go.Figure()
    for y_pos, row in zip(y_positions, plot_df.itertuples(index=False)):
        fig.add_trace(
            go.Scatter(
                x=[row.nps_a, row.nps_b],
                y=[y_pos, y_pos],
                mode="lines",
                line={"color": "#C9D8EA", "width": 5},
                hoverinfo="skip",
                showlegend=False,
            )
        )

    fig.add_trace(
        go.Scatter(
            x=plot_df["nps_a"],
            y=y_positions,
            mode="markers",
            name=FREQUENCY_DISPLAY_LABELS.get(frequency_a, frequency_a),
            marker={
                "size": 14,
                "color": frequency_comparison_color(frequency_a),
                "line": {"color": "#FFFFFF", "width": 2.4},
            },
            customdata=plot_df[["label_full", "responses_a", "nps_a"]],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                f"{FREQUENCY_DISPLAY_LABELS.get(frequency_a, frequency_a)}<br>"
                "iCX: %{customdata[2]:.2f}<br>"
                "Responses: %{customdata[1]:,.0f}<extra></extra>"
            ),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=plot_df["nps_b"],
            y=y_positions,
            mode="markers",
            name=FREQUENCY_DISPLAY_LABELS.get(frequency_b, frequency_b),
            marker={
                "size": 14,
                "color": frequency_comparison_color(frequency_b),
                "line": {"color": "#FFFFFF", "width": 2.4},
            },
            customdata=plot_df[["label_full", "responses_b", "nps_b"]],
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                f"{FREQUENCY_DISPLAY_LABELS.get(frequency_b, frequency_b)}<br>"
                "iCX: %{customdata[2]:.2f}<br>"
                "Responses: %{customdata[1]:,.0f}<extra></extra>"
            ),
        )
    )

    for y_pos, row in zip(y_positions, plot_df.itertuples(index=False)):
        fig.add_annotation(
            x=104,
            y=y_pos,
            text=f"<b>{float(row.gap_points):.1f} pts</b>",
            showarrow=False,
            xanchor="left",
            font={"size": 15, "color": COLORS["text"]},
        )

    fig.add_vline(x=NPS_THRESHOLD, line={"color": COLORS["deep"], "width": 2})
    fig.update_layout(
        height=max(560, 260 + row_count * 34),
        margin={"l": 130, "r": 170, "t": 56, "b": 130},
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["surface"],
        legend={
            "orientation": "h",
            "yanchor": "bottom",
            "y": -0.22,
            "xanchor": "center",
            "x": 0.52,
            "bgcolor": "#FFFFFF",
            "bordercolor": COLORS["border"],
            "borderwidth": 1,
            "font": {"size": 15, "color": COLORS["text"]},
        },
        font={"family": CHART_FONT, "color": COLORS["text"]},
    )
    fig.update_xaxes(
        title="iCX score",
        range=[0, 112],
        tickmode="array",
        tickvals=[0, 30, 50, 70, 90, 100],
        showgrid=True,
        gridcolor=COLORS["grid"],
        zeroline=False,
        linecolor=COLORS["border"],
        title_font={"size": 16, "color": COLORS["text"]},
        tickfont={"size": 13, "color": COLORS["muted"]},
    )
    fig.update_yaxes(
        tickmode="array",
        tickvals=y_positions,
        ticktext=plot_df["label_short"],
        range=[0.3, row_count + 0.7],
        showgrid=False,
        zeroline=False,
        linecolor=COLORS["border"],
        tickfont={"size": 16, "color": COLORS["text"]},
    )
    fig.add_annotation(
        x=NPS_THRESHOLD,
        y=row_count + 0.6,
        text="70 iCX",
        showarrow=False,
        yanchor="bottom",
        font={"size": 13, "color": COLORS["deep"]},
    )
    fig.add_annotation(
        x=104,
        y=row_count + 0.6,
        text="Gap",
        showarrow=False,
        xanchor="left",
        yanchor="bottom",
        font={"size": 14, "color": COLORS["muted"]},
    )
    return fig


def build_all_frequency_gap_ranking(
    data: pd.DataFrame,
    title: str,
    subtitle: str,
    top_n: int | None = 20,
) -> go.Figure:
    if data.empty:
        return empty_figure(title, "No cross-frequency gap rows match the current filters.")

    plot_df = data.copy()
    if top_n is not None:
        plot_df = plot_df.head(top_n)
    if plot_df.empty:
        return empty_figure(title, "No cross-frequency gap rows match the current filters.")

    plot_df["pair_label"] = (
        plot_df["label_short"].astype(str)
        + " | "
        + plot_df["frequency_a"].map(FREQUENCY_SHORT_LABELS).fillna(plot_df["frequency_a"])
        + " vs "
        + plot_df["frequency_b"].map(FREQUENCY_SHORT_LABELS).fillna(plot_df["frequency_b"])
    )
    plot_df["pair_full"] = (
        plot_df["label_full"].astype(str)
        + " | "
        + plot_df["frequency_a"].map(FREQUENCY_DISPLAY_LABELS).fillna(plot_df["frequency_a"])
        + " vs "
        + plot_df["frequency_b"].map(FREQUENCY_DISPLAY_LABELS).fillna(plot_df["frequency_b"])
    )
    plot_df["bar_color"] = plot_df["lower_nps"].map(icx_color)

    max_gap = max(float(plot_df["gap_points"].max()), 1.0)
    fig = go.Figure(
        data=[
            go.Bar(
                x=plot_df["gap_points"],
                y=plot_df["pair_label"],
                orientation="h",
                marker={"color": plot_df["bar_color"], "line": {"color": "#FFFFFF", "width": 1.2}},
                text=[f"{float(value):.1f} pts" for value in plot_df["gap_points"]],
                textposition="outside",
                cliponaxis=False,
                customdata=plot_df[
                    [
                        "pair_full",
                        "gap_points",
                        "frequency_a",
                        "nps_a",
                        "responses_a",
                        "frequency_b",
                        "nps_b",
                        "responses_b",
                        "combined_responses",
                        "lower_nps",
                    ]
                ],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Gap: %{customdata[1]:.2f} pts<br>"
                    "%{customdata[2]} iCX: %{customdata[3]:.2f} "
                    "(n=%{customdata[4]:,.0f})<br>"
                    "%{customdata[5]} iCX: %{customdata[6]:.2f} "
                    "(n=%{customdata[7]:,.0f})<br>"
                    "Combined responses: %{customdata[8]:,.0f}<br>"
                    "Lower iCX in pair: %{customdata[9]:.2f}<extra></extra>"
                ),
            )
        ]
    )
    fig.update_layout(
        height=max(560, 270 + len(plot_df) * 28),
        margin={"l": 140, "r": 110, "t": 48, "b": 95},
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["surface"],
        font={"family": CHART_FONT, "color": COLORS["text"]},
    )
    fig.update_xaxes(
        title="Absolute iCX gap (points)",
        range=[0, max_gap + max(4.0, max_gap * 0.18)],
        showgrid=True,
        gridcolor=COLORS["grid"],
        zeroline=False,
        linecolor=COLORS["border"],
        title_font={"size": 16, "color": COLORS["text"]},
        tickfont={"size": 13, "color": COLORS["muted"]},
    )
    fig.update_yaxes(
        autorange="reversed",
        showgrid=False,
        zeroline=False,
        linecolor=COLORS["border"],
        tickfont={"size": 14, "color": COLORS["text"]},
    )
    return fig


def empty_figure(title: str, message: str) -> go.Figure:
    fig = go.Figure()
    fig.update_layout(
        height=620,
        margin={"l": 40, "r": 40, "t": 32, "b": 40},
        paper_bgcolor=COLORS["background"],
        plot_bgcolor=COLORS["surface"],
        font={"family": CHART_FONT, "color": COLORS["text"]},
        xaxis={"visible": False},
        yaxis={"visible": False},
        annotations=[
            {
                "text": message,
                "showarrow": False,
                "xref": "paper",
                "yref": "paper",
                "x": 0.5,
                "y": 0.5,
                "font": {"size": 18, "color": COLORS["muted"]},
                "align": "center",
            }
        ],
    )
    return fig


def _add_external_scatter_labels(
    fig: go.Figure,
    plot_df: pd.DataFrame,
    x_values: pd.Series,
    y_values: pd.Series,
    x_range: list[float],
    y_range: list[float],
    vertical_line: float,
    score_threshold: float,
    label_font_size: int = 13,
    label_scale: float = 1.05,
) -> None:
    if plot_df.empty:
        return

    label_scale = _clamp_scatter_size_scale(label_scale)
    offsets = _external_scatter_label_offsets(
        plot_df=plot_df,
        marker_df=plot_df,
        x_values=x_values,
        y_values=y_values,
        x_range=x_range,
        y_range=y_range,
        vertical_line=vertical_line,
        score_threshold=score_threshold,
        label_scale=label_scale,
    )
    for index, point in plot_df.iterrows():
        ax, ay = offsets.get(index, (30, -30))
        fig.add_annotation(
            x=float(x_values.loc[index]),
            y=float(y_values.loc[index]),
            xref="x",
            yref="y",
            text=_scatter_label_text(str(point["label_short"])),
            showarrow=True,
            arrowhead=0,
            arrowwidth=1.2,
            arrowsize=1,
            arrowcolor=COLORS["muted"],
            standoff=4,
            ax=ax,
            ay=ay,
            axref="pixel",
            ayref="pixel",
            align="center",
            bgcolor="rgba(255,255,255,0.94)",
            bordercolor=COLORS["border"],
            borderwidth=1,
            borderpad=2,
            font={"size": label_font_size, "color": COLORS["text"], "family": CHART_FONT},
        )


def _external_scatter_label_offsets(
    plot_df: pd.DataFrame,
    marker_df: pd.DataFrame,
    x_values: pd.Series,
    y_values: pd.Series,
    x_range: list[float],
    y_range: list[float],
    vertical_line: float,
    score_threshold: float,
    label_scale: float = 1.05,
) -> dict[int, tuple[int, int]]:
    x_min, x_max = x_range
    y_min, y_max = y_range
    x_span = max(x_max - x_min, 0.001)
    y_span = max(y_max - y_min, 0.001)
    plot_width = 1420
    plot_height = 650
    marker_rects = _scatter_marker_rects(
        plot_df=marker_df,
        x_values=x_values,
        y_values=y_values,
        x_min=x_min,
        x_span=x_span,
        y_min=y_min,
        y_span=y_span,
        plot_width=plot_width,
        plot_height=plot_height,
    )
    placed_rects: list[tuple[float, float, float, float]] = []
    offsets: dict[int, tuple[int, int]] = {}
    dense_labels = len(plot_df) > 22

    work = plot_df.copy()
    work["_label_priority"] = (
        work["ratings"].clip(lower=1)
        + np.where(work["small_n"], 0, 100000)
        + np.where(work["nps"].lt(NPS_THRESHOLD), 50000, 0)
    )
    ordered = work.sort_values(
        ["_label_priority", "ratings", "nps"],
        ascending=[False, False, True],
    )

    for index, point in ordered.iterrows():
        point_x = ((float(x_values.loc[index]) - x_min) / x_span) * plot_width
        point_y = (1 - ((float(y_values.loc[index]) - y_min) / y_span)) * plot_height
        label = str(point["label_short"])
        label_width, label_height = _scatter_label_dimensions(label, label_scale=label_scale)
        x_side = -1 if float(x_values.loc[index]) < vertical_line else 1
        y_side = -1 if float(y_values.loc[index]) >= score_threshold else 1
        standard_candidates = _quadrant_label_candidates(
            x_side=x_side,
            y_side=y_side,
            label_width=label_width,
            label_height=label_height,
            marker_size=float(point["marker_size"]),
            dense=dense_labels,
        )
        if dense_labels:
            candidates = _label_specific_candidates(label) + standard_candidates
        else:
            candidates = _label_specific_candidates(label) or standard_candidates

        best_offset = candidates[0]
        best_score = float("inf")
        best_rect = (0.0, 0.0, 0.0, 0.0)
        for candidate in candidates:
            center_x = point_x + candidate[0]
            center_y = point_y + candidate[1]
            rect = (
                center_x - label_width / 2,
                center_y - label_height / 2,
                center_x + label_width / 2,
                center_y + label_height / 2,
            )
            overlap = sum(_rect_overlap_area(rect, other) for other in placed_rects)
            outside_penalty = (
                max(0, -rect[0])
                + max(0, -rect[1])
                + max(0, rect[2] - plot_width)
                + max(0, rect[3] - plot_height)
            )
            own_marker_overlap = _rect_overlap_area(rect, marker_rects[int(index)])
            marker_overlap = sum(
                _rect_overlap_area(rect, marker_rect)
                for marker_index, marker_rect in marker_rects.items()
                if marker_index != int(index)
            )
            distance_penalty = (abs(candidate[0]) + abs(candidate[1])) * 0.12
            slant_penalty = (
                80 if dense_labels and candidate[0] != 0 and candidate[1] != 0
                else 180 if candidate[0] != 0 and candidate[1] != 0
                else 0
            )
            score = (
                own_marker_overlap * (2600 if dense_labels else 1500)
                + marker_overlap * (2200 if dense_labels else 1500)
                + overlap * (5200 if dense_labels else 1000)
                + outside_penalty * (1.2 if dense_labels else 4)
                + distance_penalty
                + slant_penalty
            )
            if score < best_score:
                best_score = score
                best_offset = candidate
                best_rect = rect

        offsets[int(index)] = best_offset
        placed_rects.append(best_rect)

    return offsets


def _scatter_marker_rects(
    plot_df: pd.DataFrame,
    x_values: pd.Series,
    y_values: pd.Series,
    x_min: float,
    x_span: float,
    y_min: float,
    y_span: float,
    plot_width: float,
    plot_height: float,
) -> dict[int, tuple[float, float, float, float]]:
    rects: dict[int, tuple[float, float, float, float]] = {}
    for index, point in plot_df.iterrows():
        center_x = ((float(x_values.loc[index]) - x_min) / x_span) * plot_width
        center_y = (1 - ((float(y_values.loc[index]) - y_min) / y_span)) * plot_height
        radius = float(point["marker_size"]) / 2 + 7
        rects[int(index)] = (
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
        )
    return rects


def _scatter_label_text(label: str) -> str:
    return "<br>".join(html.escape(line) for line in _scatter_label_lines(label))


def _scatter_label_dimensions(label: str, label_scale: float = 1.0) -> tuple[float, float]:
    lines = _scatter_label_lines(label)
    scale = _clamp_scatter_size_scale(label_scale)
    width = min(
        210 * scale,
        max(44 * scale, max(len(line) for line in lines) * 9.2 * scale + 26 * scale),
    )
    height = 22 * scale * len(lines) + 10 * scale
    return width, height


def _scatter_label_lines(label: str, max_chars: int = 24, max_lines: int = 3) -> list[str]:
    label = str(label)
    if len(label) <= max_chars:
        return [label]

    words = label.split()
    if len(words) <= 1:
        return [label]

    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > max_chars:
            lines.append(current)
            current = word
            if len(lines) == max_lines - 1:
                break
        else:
            current = candidate

    remaining_words = words[sum(len(line.split()) for line in lines):]
    if len(lines) == max_lines - 1 and remaining_words:
        final_line = " ".join(remaining_words)
        if len(final_line) > max_chars + 6:
            final_line = final_line[: max_chars + 3].rstrip() + "..."
        lines.append(final_line)
    elif current:
        lines.append(current)

    return lines[:max_lines] or [label]


def _quadrant_label_candidates(
    x_side: int,
    y_side: int,
    label_width: float,
    label_height: float,
    marker_size: float,
    dense: bool = False,
) -> list[tuple[int, int]]:
    marker_radius = marker_size / 2 + 7
    min_x = int(np.ceil(marker_radius + label_width / 2 + 8))
    min_y = int(np.ceil(marker_radius + label_height / 2 + 8))
    near_x = int(round(min_x * 0.86))
    near_y = int(round(min_y * 0.86))
    candidates = [
        (x_side * min_x, 0),
        (x_side * int(round(min_x * 0.85)), 0),
        (0, y_side * min_y),
        (0, y_side * int(round(min_y * 0.85))),
        (-x_side * min_x, 0),
        (0, -y_side * min_y),
        (x_side * min_x, y_side * min_y),
        (x_side * near_x, y_side * min_y),
        (x_side * min_x, y_side * near_y),
        (-x_side * min_x, y_side * min_y),
        (x_side * min_x, -y_side * min_y),
        (-x_side * min_x, -y_side * min_y),
        (x_side * int(round(min_x * 1.18)), 0),
        (0, y_side * int(round(min_y * 1.18))),
        (-x_side * int(round(min_x * 1.18)), 0),
        (0, -y_side * int(round(min_y * 1.18))),
        (x_side * int(round(min_x * 1.18)), y_side * int(round(min_y * 0.72))),
        (x_side * int(round(min_x * 0.72)), y_side * int(round(min_y * 1.18))),
    ]
    if dense:
        candidates.extend(_near_label_ring_candidates(min_x=min_x, min_y=min_y))
    return _cap_label_offsets(_unique_offsets(candidates))


def _near_label_ring_candidates(min_x: int, min_y: int) -> list[tuple[int, int]]:
    candidates: list[tuple[int, int]] = []
    for scale in [1.0, 1.18, 1.36, 1.55]:
        x = int(round(min_x * scale))
        y = int(round(min_y * scale))
        candidates.extend(
            [
                (x, 0),
                (-x, 0),
                (0, y),
                (0, -y),
                (x, int(round(y * 0.55))),
                (x, -int(round(y * 0.55))),
                (-x, int(round(y * 0.55))),
                (-x, -int(round(y * 0.55))),
                (int(round(x * 0.55)), y),
                (int(round(x * 0.55)), -y),
                (-int(round(x * 0.55)), y),
                (-int(round(x * 0.55)), -y),
            ]
        )
    return candidates


def _cap_label_offsets(offsets: list[tuple[int, int]]) -> list[tuple[int, int]]:
    capped: list[tuple[int, int]] = []
    max_offset = BLUE_SCATTER_LABEL_MAX_OFFSET_PX
    for ax, ay in offsets:
        if max(abs(ax), abs(ay)) <= max_offset:
            capped.append((ax, ay))
            continue

        distance = max(abs(ax), abs(ay), 1)
        scale = max_offset / distance
        capped.append((int(round(ax * scale)), int(round(ay * scale))))
    return _unique_offsets(capped)


def _unique_offsets(offsets: list[tuple[int, int]]) -> list[tuple[int, int]]:
    seen: set[tuple[int, int]] = set()
    unique: list[tuple[int, int]] = []
    for offset in offsets:
        if offset in seen:
            continue
        seen.add(offset)
        unique.append(offset)
    return unique


def _label_specific_candidates(label: str) -> list[tuple[int, int]]:
    return []


def _rect_overlap_area(
    first: tuple[float, float, float, float],
    second: tuple[float, float, float, float],
) -> float:
    overlap_width = max(0.0, min(first[2], second[2]) - max(first[0], second[0]))
    overlap_height = max(0.0, min(first[3], second[3]) - max(first[1], second[1]))
    return overlap_width * overlap_height


def _matrix_values(
    data: pd.DataFrame,
    value_col: str,
    row_order: list[str],
    col_order: list[str],
) -> np.ndarray:
    pivot = data.pivot(
        index="criticality_normalized",
        columns="frequency_normalized",
        values=value_col,
    )
    pivot = pivot.reindex(index=row_order, columns=col_order)
    return pivot.to_numpy(dtype=float)


def _attention_text_color(nps: float) -> str:
    return icx_text_color(nps)


def _icx_status_color(nps: float) -> str:
    return blue_band_color(nps)


def _pill_text_color(nps: float) -> str:
    return icx_text_color(nps)


def _truncate_annotation_text(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)].rstrip() + "..."


def _wrap_annotation_text(text: str, limit: int = 30) -> str:
    """Wrap a table label without dropping words or hiding the full name."""
    words = str(text).split()
    if not words:
        return ""
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= limit:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return "<br>".join(html.escape(line) for line in lines)


def _table_annotation(
    x: float,
    y: float,
    text: str,
    size: int = 14,
    color: str | None = None,
    allow_html: bool = False,
) -> dict:
    return {
        "x": x,
        "y": y,
        "text": str(text) if allow_html else html.escape(str(text)),
        "showarrow": False,
        "xanchor": "left",
        "font": {"size": size, "color": color or COLORS["text"]},
    }


def _add_table_annotation(
    fig: go.Figure,
    x: float,
    y: float,
    text: str,
    size: int = 14,
    color: str | None = None,
) -> None:
    fig.add_annotation(**_table_annotation(x, y, text, size=size, color=color))


def _blue_band_shapes(y_range: list[float]) -> list[dict]:
    return [
        {
            "type": "line",
            "xref": "paper",
            "yref": "y",
            "x0": 0,
            "x1": 1,
            "y0": threshold,
            "y1": threshold,
            "line": {"color": "#8FA8C7", "width": 2.5},
            "layer": "above",
        }
        for threshold in [0, 30, NPS_THRESHOLD]
        if y_range[0] <= threshold <= y_range[1]
    ]


def _blue_band_annotations(
    y_range: list[float],
    label_scale: float = 1.05,
) -> list[dict]:
    annotations: list[dict] = []
    scale = _clamp_scatter_size_scale(label_scale)
    for band in BLUE_QUEUE_ORDER:
        low, high = _blue_band_visual_range(band)
        visible_low = max(low, y_range[0])
        visible_high = min(high, y_range[1])
        if visible_high < visible_low:
            continue

        label_y = visible_low + (visible_high - visible_low) / 2
        color = BLUE_CATEGORY_COLORS[band]
        annotations.append(
            {
                "x": 1.015,
                "y": label_y,
                "xref": "paper",
                "yref": "y",
                "text": band,
                "showarrow": False,
                "align": "center",
                "xanchor": "left",
                "font": {
                    "size": max(
                        14,
                        int(round(BLUE_SCATTER_BASE_BAND_LABEL_FONT_SIZE * scale)),
                    ),
                    "color": _contrast_text_color(color),
                    "family": CHART_FONT,
                },
                "bgcolor": color,
                "bordercolor": color,
                "borderpad": max(5, int(round(7 * scale))),
            }
        )
    return annotations


def _packed_positions(
    plot_df: pd.DataFrame,
    kind: PlotKind,
    x_metric: pd.Series,
    x_range: list[float],
    y_range: list[float],
    vertical_line: float,
    score_threshold: float,
) -> tuple[pd.Series, pd.Series]:
    if plot_df.empty:
        return x_metric, plot_df["nps"]

    x_min, x_max = x_range
    y_min, y_max = y_range
    x_span = x_max - x_min
    y_span = y_max - y_min
    plot_width_px = 1500
    plot_height_px = 720

    working = pd.DataFrame(
        {
            "index": plot_df.index,
            "label": plot_df["hover_title"].astype(str),
            "x": x_metric.astype(float),
            "y": plot_df["nps"].astype(float),
            "size": plot_df["marker_size"].astype(float),
        }
    )
    working = working.sort_values(["x", "y", "label"], ascending=[True, True, True])

    placed: list[dict[str, float]] = []
    out_x: dict[int, float] = {}
    out_y: dict[int, float] = {}

    max_dx = 0.17 if kind == "frequency" else 0.075
    max_dy = 0.15 if kind == "frequency" else 0.08
    candidates = _packing_candidates(max_dx=max_dx, max_dy=max_dy)

    for row in working.itertuples(index=False):
        raw_x_norm = (float(row.x) - x_min) / x_span
        raw_y_norm = (float(row.y) - y_min) / y_span
        radius_x = ((float(row.size) + 10) / 2) / plot_width_px
        radius_y = ((float(row.size) + 10) / 2) / plot_height_px

        best = None
        best_score = float("inf")
        for dx, dy in candidates:
            candidate_x = raw_x_norm + dx
            candidate_y = raw_y_norm + dy
            candidate_x, candidate_y = _keep_candidate_in_quadrant(
                kind=kind,
                raw_x_norm=raw_x_norm,
                raw_y_norm=raw_y_norm,
                candidate_x=candidate_x,
                candidate_y=candidate_y,
                x_min=x_min,
                x_span=x_span,
                y_min=y_min,
                y_span=y_span,
                vertical_line=vertical_line,
                score_threshold=score_threshold,
            )
            collision_score = 0.0
            for prior in placed:
                x_gap = abs(candidate_x - prior["x"])
                y_gap = abs(candidate_y - prior["y"])
                required_x = (radius_x + prior["rx"]) * 1.07
                required_y = (radius_y + prior["ry"]) * 1.07
                if x_gap < required_x and y_gap < required_y:
                    collision_score += (
                        (required_x - x_gap) / required_x
                        + (required_y - y_gap) / required_y
                    )
            movement = abs(dx) * 0.55 + abs(dy)
            score = collision_score * 100 + movement
            if score < best_score:
                best_score = score
                best = (candidate_x, candidate_y, collision_score)
            if collision_score == 0:
                break

        assert best is not None
        placed_x, placed_y, _ = best
        placed_x = float(np.clip(placed_x, 0.0, 1.0))
        placed_y = float(np.clip(placed_y, 0.0, 1.0))
        placed.append({"x": placed_x, "y": placed_y, "rx": radius_x, "ry": radius_y})
        out_x[int(row.index)] = x_min + placed_x * x_span
        out_y[int(row.index)] = y_min + placed_y * y_span

    return (
        pd.Series(out_x).reindex(plot_df.index),
        pd.Series(out_y).reindex(plot_df.index),
    )


def _packing_candidates(max_dx: float, max_dy: float) -> list[tuple[float, float]]:
    candidates: list[tuple[float, float]] = [(0.0, 0.0)]
    for ring in range(1, 24):
        radius = ring / 23
        points = max(12, ring * 10)
        for point in range(points):
            angle = (2 * np.pi * point) / points
            candidates.append(
                (
                    float(np.cos(angle) * max_dx * radius),
                    float(np.sin(angle) * max_dy * radius),
                )
            )
    return candidates


def _keep_candidate_in_quadrant(
    kind: PlotKind,
    raw_x_norm: float,
    raw_y_norm: float,
    candidate_x: float,
    candidate_y: float,
    x_min: float,
    x_span: float,
    y_min: float,
    y_span: float,
    vertical_line: float,
    score_threshold: float,
) -> tuple[float, float]:
    score = y_min + raw_y_norm * y_span
    band = classify_icx_score_band(score)
    if band in BLUE_QUEUE_ORDER:
        band_low, band_high = _blue_band_visual_range(str(band))
        low_norm = (max(float(band_low), y_min) - y_min) / y_span
        high_norm = (min(float(band_high), y_min + y_span) - y_min) / y_span
        if low_norm <= high_norm:
            candidate_y = float(np.clip(candidate_y, low_norm + 0.006, high_norm - 0.006))
    return candidate_x, candidate_y
