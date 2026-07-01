"""
modules/race_overview.py — Championship standings + race position trace
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from utils.data import (
    get_event_schedule, load_session, get_clean_laps,
    get_standings, TEAM_COLORS, AVAILABLE_YEARS, get_race_name_list,
    get_team_color, get_team_map
)
from utils.plots import apply_base


def render():
    st.markdown("""
    <div style="margin-bottom:1.5rem;">
        <div style="font-family:'Exo 2',sans-serif;font-weight:900;font-size:2rem;letter-spacing:-0.03em;">
            Race Overview
        </div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#666;text-transform:uppercase;letter-spacing:0.1em;">
            Championship standings · Position trace · Race results
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Controls ───────────────────────────────────────────────────────────
    c1, c2 = st.columns([1, 2])
    with c1:
        year = st.selectbox("Season", AVAILABLE_YEARS, key="ov_year")
    with c2:
        races = get_race_name_list(year)
        if not races:
            st.warning("Could not load race schedule.")
            return
        gp = st.selectbox("Grand Prix", races, index=min(7, len(races)-1), key="ov_gp")

    st.markdown('<hr style="border:none;border-top:1px solid #222;margin:1rem 0;">', unsafe_allow_html=True)

    tab_standings, tab_race = st.tabs(["CHAMPIONSHIP STANDINGS", "RACE POSITION TRACE"])

    # ── Standings tab ──────────────────────────────────────────────────────
    with tab_standings:
        # Pass year explicitly so cache key changes when year changes
        with st.spinner("Loading championship standings…"):
            drivers, constructors = get_standings(year)

        if not drivers and not constructors:
            st.info("Standings not available for this selection.")
        else:
            col_d, col_c = st.columns(2)

            with col_d:
                st.markdown("**DRIVERS' CHAMPIONSHIP**")
                if drivers:
                    rows = []
                    for d in drivers[:20]:
                        rows.append({
                            "Pos": d["position"],
                            "Driver": f"{d['Driver']['givenName']} {d['Driver']['familyName']}",
                            "Team": d["Constructors"][0]["name"] if d.get("Constructors") else "—",
                            "Points": d["points"],
                            "Wins": d["wins"],
                        })
                    _render_standings_table(pd.DataFrame(rows))

            with col_c:
                st.markdown("**CONSTRUCTORS' CHAMPIONSHIP**")
                if constructors:
                    rows = []
                    for c in constructors:
                        rows.append({
                            "Pos": c["position"],
                            "Team": c["Constructor"]["name"],
                            "Points": c["points"],
                            "Wins": c["wins"],
                        })
                    _render_standings_table(pd.DataFrame(rows))

            if constructors:
                st.plotly_chart(_constructors_bar(constructors), use_container_width=True)

    # ── Race tab ───────────────────────────────────────────────────────────
    with tab_race:
        # Use a unique key combining year+gp so spinner re-fires on change
        cache_key = f"{year}_{gp}"
        with st.spinner(f"Loading {gp} {year}…"):
            session = load_session(year, gp, "R")

        if session is None:
            st.warning("Race data not available. Try a different race.")
            return

        _render_position_trace(session)
        _render_results_table(session)


def _render_standings_table(df: pd.DataFrame):
    display_cols = [c for c in ["Pos", "Driver", "Team", "Points", "Wins"] if c in df.columns]
    st.dataframe(
        df[display_cols].set_index("Pos"),
        use_container_width=True,
        hide_index=False,
    )


def _constructors_bar(constructors: list) -> go.Figure:
    names = [c["Constructor"]["name"] for c in constructors]
    points = [int(c["points"]) for c in constructors]
    colors = [get_team_color(n) for n in names]

    fig = go.Figure(go.Bar(
        x=points,
        y=names,
        orientation="h",
        marker_color=colors,
        text=points,
        textposition="outside",
        textfont=dict(family="JetBrains Mono", size=10, color="#fff"),
        hovertemplate="<b>%{y}</b><br>Points: %{x}<extra></extra>",
    ))
    fig.update_layout(yaxis=dict(autorange="reversed"), xaxis_title="Points")
    apply_base(fig, "Constructors' Championship", height=380)
    return fig


def _render_position_trace(session):
    try:
        laps = session.laps[["Driver", "LapNumber", "Position"]].dropna(subset=["Position"])
        if laps.empty:
            st.info("Position data not available for this race.")
            return

        # Get team map from all available sources
        team_map = get_team_map(session)

        fig = go.Figure()
        for drv in laps["Driver"].unique():
            drv_laps = laps[laps["Driver"] == drv].sort_values("LapNumber")
            team = team_map.get(drv, "Unknown")
            color = get_team_color(team)
            is_cadillac = "cadillac" in team.lower()

            fig.add_trace(go.Scatter(
                x=drv_laps["LapNumber"],
                y=drv_laps["Position"],
                mode="lines",
                name=drv,
                line=dict(color=color, width=3 if is_cadillac else 1.5),
                opacity=1.0 if is_cadillac else 0.6,
                hovertemplate=f"<b>{drv}</b> ({team})<br>Lap %{{x}}<br>P%{{y}}<extra></extra>",
            ))

        fig.update_layout(
            yaxis=dict(autorange="reversed", dtick=1, title="Position"),
            xaxis_title="Lap",
        )
        apply_base(fig, "Race Position Trace", height=450)
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.warning(f"Position trace unavailable: {e}")


def _render_results_table(session):
    try:
        results = session.results[
            ["FullName", "TeamName", "GridPosition", "Position", "Points", "Status"]
        ].copy()
        results = results.sort_values("Position")
        results.columns = ["Driver", "Team", "Grid", "Finish", "Points", "Status"]

        st.markdown("**RACE RESULT**")
        rows = []
        for _, row in results.iterrows():
            finish = int(row["Finish"]) if pd.notna(row["Finish"]) else None
            grid   = int(row["Grid"])   if pd.notna(row["Grid"])   else None
            pts    = float(row["Points"]) if pd.notna(row["Points"]) else 0

            if finish and grid:
                delta = grid - finish
                change = f"▲{delta}" if delta > 0 else (f"▼{abs(delta)}" if delta < 0 else "—")
            else:
                change = "—"

            rows.append({
                "Pos":    f"P{finish}" if finish else "—",
                "Driver": row["Driver"],
                "Team":   row["Team"],
                "Grid":   f"P{grid}" if grid else "—",
                "Δ Pos":  change,
                "Points": int(pts) if pts > 0 else "",
                "Status": row["Status"],
            })

        df = pd.DataFrame(rows)
        st.dataframe(df.set_index("Pos"), use_container_width=True, hide_index=False)

    except Exception as e:
        st.warning(f"Results table unavailable: {e}")
