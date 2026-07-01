"""
utils/plots.py — Shared Plotly figure factory with PitWall dark theme
"""

import plotly.graph_objects as go
import plotly.express as px

DARK_BG    = "#0A0A0A"
PANEL_BG   = "#111111"
BORDER     = "#222222"
MUTED      = "#666666"
WHITE      = "#FFFFFF"
RED        = "#E8002D"


def base_layout(title: str = "", height: int = 420) -> dict:
    return dict(
        title=dict(text=title, font=dict(family="Exo 2", size=14, color=WHITE), x=0.0, xanchor="left"),
        paper_bgcolor=DARK_BG,
        plot_bgcolor=PANEL_BG,
        font=dict(family="Exo 2", color=WHITE, size=11),
        height=height,
        margin=dict(l=48, r=20, t=40, b=48),
        xaxis=dict(
            gridcolor=BORDER,
            zerolinecolor=BORDER,
            tickfont=dict(family="JetBrains Mono", size=10, color=MUTED),
        ),
        yaxis=dict(
            gridcolor=BORDER,
            zerolinecolor=BORDER,
            tickfont=dict(family="JetBrains Mono", size=10, color=MUTED),
        ),
        legend=dict(
            bgcolor=PANEL_BG,
            bordercolor=BORDER,
            borderwidth=1,
            font=dict(family="JetBrains Mono", size=10),
        ),
        hoverlabel=dict(
            bgcolor=PANEL_BG,
            bordercolor=BORDER,
            font=dict(family="JetBrains Mono", size=11),
        ),
    )


def apply_base(fig: go.Figure, title: str = "", height: int = 420) -> go.Figure:
    fig.update_layout(**base_layout(title, height))
    return fig


def empty_fig(message: str = "No data available") -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(color=MUTED, size=14, family="JetBrains Mono"),
    )
    fig.update_layout(**base_layout())
    return fig
