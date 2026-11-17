from __future__ import annotations

import json
from typing import Literal

import plotly
import plotly.graph_objects as go

from . import metrics
from .schemas import records
from ..icx import icx_data as icx
from ..icx import icx_visuals as visuals


def _fig_json(fig) -> dict:
    return json.loads(json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder))


def chart_payload(
    view: str,
    perspective: Literal["provider", "customer"] = "provider",
    group: str = icx.ALL_GROUPS_LABEL,
    analysis: str = "groups",
    min_ratings: int = 1,
    show_labels: bool = True,
    full_labels: bool = False,
    mean_line: bool = True,
    scatter_size: float = 1.05,
    band: str = "Busted",
) -> dict:
    title_group = group or icx.ALL_GROUPS_LABEL
    if view == "criticality-scatter":
        special_data_group = metrics.is_data_group(title_group)
        summary = metrics.summary_for_analysis(
            perspective=perspective,
            analysis=analysis,                          
            selected_group=icx.ALL_GROUPS_LABEL if analysis == "groups" else title_group,
            min_ratings=min_ratings,
        )
        global_mean = None
        if (
            perspective == "provider"
            and analysis == "territory_only"
            and title_group == icx.ALL_GROUPS_LABEL
        ):
            mean_source = summary
        else:
            mean_source = metrics.summary_for_analysis(
                "provider",
                "service_clusters",
                title_group if special_data_group else icx.ALL_GROUPS_LABEL,
            )
        if not mean_source.empty and "avg_criticality" in mean_source.columns:
            values = mean_source["avg_criticality"].dropna()
            global_mean = float(values.mean()) if not values.empty else None
        fig = visuals.build_blue_band_scatter(
            summary,
            kind="criticality",
            title="iCX score vs Criticality",
            subtitle=(
                f"Synthetic provider view | {title_group}"
                if special_data_group
                else f"{perspective.title()} perspective | {title_group}"
            ),
            highlighted_label=title_group if analysis == "groups" else None,
            show_labels=show_labels,
            use_full_labels=full_labels,
            scatter_size_scale=scatter_size,
            global_mean_criticality=global_mean,
            show_global_mean_criticality=mean_line,
            global_mean_label=(
                "All Groups territory mean criticality"
                if (
                    perspective == "provider"
                    and analysis == "territory_only"
                    and title_group == icx.ALL_GROUPS_LABEL
                )
                else "global service-cluster mean criticality"
            ),
        )
        _remove_scatter_footer_note(fig)
        if special_data_group:
            _use_synthetic_data_group_hover(fig)
            _add_data_group_note(fig)
        elif (
            perspective == "provider"
            and analysis == "territory_only"
            and title_group == icx.ALL_GROUPS_LABEL
        ):
            _add_territory_scatter_note(fig)
        elif perspective == "provider" and analysis == "service_clusters":
            _add_master_service_note(fig)
        return {"kind": "plotly", "figure": _fig_json(fig)}
    if view == "frequency-heatmap":
        df = metrics.display_rows()
        summary = icx.summarize_frequency_criticality(df, perspective, title_group)
        fig = visuals.build_frequency_criticality_heatmap(
            summary,
            title="iCX by Frequency and Criticality",
            subtitle=f"{perspective.title()} perspective | {title_group}",
        )
        return {"kind": "plotly", "figure": _fig_json(fig)}
    if view == "frequency-attention":
        df = metrics.display_rows()
        freq = icx.summarize_group_frequency_slices(df, perspective, title_group)
        attention = icx.summarize_frequency_attention(freq)
        return {"kind": "attention-queue", "rows": records(attention.head(20))}
    if view == "service-cluster-scatter":
        clusters = metrics.summary_for_analysis(
            perspective=perspective,
            analysis="service_clusters",
            selected_group=title_group,
            min_ratings=min_ratings,
        )
        fig = visuals.build_blue_band_scatter(
            clusters,
            kind="criticality",
            title="Service clusters: iCX score vs Criticality",
            subtitle=f"{perspective.title()} perspective | {title_group}",
            show_labels=show_labels,
            use_full_labels=full_labels,
            scatter_size_scale=scatter_size,
        )
        _remove_scatter_footer_note(fig)
        if perspective == "provider":
            _add_master_service_note(fig)
        return {"kind": "plotly", "figure": _fig_json(fig)}
    if view == "received-gave-gap":
        return {"kind": "plotly", "figure": _fig_json(_gap_bar_figure(metrics.received_gave_summary(title_group), "Received iCX - Gave iCX", "gap", "received vs gave"))}
    if view == "inter-intra-gap":
        return {"kind": "plotly", "figure": _fig_json(_gap_bar_figure(metrics.inter_intra_summary(title_group), "Inter iCX - Intra iCX", "gap", "inter vs intra"))}
    if view == "blue-attention-queue":
        queues = metrics.blue_service_queues(title_group, perspective)["queues"]
        queue = queues.get(band, [])
        return {"kind": "attention-queue", "rows": queue, "band": band}
    raise ValueError(f"Unknown chart view: {view}")


def _gap_bar_figure(payload: dict, title: str, value_key: str, label: str) -> go.Figure:
    rows = payload.get("rows", [])
    if not rows:
        return visuals.empty_figure(title, f"No {label} rows are available.")
    labels = [str(row.get("label_short") or row.get("label_full")) for row in rows]
    full_labels = [str(row.get("label_full")) for row in rows]
    values = [row.get(value_key) for row in rows]
    colors = [
        "#155EEF" if row.get("selected")
        else "#D92D20" if (row.get(value_key) is not None and float(row.get(value_key)) < 0)
        else "#0E7A5F"
        for row in rows
    ]
    line_colors = ["#081A33" if row.get("selected") else "#FFFFFF" for row in rows]
    line_widths = [2.5 if row.get("selected") else 1 for row in rows]
    fig = go.Figure(
        data=[
            go.Bar(
                x=values,
                y=labels,
                orientation="h",
                marker={"color": colors, "line": {"color": line_colors, "width": line_widths}},
                customdata=full_labels,
                hovertemplate="<b>%{customdata}</b><br>Gap: %{x:.2f}<extra></extra>",
            )
        ]
    )
    fig.add_vline(x=0, line={"color": "#6B7F99", "width": 1, "dash": "dot"})
    fig.update_layout(
        height=max(560, 220 + len(rows) * 30),
        margin={"l": 130, "r": 80, "t": 58, "b": 80},
        paper_bgcolor=visuals.COLORS["background"],
        plot_bgcolor=visuals.COLORS["surface"],
        font={"family": visuals.CHART_FONT, "color": visuals.COLORS["text"]},
        showlegend=False,
        title={"text": title, "x": 0.02, "xanchor": "left"},
    )
    fig.update_xaxes(title="Gap points", zeroline=False, gridcolor="#E3ECF8")
    fig.update_yaxes(autorange="reversed")
    return fig


def _remove_scatter_footer_note(fig: go.Figure) -> None:
    annotations = []
    for annotation in fig.layout.annotations or []:
        text = str(getattr(annotation, "text", ""))
        if text.startswith("BLUE thresholds:"):
            continue
        annotations.append(annotation)
    fig.update_layout(annotations=annotations)


def _add_master_service_note(fig: go.Figure) -> None:
    fig.add_annotation(
        x=0.01,
        y=-0.10,
        xref="paper",
        yref="paper",
        text=(
            "Source: active CSV dataset. "
            "N/A services and services without usable criticality are not plotted."
        ),
        showarrow=False,
        align="left",
        font={"size": 14, "color": visuals.COLORS["muted"]},
    )


def _add_territory_scatter_note(fig: go.Figure) -> None:
    fig.add_annotation(
        x=0.01,
        y=-0.10,
        xref="paper",
        yref="paper",
        text=(
            "Territory scores, rating counts, and average criticality are calculated from the active CSV."
        ),
        showarrow=False,
        align="left",
        font={"size": 14, "color": visuals.COLORS["muted"]},
    )


def _use_synthetic_data_group_hover(fig: go.Figure) -> None:
    for trace in fig.data:
        if getattr(trace, "type", None) != "scatter":
            continue
        trace.hovertemplate = (
            "<b>%{customdata[0]}</b><br>"
            "%{customdata[1]}<br>"
            "Ratings: %{customdata[2]:,.0f}<br>"
            "iCX score: %{customdata[3]:.2f}<br>"
            "BLUE band: %{customdata[4]}<br>"
            "Avg criticality: %{customdata[5]:.2f}<br>"
            "Frequency: %{customdata[6]}<br>"
            "Synthetic Data Group view; not a organization group<extra></extra>"
        )


def _add_data_group_note(fig: go.Figure) -> None:
    fig.add_annotation(
        x=0.01,
        y=-0.10,
        xref="paper",
        yref="paper",
        text=(
            "Source: Data Group service metrics. Service scores use the latest "
            "owner-supplied values; division scores use the four owner-supplied values. "
            "This synthetic view is excluded from organization group totals and rankings."
        ),
        showarrow=False,
        align="left",
        font={"size": 14, "color": visuals.COLORS["muted"]},
    )
