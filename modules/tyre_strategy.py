"""
pages/tyre_strategy.py — Horizontal stint timeline coloured by compound
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from utils.data import (
    load_session, get_race_name_list, COMPOUND_COLORS,
    get_team_color, AVAILABLE_YEARS, get_pit_stops
)
from utils.plots import apply_base, empty_fig


def render():
    st.markdown("""
    <div style="margin-bottom:1.5rem;">
        <div style="font-family:'Exo 2',sans-serif;font-weight:900;font-size:2rem;letter-spacing:-0.03em;">
            Tyre Strategy
        </div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#666;text-transform:uppercase;letter-spacing:0.1em;">
            Stint timeline · Compound sequence · Pit windows
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns([1, 2])
    with c1:
        year = st.selectbox("Season", AVAILABLE_YEARS, key="ts_year")
    with c2:
        races = get_race_name_list(year)
        if not races:
            st.warning("Could not load schedule.")
            return
        gp = st.selectbox("Grand Prix", races, index=min(7, len(races)-1), key="ts_gp")

    with st.spinner(f"Loading tyre data for {gp} {year}…"):
        session = load_session(year, gp, "R")

    if session is None:
        st.warning("Race data not available.")
        return

    _render_strategy_timeline(session)
    _render_compound_summary(session)
    _render_pit_stops_table(session)


def _render_strategy_timeline(session):
    """Horizontal stacked bar chart per driver showing compound stints."""
    try:
        laps = session.laps[["Driver", "LapNumber", "Compound", "Stint", "Team", "PitInTime"]].copy()
        laps["Compound"] = laps["Compound"].fillna("UNKNOWN").str.upper()

        # Build stint summary
        stints = (
            laps.groupby(["Driver", "Stint", "Compound", "Team"])
            .agg(start_lap=("LapNumber", "min"), end_lap=("LapNumber", "max"))
            .reset_index()
        )
        stints["stint_len"] = stints["end_lap"] - stints["start_lap"] + 1

        # Sort drivers: winners first, Cadillac highlighted
        try:
            results = session.results[["Abbreviation", "Position"]].dropna()
            results["Position"] = pd.to_numeric(results["Position"], errors="coerce")
            driver_order = results.sort_values("Position")["Abbreviation"].tolist()
        except Exception:
            driver_order = stints["Driver"].unique().tolist()

        # Reverse for Plotly (bottom = P1)
        driver_order_rev = list(reversed(driver_order))

        fig = go.Figure()

        # Add invisible base bar for positioning
        for drv in driver_order_rev:
            drv_stints = stints[stints["Driver"] == drv].sort_values("start_lap")
            if drv_stints.empty:
                continue

            for _, stint in drv_stints.iterrows():
                compound = stint["Compound"]
                color = COMPOUND_COLORS.get(compound, "#888888")
                team = stint["Team"]
                t_color = get_team_color(str(team))

                # Make Cadillac bars slightly taller
                is_cadillac = "cadillac" in str(team).lower()

                fig.add_trace(go.Bar(
                    y=[drv],
                    x=[stint["stint_len"]],
                    base=stint["start_lap"] - 1,
                    orientation="h",
                    name=compound,
                    legendgroup=compound,
                    showlegend=(drv == driver_order_rev[0]),
                    marker=dict(
                        color=color,
                        opacity=0.9 if is_cadillac else 0.7,
                        line=dict(color=t_color if is_cadillac else "#0A0A0A", width=2 if is_cadillac else 0.5),
                    ),
                    hovertemplate=(
                        f"<b>{drv}</b><br>"
                        f"Compound: {compound}<br>"
                        f"Laps {int(stint['start_lap'])}–{int(stint['end_lap'])} "
                        f"({int(stint['stint_len'])} laps)<extra></extra>"
                    ),
                ))

        fig.update_layout(
            barmode="overlay",
            xaxis_title="Lap Number",
            yaxis=dict(
                title="Driver",
                categoryorder="array",
                categoryarray=driver_order_rev,
            ),
            legend=dict(
                title="Compound",
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="left",
                x=0,
            ),
        )
        apply_base(fig, "Race Tyre Strategy", height=max(400, len(driver_order_rev) * 28 + 100))
        st.plotly_chart(fig, use_container_width=True)

        # Compound legend badges
        st.markdown("**Compound key:**  " + "  ".join([
            f'<span style="background:{v};color:{"#000" if k in ["MEDIUM","HARD","INTERMEDIATE"] else "#fff"};'
            f'padding:2px 8px;border-radius:2px;font-family:JetBrains Mono,monospace;font-size:0.7rem;">{k}</span>'
            for k, v in COMPOUND_COLORS.items() if k not in ["UNKNOWN", "TEST_UNKNOWN"]
        ]), unsafe_allow_html=True)

    except Exception as e:
        st.warning(f"Strategy timeline unavailable: {e}")


def _render_compound_summary(session):
    """Summary: how many drivers used each compound."""
    try:
        laps = session.laps[["Driver", "Compound"]].dropna()
        laps["Compound"] = laps["Compound"].str.upper()

        summary = (
            laps.groupby("Compound")["Driver"]
            .nunique()
            .reset_index()
            .rename(columns={"Driver": "Drivers"})
            .sort_values("Drivers", ascending=False)
        )

        st.markdown('<hr style="border:none;border-top:1px solid #222;margin:1.5rem 0;">', unsafe_allow_html=True)
        st.markdown("**COMPOUND USAGE**")

        cols = st.columns(len(summary))
        for i, (_, row) in enumerate(summary.iterrows()):
            compound = row["Compound"]
            color = COMPOUND_COLORS.get(compound, "#888")
            text_color = "#000" if compound in ["MEDIUM", "HARD", "INTERMEDIATE"] else "#fff"
            with cols[i]:
                st.markdown(f"""
                <div class="metric-card" style="border-left-color:{color};text-align:center;">
                    <div style="background:{color};color:{text_color};padding:4px 8px;border-radius:2px;
                         font-family:'JetBrains Mono',monospace;font-size:0.7rem;font-weight:600;
                         display:inline-block;margin-bottom:0.5rem;">{compound}</div>
                    <div class="value">{int(row['Drivers'])}</div>
                    <div class="delta">drivers used</div>
                </div>
                """, unsafe_allow_html=True)
    except Exception:
        pass


def _render_pit_stops_table(session):
    """Table of all pit stops with stationary time."""
    try:
        pit_df = get_pit_stops(session)

        if pit_df.empty:
            st.info("No pit stop data available for this session.")
            return

        pit_df["StopTime"] = pit_df["StopTime"].round(2)
        pit_df = pit_df.sort_values("StopTime")
        pit_table = pit_df.copy()
        # Normalise column names for display
        if "Compound" not in pit_table.columns:
            pit_table["Compound"] = "UNKNOWN"
        pit_table = pit_table.rename(columns={"StopTime": "Stop Time (s)", "LapNumber": "Lap"})

        st.markdown('<hr style="border:none;border-top:1px solid #222;margin:1.5rem 0;">', unsafe_allow_html=True)
        st.markdown("**PIT STOP TIMES** (sorted fastest first)")

        rows_html = []
        for _, row in pit_table.head(25).iterrows():
            compound = str(row.get("New Compound", "")).upper()
            comp_color = COMPOUND_COLORS.get(compound, "#888")
            team_color = get_team_color(str(row["Team"]))
            stop_t = row["Stop Time (s)"]

            # Colour code: green <2.5s, yellow 2.5-3.5s, red >3.5s
            if stop_t < 2.5:
                t_color = "#39FF14"
            elif stop_t < 3.5:
                t_color = "#FFD700"
            else:
                t_color = "#E8002D"

            rows_html.append(f"""
            <div style="display:flex;align-items:center;padding:5px 0;border-bottom:1px solid #1a1a1a;font-size:0.82rem;">
                <span style="display:inline-block;width:3px;height:14px;background:{team_color};margin-right:8px;border-radius:1px;"></span>
                <span style="width:50px;font-family:'JetBrains Mono',monospace;">{row['Driver']}</span>
                <span style="flex:1;color:#888;font-size:0.75rem;">{row['Team']}</span>
                <span style="width:50px;text-align:center;font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#888;">L{int(row['Lap'])}</span>
                <span style="width:80px;text-align:center;">
                    <span style="background:{comp_color};color:{"#000" if compound in ["MEDIUM","HARD","INTERMEDIATE"] else "#fff"};
                    padding:1px 6px;border-radius:2px;font-size:0.65rem;">{compound}</span>
                </span>
                <span style="width:70px;text-align:right;font-family:'JetBrains Mono',monospace;font-weight:700;color:{t_color};">{stop_t:.2f}s</span>
            </div>
            """)

        st.markdown(
            '<div style="background:#111;border:1px solid #222;border-radius:4px;padding:0.5rem 1rem;">'
            + "".join(rows_html)
            + "</div>",
            unsafe_allow_html=True,
        )
    except Exception as e:
        st.warning(f"Pit stop table unavailable: {e}")
