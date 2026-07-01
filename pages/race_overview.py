"""
pages/race_overview.py — Championship standings + race position trace
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from utils.data import (
    get_event_schedule, load_session, get_clean_laps,
    get_standings, TEAM_COLORS, AVAILABLE_YEARS, get_race_name_list,
    get_team_color
)
from utils.plots import apply_base, empty_fig


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
            st.warning("Could not load race schedule. Check internet connection.")
            return
        gp = st.selectbox("Grand Prix", races, index=min(7, len(races)-1), key="ov_gp")

    # ── Standings ──────────────────────────────────────────────────────────
    st.markdown('<hr style="border:none;border-top:1px solid #222;margin:1rem 0;">', unsafe_allow_html=True)

    with st.spinner("Loading championship standings…"):
        drivers, constructors = get_standings(year)

    tab_standings, tab_race = st.tabs(["CHAMPIONSHIP STANDINGS", "RACE POSITION TRACE"])

    with tab_standings:
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
                    df = pd.DataFrame(rows)
                    _render_standings_table(df, "Team")

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
                    df = pd.DataFrame(rows)
                    _render_standings_table(df, "Team")

            # Bar chart constructors
            if constructors:
                fig = _constructors_bar(constructors)
                st.plotly_chart(fig, use_container_width=True)

    with tab_race:
        with st.spinner(f"Loading {gp} {year} race data…"):
            session = load_session(year, gp, "R")

        if session is None:
            st.warning("Race data not available. Try a different race.")
            return

        _render_position_trace(session)
        _render_results_table(session)


def _render_standings_table(df: pd.DataFrame, team_col: str):
    """Render a styled standings table."""
    styled_rows = []
    for _, row in df.iterrows():
        team_color = get_team_color(str(row.get(team_col, "")))
        pos = row["Pos"]
        medal = "🥇" if pos == "1" else ("🥈" if pos == "2" else ("🥉" if pos == "3" else f"P{pos}"))

        if team_col in row:
            team_html = f'<span style="display:inline-block;width:4px;height:12px;background:{team_color};margin-right:6px;border-radius:1px;vertical-align:middle;"></span>{row[team_col]}'
        else:
            team_html = ""

        row_html = f"""
        <div style="display:flex;align-items:center;padding:6px 0;border-bottom:1px solid #1a1a1a;font-size:0.85rem;">
            <span style="width:40px;font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#666;">{medal}</span>
            <span style="flex:1;">{row.get('Driver', row.get('Team',''))}</span>
        """
        if "Team" in row and team_col != "Team":
            row_html += f'<span style="flex:1;font-size:0.75rem;color:#888;">{team_html}</span>'
        row_html += f"""
            <span style="width:60px;text-align:right;font-family:'JetBrains Mono',monospace;font-weight:600;color:#E8002D;">{row['Points']}</span>
        </div>
        """
        styled_rows.append(row_html)

    st.markdown(
        '<div style="background:#111;border:1px solid #222;border-radius:4px;padding:0.5rem 1rem;">'
        + "".join(styled_rows)
        + "</div>",
        unsafe_allow_html=True,
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
    fig.update_layout(
        yaxis=dict(autorange="reversed"),
        xaxis_title="Points",
    )
    apply_base(fig, "Constructors' Championship", height=380)
    return fig


def _render_position_trace(session):
    """Lap-by-lap position chart."""
    try:
        laps = session.laps[["Driver", "LapNumber", "Position", "Team"]].dropna(subset=["Position"])
        if laps.empty:
            st.info("Position data not available for this race.")
            return

        fig = go.Figure()
        drivers = laps["Driver"].unique()

        for drv in drivers:
            drv_laps = laps[laps["Driver"] == drv].sort_values("LapNumber")
            team = drv_laps["Team"].iloc[0] if "Team" in drv_laps.columns else "Unknown"
            color = get_team_color(str(team))

            # Highlight Cadillac drivers
            width = 3 if team == "Cadillac" else 1.5
            opacity = 1.0 if team == "Cadillac" else 0.6

            fig.add_trace(go.Scatter(
                x=drv_laps["LapNumber"],
                y=drv_laps["Position"],
                mode="lines",
                name=drv,
                line=dict(color=color, width=width),
                opacity=opacity,
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
    """Race results summary table."""
    try:
        results = session.results[["FullName", "TeamName", "GridPosition", "Position", "Points", "Status"]].copy()
        results = results.sort_values("Position")
        results.columns = ["Driver", "Team", "Grid", "Finish", "Points", "Status"]

        st.markdown("**RACE RESULT**")
        rows_html = []
        for _, row in results.iterrows():
            color = get_team_color(str(row["Team"]))
            finish = int(row["Finish"]) if pd.notna(row["Finish"]) else "—"
            grid = int(row["Grid"]) if pd.notna(row["Grid"]) else "—"
            change = ""
            if isinstance(finish, int) and isinstance(grid, int):
                delta = grid - finish
                if delta > 0:
                    change = f'<span style="color:#39FF14;">▲{delta}</span>'
                elif delta < 0:
                    change = f'<span style="color:#E8002D;">▼{abs(delta)}</span>'
                else:
                    change = '<span style="color:#666;">—</span>'

            pts = int(row["Points"]) if pd.notna(row["Points"]) and float(row["Points"]) > 0 else ""
            pts_html = f'<span style="color:#E8002D;font-weight:700;">{pts}</span>' if pts else ""

            rows_html.append(f"""
            <div style="display:flex;align-items:center;padding:5px 0;border-bottom:1px solid #1a1a1a;font-size:0.82rem;">
                <span style="width:32px;font-family:'JetBrains Mono',monospace;color:#666;font-size:0.75rem;">P{finish}</span>
                <span style="display:inline-block;width:3px;height:14px;background:{color};margin-right:8px;border-radius:1px;"></span>
                <span style="flex:1;">{row['Driver']}</span>
                <span style="width:140px;color:#888;font-size:0.75rem;">{row['Team']}</span>
                <span style="width:50px;text-align:center;">{change}</span>
                <span style="width:40px;text-align:right;">{pts_html}</span>
            </div>
            """)

        st.markdown(
            '<div style="background:#111;border:1px solid #222;border-radius:4px;padding:0.5rem 1rem;">'
            + "".join(rows_html)
            + "</div>",
            unsafe_allow_html=True,
        )
    except Exception as e:
        st.warning(f"Results table unavailable: {e}")
