"""Chart builders are independent of Streamlit, so they also export to HTML."""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

COLORS = ("#2563eb", "#ef7b24")
COMPOUND_COLORS = {
    "SOFT": "#e11d48",
    "MEDIUM": "#d97706",
    "HARD": "#475569",
    "INTERMEDIATE": "#16a34a",
    "WET": "#2563eb",
    "UNKNOWN": "#94a3b8",
}
DRIVER_SYMBOLS = ("circle", "square", "diamond", "triangle-up")


def style_figure(figure, title, height=640):
    figure.update_layout(
        title=dict(text=title, font=dict(size=16), x=0),
        height=height, margin=dict(l=60, r=20, t=80, b=45),
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Arial, sans-serif", size=12, color="#253247"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
        hovermode="x unified",
        dragmode="zoom",
    )
    figure.update_xaxes(gridcolor="#edf0f5", zeroline=False, automargin=True)
    figure.update_yaxes(gridcolor="#edf0f5", zeroline=False, automargin=True, title_standoff=10)
    return figure


def telemetry_chart(telemetry, labels, start, end, title, summaries=None):
    """Three linked panels with one shared distance axis.

    Plotly's shared x axes and ``matches`` keep speed, throttle and brake on the
    same section when the user zooms or pans any panel.
    """
    figure = make_subplots(rows=3, cols=1, shared_xaxes=True,
                           row_heights=[0.5, 0.3, 0.2], vertical_spacing=0.06)
    for index, (data, label) in enumerate(zip(telemetry, labels)):
        for row, channel, unit in [(1, "Speed", " km/h"), (2, "Throttle", "%"), (3, "Brake", "")]:
            values = data[channel].astype("Float64").to_numpy(dtype=float, na_value=float("nan"))
            line = dict(color=COLORS[index], width=2, dash="solid" if index == 0 else "dash")
            if channel == "Brake":
                line["shape"] = "hv"
                status = data["Brake"].map({True: "On", False: "Off"}).fillna("Unknown")
                hover = "%{x:.0f} m · brake %{customdata}<extra>%{fullData.name}</extra>"
            else:
                status = None
                hover = f"%{{x:.0f}} m · %{{y:.1f}}{unit}<extra>%{{fullData.name}}</extra>"
            figure.add_trace(go.Scatter(
                x=data["Distance"], y=values, name=label, mode="lines",
                line=line, legendgroup=label, showlegend=row == 1,
                hovertemplate=hover, customdata=status, connectgaps=False,
            ), row=row, col=1)

    # Shade the measured section across all three panels. xref="x3" is the
    # bottom shared axis; yref="paper" spans the full figure height.
    figure.add_shape(
        type="rect", x0=start, x1=end, y0=0, y1=1, xref="x3", yref="paper",
        fillcolor="#dbeafe", opacity=0.35, line_width=0, layer="below",
    )

    if summaries:
        for index, summary in enumerate(summaries):
            if summary is None or summary.brake_distance is None:
                continue
            figure.add_trace(go.Scatter(
                x=[summary.brake_distance], y=[1.05], mode="markers",
                marker=dict(symbol="triangle-down", size=10, color=COLORS[index]),
                name=f"{labels[index]} · first On sample", showlegend=False,
                hovertemplate=("%{x:.1f} m · first recorded brake-on sample"
                               "<extra>%{fullData.name}</extra>"),
            ), row=3, col=1)

    figure.update_xaxes(range=[start, end], matches="x3")
    figure.update_xaxes(title_text="Distance into lap (m)", row=3, col=1)
    figure.update_yaxes(title_text="Speed (km/h)", row=1, col=1)
    figure.update_yaxes(title_text="Throttle (%)", row=2, col=1)
    figure.update_yaxes(title_text="Braking", tickvals=[0, 1], ticktext=["Off", "On"],
                        range=[-0.12, 1.12], row=3, col=1)
    return style_figure(figure, title)


def pace_chart(laps, drivers, title):
    """Race pace by tyre age (x), compound (colour) and stint (line)."""
    figure = go.Figure()
    for index, driver in enumerate(drivers):
        driver_laps = laps.loc[laps["Driver"] == driver]
        for stint, group in driver_laps.groupby("Stint", dropna=False):
            if group.empty:
                continue
            compound = str(group["Compound"].iloc[0]).upper()
            color = COMPOUND_COLORS.get(compound, COMPOUND_COLORS["UNKNOWN"])
            stint_label = "unknown stint" if pd.isna(stint) else f"stint {int(stint)}"
            figure.add_trace(go.Scatter(
                x=group["TyreLife"], y=group["LapSeconds"], mode="lines+markers",
                name=f"{driver} · {stint_label} · {compound}",
                line=dict(color=color, width=2, dash="solid" if index == 0 else "dash"),
                marker=dict(symbol=DRIVER_SYMBOLS[index % len(DRIVER_SYMBOLS)], size=8,
                            color=color),
                customdata=group[["LapNumber", "Compound", "Stint", "TrackStatus"]].astype(str),
                hovertemplate=(
                    "Tyre age %{x} laps · %{y:.3f} s"
                    "<br>Lap %{customdata[0]} · %{customdata[1]} · stint %{customdata[2]}"
                    "<br>Track status %{customdata[3]}"
                    "<extra>%{fullData.name}</extra>"
                ),
            ))
    figure.update_xaxes(title_text="Tyre age (laps)")
    figure.update_yaxes(title_text="Lap time (seconds)")
    return style_figure(figure, title, 480)


def stint_sequence_chart(laps, drivers, title):
    """Lap-by-lap view so stint order is visible next to the tyre-age view."""
    figure = go.Figure()
    for index, driver in enumerate(drivers):
        driver_laps = laps.loc[laps["Driver"] == driver]
        for stint, group in driver_laps.groupby("Stint", dropna=False):
            if group.empty:
                continue
            compound = str(group["Compound"].iloc[0]).upper()
            color = COMPOUND_COLORS.get(compound, COMPOUND_COLORS["UNKNOWN"])
            stint_label = "unknown stint" if pd.isna(stint) else f"stint {int(stint)}"
            figure.add_trace(go.Scatter(
                x=group["LapNumber"], y=group["LapSeconds"], mode="lines+markers",
                name=f"{driver} · {stint_label} · {compound}",
                line=dict(color=color, width=2, dash="solid" if index == 0 else "dash"),
                marker=dict(symbol=DRIVER_SYMBOLS[index % len(DRIVER_SYMBOLS)], size=8,
                            color=color),
                customdata=group[["TyreLife", "Compound", "TrackStatus"]].astype(str),
                hovertemplate=(
                    "Lap %{x} · %{y:.3f} s"
                    "<br>Tyre age %{customdata[0]} laps · %{customdata[1]}"
                    "<br>Track status %{customdata[2]}"
                    "<extra>%{fullData.name}</extra>"
                ),
            ))
    figure.update_xaxes(title_text="Race / session lap")
    figure.update_yaxes(title_text="Lap time (seconds)")
    return style_figure(figure, title, 480)
