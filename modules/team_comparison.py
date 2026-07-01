"""
pages/team_comparison.py — Head-to-head team pace, pit consistency, Cadillac trajectory
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import requests
from utils.data import (
    load_session, get_race_name_list, get_clean_laps,
    TEAM_COLORS, AVAILABLE_YEARS, get_team_color, fuel_correct
)
from utils.plots import apply_base, empty_fig


# 2026 Cadillac trajectory — qualifying gap to next team (Aston Martin) across rounds
CADILLAC_TRAJECTORY = {
    "Round": [1, 2, 3, 4, 5, 6, 7, 8],
    "Event": ["Australia", "China", "Japan", "Bahrain*", "Spain", "Monaco", "Canada", "Austria"],
    "Quali_Gap_to_Midfield": [3.1, 2.9, 2.6, None, 2.4, 2.2, 2.0, 2.1],  # seconds off midfield
    "Note": ["", "", "Ahead of Aston Martins", "", "", "Pérez P10→P15 penalty", "Best weekend", "Both retired"],
}


def render():
    st.markdown("""
    <div style="margin-bottom:1.5rem;">
        <div style="font-family:'Exo 2',sans-serif;font-weight:900;font-size:2rem;letter-spacing:-0.03em;">
            Team Comparison
        </div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#666;text-transform:uppercase;letter-spacing:0.1em;">
            Head-to-head pace · Pit stop consistency · Cadillac trajectory
        </div>
    </div>
    """, unsafe_allow_html=True)

    tabs = st.tabs(["RACE PACE COMPARISON", "PIT STOP CONSISTENCY", "CADILLAC TRAJECTORY"])

    with tabs[0]:
        _render_race_pace(AVAILABLE_YEARS)

    with tabs[1]:
        _render_pit_consistency(AVAILABLE_YEARS)

    with tabs[2]:
        _render_cadillac_trajectory()


def _render_race_pace(available_years):
    st.markdown("**Compare race pace across teams for any race**")

    c1, c2 = st.columns([1, 2])
    with c1:
        year = st.selectbox("Season", available_years, key="tc_year")
    with c2:
        races = get_race_name_list(year)
        if not races:
            st.warning("Could not load schedule.")
            return
        gp = st.selectbox("Grand Prix", races, index=min(7, len(races)-1), key="tc_gp")

    with st.spinner(f"Loading {gp} {year}…"):
        session = load_session(year, gp, "R")

    if session is None:
        st.warning("Race data not available.")
        return

    laps = get_clean_laps(session)
    if laps.empty:
        st.warning("No clean laps available.")
        return

    total_laps = int(laps["LapNumber"].max())
    laps = fuel_correct(laps, total_laps)
    pace_col = "LapTimeCorr"

    # Merge team info — try session.laps first, fall back to session.results
    try:
        team_info = (
            session.laps[["Driver", "Team"]]
            .dropna(subset=["Team"])
            .drop_duplicates(subset=["Driver"])
        )
        if team_info.empty:
            raise ValueError("empty")
        laps = laps.merge(team_info, on="Driver", how="left")
    except Exception:
        try:
            team_info = (
                session.results[["Abbreviation", "TeamName"]]
                .rename(columns={"Abbreviation": "Driver", "TeamName": "Team"})
                .dropna()
                .drop_duplicates(subset=["Driver"])
            )
            laps = laps.merge(team_info, on="Driver", how="left")
        except Exception as e:
            st.warning(f"Could not attach team names: {e}")
            return

    if "Team" not in laps.columns or laps["Team"].isna().all():
        st.warning("Team data unavailable for this session.")
        return

    laps = laps.dropna(subset=["Team", pace_col])
    if laps.empty:
        st.warning("No clean laps with team data found.")
        return

    # Team summary stats
    team_stats = (
        laps.groupby("Team")[pace_col]
        .agg(["median", "mean", "std", "count"])
        .reset_index()
        .sort_values("median")
    )
    team_stats.columns = ["Team", "Median", "Mean", "StdDev", "Laps"]

    # Bar chart: median pace
    fig = go.Figure()
    best_pace = team_stats["Median"].min()

    for _, row in team_stats.iterrows():
        color = get_team_color(row["Team"])
        gap = row["Median"] - best_pace
        is_cadillac = "cadillac" in row["Team"].lower()

        fig.add_trace(go.Bar(
            y=[row["Team"]],
            x=[row["Median"]],
            orientation="h",
            name=row["Team"],
            marker=dict(
                color=color,
                opacity=1.0 if is_cadillac else 0.75,
                line=dict(color="#fff" if is_cadillac else "rgba(0,0,0,0)", width=2 if is_cadillac else 0),
            ),
            text=f"+{gap:.3f}s" if gap > 0 else "FASTEST",
            textposition="outside",
            textfont=dict(family="JetBrains Mono", size=9, color="#888"),
            hovertemplate=f"<b>{row['Team']}</b><br>Median: {row['Median']:.3f}s<br>Gap to leader: +{gap:.3f}s<extra></extra>",
            showlegend=False,
        ))

    fig.update_layout(
        xaxis_title="Median Fuel-Corrected Lap Time (s)",
        yaxis=dict(autorange="reversed"),
        xaxis=dict(range=[best_pace - 0.5, team_stats["Median"].max() + 1.5]),
    )
    apply_base(fig, f"Race Pace Comparison — {gp} {year}", height=max(350, len(team_stats) * 32 + 80))
    st.plotly_chart(fig, use_container_width=True)

    # Gap table
    st.markdown("**PACE GAP TO FASTEST TEAM**")
    rows_html = []
    for _, row in team_stats.iterrows():
        color = get_team_color(row["Team"])
        gap = row["Median"] - best_pace
        is_cadillac = "cadillac" in row["Team"].lower()
        border = "2px solid #CC1E4A" if is_cadillac else "none"

        rows_html.append(f"""
        <div style="display:flex;align-items:center;padding:6px 0;border-bottom:1px solid #1a1a1a;
             font-size:0.82rem;{f'outline:{border};outline-offset:-1px;background:#1a0a0a;padding:6px 8px;' if is_cadillac else ''}">
            <span style="display:inline-block;width:4px;height:14px;background:{color};margin-right:10px;border-radius:1px;"></span>
            <span style="flex:1;">{row['Team']}{' ⬅' if is_cadillac else ''}</span>
            <span style="width:80px;font-family:'JetBrains Mono',monospace;color:#888;font-size:0.75rem;">{int(row['Laps'])} laps</span>
            <span style="width:70px;text-align:right;font-family:'JetBrains Mono',monospace;
                 color:{'#39FF14' if gap < 0.1 else ('#FFD700' if gap < 0.8 else '#E8002D')};">
                {'+' if gap > 0 else ''}{gap:.3f}s
            </span>
        </div>
        """)

    st.markdown(
        '<div style="background:#111;border:1px solid #222;border-radius:4px;padding:0.5rem 1rem;">'
        + "".join(rows_html)
        + "</div>",
        unsafe_allow_html=True,
    )


def _render_pit_consistency(available_years):
    st.markdown("**Pit stop execution consistency by team**")
    st.markdown('<div style="font-family:JetBrains Mono,monospace;font-size:0.7rem;color:#555;margin-bottom:1rem;">Lower standard deviation = more consistent stops. This is a key indicator of operational excellence.</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([1, 2])
    with c1:
        year = st.selectbox("Season", available_years, key="pc_year")
    with c2:
        races = get_race_name_list(year)
        if not races:
            return
        gp = st.selectbox("Grand Prix", races, index=min(7, len(races)-1), key="pc_gp")

    with st.spinner(f"Loading {gp} {year}…"):
        session = load_session(year, gp, "R")

    if session is None:
        st.warning("Data not available.")
        return

    try:
        laps = session.laps.copy()
        pit_laps = laps[laps["PitInTime"].notna()].copy()
        pit_laps["StopTime"] = (laps["PitOutTime"] - laps["PitInTime"]).dt.total_seconds()
        pit_laps = pit_laps.dropna(subset=["StopTime"])
        pit_laps = pit_laps[pit_laps["StopTime"].between(1.5, 15)]  # valid stops only

        team_pit = (
            pit_laps.groupby("Team")["StopTime"]
            .agg(["mean", "std", "count", "min"])
            .reset_index()
            .rename(columns={"mean": "AvgStop", "std": "StdDev", "count": "Stops", "min": "BestStop"})
            .dropna(subset=["StdDev"])
            .sort_values("AvgStop")
        )

        if team_pit.empty:
            st.info("No pit stop data available.")
            return

        # Scatter: mean stop time vs std dev (lower-left = best)
        fig = go.Figure()
        for _, row in team_pit.iterrows():
            color = get_team_color(row["Team"])
            is_cadillac = "cadillac" in row["Team"].lower()

            fig.add_trace(go.Scatter(
                x=[row["AvgStop"]],
                y=[row["StdDev"]],
                mode="markers+text",
                name=row["Team"],
                marker=dict(
                    color=color,
                    size=16 if is_cadillac else 12,
                    symbol="diamond" if is_cadillac else "circle",
                    line=dict(color="#fff" if is_cadillac else "rgba(0,0,0,0)", width=2),
                ),
                text=[row["Team"]],
                textposition="top center",
                textfont=dict(
                    family="JetBrains Mono",
                    size=9,
                    color="#fff" if is_cadillac else "#888",
                ),
                hovertemplate=(
                    f"<b>{row['Team']}</b><br>"
                    f"Avg stop: {row['AvgStop']:.2f}s<br>"
                    f"Std dev: {row['StdDev']:.2f}s<br>"
                    f"Stops: {int(row['Stops'])}<br>"
                    f"Best: {row['BestStop']:.2f}s<extra></extra>"
                ),
                showlegend=False,
            ))

        # Annotate quadrants
        x_mid = team_pit["AvgStop"].median()
        y_mid = team_pit["StdDev"].median()

        fig.add_annotation(x=team_pit["AvgStop"].min() + 0.1, y=team_pit["StdDev"].min() + 0.05,
                           text="⭐ FAST & CONSISTENT", font=dict(color="#39FF14", size=9, family="JetBrains Mono"),
                           showarrow=False)

        fig.update_layout(
            xaxis_title="Average Stop Time (s)",
            yaxis_title="Stop Time Std Dev (s)",
        )
        apply_base(fig, "Pit Stop Speed vs Consistency", height=420)
        st.plotly_chart(fig, use_container_width=True)

        # Table
        st.markdown("**PIT STOP STATISTICS**")
        rows_html = []
        for _, row in team_pit.iterrows():
            color = get_team_color(row["Team"])
            is_cadillac = "cadillac" in row["Team"].lower()
            rows_html.append(f"""
            <div style="display:flex;align-items:center;padding:6px 0;border-bottom:1px solid #1a1a1a;font-size:0.82rem;
                 {'background:#1a0a0a;padding:6px 8px;' if is_cadillac else ''}">
                <span style="display:inline-block;width:4px;height:14px;background:{color};margin-right:10px;border-radius:1px;"></span>
                <span style="flex:1;">{row['Team']}</span>
                <span style="width:70px;text-align:right;font-family:'JetBrains Mono',monospace;">{row['AvgStop']:.2f}s</span>
                <span style="width:70px;text-align:right;font-family:'JetBrains Mono',monospace;color:#888;">±{row['StdDev']:.2f}s</span>
                <span style="width:70px;text-align:right;font-family:'JetBrains Mono',monospace;color:#39FF14;">{row['BestStop']:.2f}s</span>
                <span style="width:50px;text-align:right;color:#555;font-size:0.75rem;">{int(row['Stops'])} stops</span>
            </div>
            """)

        st.markdown(
            '<div style="background:#111;border:1px solid #222;border-radius:4px;padding:0.5rem 1rem;">'
            + "".join(rows_html)
            + "</div>",
            unsafe_allow_html=True,
        )

    except Exception as e:
        st.warning(f"Pit consistency data unavailable: {e}")


def _render_cadillac_trajectory():
    """Cadillac's 2026 development arc."""
    st.markdown("**Cadillac F1 — 2026 Season Trajectory**")
    st.markdown('<div style="font-family:JetBrains Mono,monospace;font-size:0.7rem;color:#555;margin-bottom:1rem;">Development progression of the MAC-26 through the 2026 season. Qualifying gap to midfield (Aston Martin) as a proxy for outright pace.</div>', unsafe_allow_html=True)

    df = pd.DataFrame(CADILLAC_TRAJECTORY)
    df = df.dropna(subset=["Quali_Gap_to_Midfield"])

    fig = go.Figure()

    # Gap line
    fig.add_trace(go.Scatter(
        x=df["Round"],
        y=df["Quali_Gap_to_Midfield"],
        mode="lines+markers",
        line=dict(color="#CC1E4A", width=3),
        marker=dict(size=10, color="#CC1E4A", line=dict(color="#fff", width=2)),
        name="Gap to Aston Martin (s)",
        hovertemplate="<b>Round %{x}</b><br>%{text}<br>Gap: %{y:.2f}s<extra></extra>",
        text=df["Event"],
    ))

    # Trend line
    x = df["Round"].values
    y = df["Quali_Gap_to_Midfield"].values
    if len(x) >= 2:
        coeffs = np.polyfit(x, y, 1)
        y_trend = np.polyval(coeffs, x)
        fig.add_trace(go.Scatter(
            x=x, y=y_trend,
            mode="lines",
            line=dict(color="#CC1E4A", width=1.5, dash="dot"),
            name=f"Trend ({coeffs[0]:+.3f}s/round)",
            hoverinfo="skip",
        ))

        # Projected points finish round
        if coeffs[0] < 0:
            target_gap = 0.0
            projected_round = (target_gap - coeffs[1]) / coeffs[0]
            if projected_round > max(x):
                fig.add_vline(
                    x=projected_round,
                    line=dict(color="#FFD700", width=1.5, dash="dash"),
                    annotation_text=f"Projected midfield match: R{projected_round:.0f}",
                    annotation_font=dict(color="#FFD700", size=10, family="JetBrains Mono"),
                )

    # Notable events
    events = df[df["Note"] != ""].copy()
    for _, ev in events.iterrows():
        fig.add_annotation(
            x=ev["Round"],
            y=ev["Quali_Gap_to_Midfield"],
            text=ev["Note"],
            showarrow=True,
            arrowhead=2,
            arrowcolor="#888",
            font=dict(size=8, color="#888", family="JetBrains Mono"),
            bgcolor="#111",
            bordercolor="#333",
            borderwidth=1,
            ax=30,
            ay=-30,
        )

    fig.update_layout(
        xaxis=dict(title="Round", dtick=1, range=[0.5, 10]),
        yaxis=dict(title="Qualifying Gap to Next Team (s)", autorange="reversed"),
    )
    apply_base(fig, "Cadillac MAC-26 Development Curve — 2026", height=420)
    st.plotly_chart(fig, use_container_width=True)

    # Context cards
    st.markdown("**SEASON HIGHLIGHTS**")
    highlights = [
        ("MAC-26", "Ferrari 1.6L V6 hybrid (2026–2028). Active aero. First car named after Mario Andretti.", "#CC1E4A"),
        ("Drivers", "Pérez (6 wins) + Bottas (10 wins) = 527 GP starts combined. Most experienced new-team pairing.", "#64C4FF"),
        ("Monaco R6", "Pérez finished P10 on road — first point! Post-race 10s penalty for restart position dropped him to P15.", "#FFD700"),
        ("Staff", "595 roles posted. 143,265 applications. 520 hired. One of motorsport's largest recruitment drives.", "#39FF14"),
        ("2029 Plan", "Ferrari engines until 2028, then GM's own works power unit. Building toward full manufacturer status.", "#888"),
    ]

    cols = st.columns(len(highlights))
    for i, (title, text, color) in enumerate(highlights):
        with cols[i]:
            st.markdown(f"""
            <div class="metric-card" style="border-left-color:{color};">
                <div class="label" style="color:{color};">{title}</div>
                <div style="font-size:0.78rem;color:#ccc;line-height:1.5;margin-top:0.4rem;">{text}</div>
            </div>
            """, unsafe_allow_html=True)
