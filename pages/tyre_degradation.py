"""
pages/tyre_degradation.py — Deg curves, slope estimation, fuel-corrected pace
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from utils.data import (
    load_session, get_race_name_list, COMPOUND_COLORS,
    get_team_color, AVAILABLE_YEARS, get_clean_laps, fuel_correct
)
from utils.plots import apply_base, empty_fig


def render():
    st.markdown("""
    <div style="margin-bottom:1.5rem;">
        <div style="font-family:'Exo 2',sans-serif;font-weight:900;font-size:2rem;letter-spacing:-0.03em;">
            Tyre Degradation
        </div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#666;text-transform:uppercase;letter-spacing:0.1em;">
            Degradation slope · Fuel-corrected pace · Compound comparison
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        year = st.selectbox("Season", AVAILABLE_YEARS, key="deg_year")
    with c2:
        races = get_race_name_list(year)
        if not races:
            st.warning("Could not load schedule.")
            return
        gp = st.selectbox("Grand Prix", races, index=min(7, len(races)-1), key="deg_gp")
    with c3:
        fuel_corr = st.checkbox("Apply fuel correction", value=True,
                                help="Removes ~0.057s/lap fuel-mass effect from lap times")

    with st.spinner(f"Loading {gp} {year}…"):
        session = load_session(year, gp, "R")

    if session is None:
        st.warning("Race data not available.")
        return

    laps = get_clean_laps(session)
    if laps.empty:
        st.warning("No clean laps found.")
        return

    total_laps = int(laps["LapNumber"].max())
    if fuel_corr:
        laps = fuel_correct(laps, total_laps)
        pace_col = "LapTimeCorr"
        pace_label = "Fuel-Corrected Lap Time (s)"
    else:
        pace_col = "LapTimeSec"
        pace_label = "Lap Time (s)"

    _render_deg_curves(laps, pace_col, pace_label)
    _render_deg_by_driver(laps, pace_col, pace_label, session)
    _render_pace_distribution(laps, pace_col, session)


def _render_deg_curves(laps: pd.DataFrame, pace_col: str, pace_label: str):
    """Median lap time vs tyre age per compound with linear regression."""
    try:
        laps = laps.copy()
        laps["Compound"] = laps["Compound"].fillna("UNKNOWN").str.upper()

        fig = go.Figure()
        slope_info = []

        for compound in ["SOFT", "MEDIUM", "HARD"]:
            cdf = laps[laps["Compound"] == compound].copy()
            if len(cdf) < 5:
                continue

            # Median per tyre age
            med = cdf.groupby("TyreLife")[pace_col].median().reset_index()
            med = med[med["TyreLife"].between(1, 50)]
            if len(med) < 3:
                continue

            color = COMPOUND_COLORS[compound]
            text_color = "#000" if compound in ["MEDIUM", "HARD"] else "#fff"

            fig.add_trace(go.Scatter(
                x=med["TyreLife"],
                y=med[pace_col],
                mode="markers+lines",
                name=compound,
                line=dict(color=color, width=2),
                marker=dict(color=color, size=5),
                hovertemplate=f"<b>{compound}</b><br>Tyre age: %{{x}} laps<br>Median: %{{y:.3f}}s<extra></extra>",
            ))

            # Linear regression for slope
            if len(med) >= 4:
                x = med["TyreLife"].values
                y = med[pace_col].values
                coeffs = np.polyfit(x, y, 1)
                slope = coeffs[0]
                slope_info.append({"compound": compound, "slope": slope, "color": color, "text_color": text_color})

                # Add trend line
                y_trend = np.polyval(coeffs, x)
                fig.add_trace(go.Scatter(
                    x=x, y=y_trend,
                    mode="lines",
                    name=f"{compound} trend",
                    line=dict(color=color, width=1.5, dash="dot"),
                    showlegend=False,
                    hoverinfo="skip",
                ))

        fig.update_layout(yaxis_title=pace_label, xaxis_title="Tyre Age (laps)")
        apply_base(fig, "Tyre Degradation Curves", height=400)
        st.plotly_chart(fig, use_container_width=True)

        # Degradation slope cards
        if slope_info:
            st.markdown("**DEGRADATION RATE** (s/lap — positive = getting slower)")
            cols = st.columns(len(slope_info))
            for i, info in enumerate(slope_info):
                with cols[i]:
                    slope_val = info["slope"]
                    sign = "+" if slope_val > 0 else ""
                    severity = "Low" if abs(slope_val) < 0.05 else ("Medium" if abs(slope_val) < 0.12 else "High")
                    sev_color = "#39FF14" if severity == "Low" else ("#FFD700" if severity == "Medium" else "#E8002D")
                    st.markdown(f"""
                    <div class="metric-card" style="border-left-color:{info['color']};">
                        <div class="label">{info['compound']}</div>
                        <div class="value" style="font-family:'JetBrains Mono',monospace;">{sign}{slope_val:.4f}s</div>
                        <div class="delta" style="color:{sev_color};">{severity} degradation</div>
                    </div>
                    """, unsafe_allow_html=True)

    except Exception as e:
        st.warning(f"Degradation curves unavailable: {e}")


def _render_deg_by_driver(laps: pd.DataFrame, pace_col: str, pace_label: str, session):
    """Individual driver pace evolution over the race."""
    try:
        st.markdown('<hr style="border:none;border-top:1px solid #222;margin:1.5rem 0;">', unsafe_allow_html=True)
        st.markdown("**DRIVER PACE EVOLUTION**")

        # Driver multiselect — default to top 6 finishers or Cadillac drivers
        all_drivers = sorted(laps["Driver"].unique())
        cadillac_drivers = [d for d in all_drivers if d in ["PER", "BOT"]]
        default_drivers = cadillac_drivers + [d for d in all_drivers if d not in cadillac_drivers][:4]

        selected = st.multiselect(
            "Select drivers",
            all_drivers,
            default=default_drivers[:6],
            key="deg_drivers",
        )
        if not selected:
            return

        fig = go.Figure()

        for drv in selected:
            drv_laps = laps[laps["Driver"] == drv].sort_values("LapNumber")
            if drv_laps.empty:
                continue

            try:
                team = session.laps[session.laps["Driver"] == drv]["Team"].iloc[0]
            except Exception:
                team = "Unknown"

            color = get_team_color(str(team))
            is_cadillac = "cadillac" in str(team).lower()

            # Group by stint for gap between stints
            for stint_num in drv_laps["Stint"].unique():
                stint_laps = drv_laps[drv_laps["Stint"] == stint_num]
                compound = stint_laps["Compound"].iloc[0] if "Compound" in stint_laps else "UNKNOWN"
                comp_color = COMPOUND_COLORS.get(str(compound).upper(), color)

                fig.add_trace(go.Scatter(
                    x=stint_laps["LapNumber"],
                    y=stint_laps[pace_col],
                    mode="lines+markers",
                    name=f"{drv} S{int(stint_num)}",
                    line=dict(color=comp_color, width=2.5 if is_cadillac else 1.5),
                    marker=dict(size=4, color=comp_color),
                    legendgroup=drv,
                    showlegend=bool(stint_num == drv_laps["Stint"].min()),
                    hovertemplate=f"<b>{drv}</b> (Stint {int(stint_num)})<br>Lap %{{x}}<br>{pace_label}: %{{y:.3f}}s<extra></extra>",
                ))

        fig.update_layout(yaxis_title=pace_label, xaxis_title="Lap Number")
        apply_base(fig, "Driver Pace Evolution by Stint", height=420)
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.warning(f"Driver pace evolution unavailable: {e}")


def _render_pace_distribution(laps: pd.DataFrame, pace_col: str, session):
    """Box plot of pace distribution per team."""
    try:
        st.markdown('<hr style="border:none;border-top:1px solid #222;margin:1.5rem 0;">', unsafe_allow_html=True)
        st.markdown("**PACE DISTRIBUTION BY TEAM**")

        team_laps = laps.copy()
        # Merge team info — get_clean_laps does not preserve Team column
        try:
            team_info = (
                session.laps[["Driver", "Team"]]
                .dropna(subset=["Team"])
                .drop_duplicates(subset=["Driver"])
            )
            team_laps = team_laps.merge(team_info, on="Driver", how="left")
        except Exception as e:
            st.info(f"Team data not available: {e}")
            return

        team_laps = team_laps.dropna(subset=["Team", pace_col])

        # Sort teams by median pace
        team_medians = team_laps.groupby("Team")[pace_col].median().sort_values()
        sorted_teams = team_medians.index.tolist()

        fig = go.Figure()
        for team in sorted_teams:
            tdf = team_laps[team_laps["Team"] == team]
            color = get_team_color(team)
            is_cadillac = "cadillac" in team.lower()

            fig.add_trace(go.Box(
                y=tdf[pace_col],
                name=team,
                marker_color=color,
                line=dict(color=color, width=2.5 if is_cadillac else 1.5),
                fillcolor=color + "33",
                boxmean=True,
                hovertemplate=f"<b>{team}</b><br>%{{y:.3f}}s<extra></extra>",
            ))

        fig.update_layout(
            yaxis_title="Lap Time (s)",
            xaxis_title="",
            showlegend=False,
        )
        apply_base(fig, "Pace Distribution by Team (clean laps only)", height=420)
        st.plotly_chart(fig, use_container_width=True)

        st.markdown(
            '<div style="font-family:JetBrains Mono,monospace;font-size:0.65rem;color:#555;">'
            'In/out laps, SC laps, and laps >110% of median excluded. Box = IQR, line = median, dot = mean.'
            '</div>',
            unsafe_allow_html=True
        )

    except Exception as e:
        st.warning(f"Pace distribution unavailable: {e}")
