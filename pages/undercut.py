"""
pages/undercut.py — Interactive undercut/overcut calculator with race data context
"""

import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd
from utils.data import (
    load_session, get_race_name_list, get_clean_laps,
    COMPOUND_COLORS, AVAILABLE_YEARS, get_team_color
)
from utils.plots import apply_base


def render():
    st.markdown("""
    <div style="margin-bottom:1.5rem;">
        <div style="font-family:'Exo 2',sans-serif;font-weight:900;font-size:2rem;letter-spacing:-0.03em;">
            Undercut Analyser
        </div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#666;text-transform:uppercase;letter-spacing:0.1em;">
            Undercut · Overcut · Pit window calculator
        </div>
    </div>
    """, unsafe_allow_html=True)

    # ── Theory explainer ──────────────────────────────────────────────────
    with st.expander("How does the undercut/overcut work?", expanded=False):
        st.markdown("""
        **Undercut:** You pit *before* your rival. Your fresh tyres generate more grip → you post a fast out-lap.
        By the time your rival pits, you've closed the gap or built enough time to emerge ahead of them after their stop.

        **Undercut works when:** `fresh_tyre_advantage × laps_ahead_in_pit > gap_to_rival + pit_loss_delta`

        **Overcut:** You stay out *longer* while your rival pits. Their new-tyre out-lap may be slow (cold tyres, traffic).
        You bank the clean-air advantage, then pit and re-emerge ahead.

        **Overcut works when:** track position advantage + pace on old tyres > rival's fresh-tyre pace gain.

        The **pit-lane delta** (total time lost vs staying out) is typically 20–25 seconds at most circuits.
        A smaller delta makes undercuts easier to execute.
        """)

    # ── Calculator ────────────────────────────────────────────────────────
    st.markdown("### INTERACTIVE CALCULATOR")
    st.markdown('<div style="font-family:JetBrains Mono,monospace;font-size:0.7rem;color:#555;margin-bottom:1rem;">Adjust parameters to model undercut/overcut scenarios.</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**YOUR CAR**")
        gap_to_rival = st.slider("Gap to car ahead (s)", 0.5, 25.0, 3.0, 0.1,
                                  help="How far behind the rival you are when considering pitting")
        your_tyre_age = st.slider("Your current tyre age (laps)", 1, 45, 18,
                                   help="Laps on your current set")
        fresh_tyre_delta = st.slider("Fresh tyre gain vs worn (s/lap)", 0.0, 1.5, 0.45, 0.05,
                                      help="Estimated performance gain per lap on new tyres vs current worn tyres")
        your_deg_rate = st.slider("Your degradation rate (s/lap)", 0.02, 0.25, 0.07, 0.01,
                                   help="How much pace you're losing per lap on worn tyres")

    with col2:
        st.markdown("**RIVAL'S CAR**")
        rival_tyre_age = st.slider("Rival's tyre age (laps)", 1, 45, 15,
                                    help="Laps on rival's current set")
        rival_deg_rate = st.slider("Rival's degradation rate (s/lap)", 0.02, 0.25, 0.06, 0.01,
                                    help="Rival's pace loss per lap")
        pit_loss = st.slider("Pit-lane delta (s)", 15.0, 35.0, 22.0, 0.5,
                              help="Total time lost vs staying out (entry + stationary + out-lap compromise)")
        out_lap_penalty = st.slider("Out-lap penalty (s)", 0.5, 5.0, 2.5, 0.1,
                                     help="Additional time lost on the out-lap for cold tyres")

    # ── Undercut maths ────────────────────────────────────────────────────
    laps_ahead = st.slider("Laps of undercut to model", 1, 8, 3,
                            help="How many laps of fresh-tyre advantage to accumulate before rival pits")

    # --- Core undercut calculation ---
    # After YOU pit and come out, over `laps_ahead` laps before RIVAL pits:
    # You gain: fresh_tyre_delta × laps_ahead  (from fresher tyres)
    # Rival loses: rival_deg_rate × laps_ahead  (from wearing tyres)
    # You lose: pit_loss (once, for pitting)
    # You lose: out_lap_penalty (once, cold tyre out-lap)
    # Net: if total gain > gap_to_rival → undercut works

    time_gained_fresh = fresh_tyre_delta * laps_ahead
    time_gained_rival_deg = rival_deg_rate * laps_ahead
    total_gain = time_gained_fresh + time_gained_rival_deg
    total_cost = pit_loss + out_lap_penalty
    net_delta = total_gain - total_cost
    undercut_gap_closed = gap_to_rival + net_delta  # positive = ahead

    undercut_works = net_delta > gap_to_rival * -1 and net_delta > 0 and total_gain > (pit_loss + out_lap_penalty)
    # Simpler: if after pitting and fresh tyre advantage, you emerge ahead
    undercut_works = (gap_to_rival - net_delta) < 0  # emerged ahead

    # Overcut: stay out, rival pits, their out-lap is slow
    rival_out_lap_slow = out_lap_penalty * 1.3  # rivals cold tyre out-lap
    overcut_gap_closed = rival_out_lap_slow + (rival_deg_rate - your_deg_rate) * laps_ahead
    overcut_works = overcut_gap_closed > gap_to_rival and your_tyre_age <= rival_tyre_age + 5

    # ── Results ───────────────────────────────────────────────────────────
    st.markdown('<hr style="border:none;border-top:1px solid #222;margin:1.5rem 0;">', unsafe_allow_html=True)
    st.markdown("### STRATEGY VERDICT")

    r1, r2, r3 = st.columns(3)
    with r1:
        color = "#39FF14" if undercut_works else "#E8002D"
        label = "WORKS ✓" if undercut_works else "WON'T WORK ✗"
        emerge = gap_to_rival - net_delta
        emerge_str = f"Emerge {'ahead' if emerge < 0 else 'behind'} by {abs(emerge):.1f}s"
        st.markdown(f"""
        <div class="metric-card" style="border-left-color:{color};">
            <div class="label">UNDERCUT</div>
            <div class="value" style="color:{color};font-size:1.2rem;">{label}</div>
            <div class="delta">{emerge_str}</div>
            <div class="delta">Net delta: {net_delta:+.2f}s over {laps_ahead} laps</div>
        </div>
        """, unsafe_allow_html=True)

    with r2:
        color2 = "#39FF14" if overcut_works else "#E8002D"
        label2 = "WORKS ✓" if overcut_works else "WON'T WORK ✗"
        st.markdown(f"""
        <div class="metric-card" style="border-left-color:{color2};">
            <div class="label">OVERCUT</div>
            <div class="value" style="color:{color2};font-size:1.2rem;">{label2}</div>
            <div class="delta">Rival out-lap: +{rival_out_lap_slow:.1f}s</div>
            <div class="delta">Gap closed: {overcut_gap_closed:.1f}s</div>
        </div>
        """, unsafe_allow_html=True)

    with r3:
        pit_decision = "UNDERCUT" if undercut_works else ("OVERCUT" if overcut_works else "STAY OUT")
        rec_color = "#FFD700"
        st.markdown(f"""
        <div class="metric-card" style="border-left-color:{rec_color};">
            <div class="label">RECOMMENDATION</div>
            <div class="value" style="color:{rec_color};font-size:1.1rem;">{pit_decision}</div>
            <div class="delta">Based on current parameters</div>
            <div class="delta">Pit loss: {pit_loss:.1f}s · Fresh gain: {total_gain:.2f}s</div>
        </div>
        """, unsafe_allow_html=True)

    # ── Gap evolution chart ───────────────────────────────────────────────
    _render_gap_evolution(gap_to_rival, net_delta, pit_loss, out_lap_penalty,
                           fresh_tyre_delta, rival_deg_rate, laps_ahead)

    # ── Real race context ─────────────────────────────────────────────────
    st.markdown('<hr style="border:none;border-top:1px solid #222;margin:1.5rem 0;">', unsafe_allow_html=True)
    st.markdown("### CALIBRATE FROM REAL RACE DATA")
    st.markdown('<div style="font-family:JetBrains Mono,monospace;font-size:0.7rem;color:#555;margin-bottom:1rem;">Load a race to see actual pit deltas and use them in the calculator.</div>', unsafe_allow_html=True)

    c1, c2 = st.columns([1, 2])
    with c1:
        year = st.selectbox("Season", AVAILABLE_YEARS, key="uc_year")
    with c2:
        races = get_race_name_list(year)
        if not races:
            return
        gp = st.selectbox("Grand Prix", races, index=min(7, len(races)-1), key="uc_gp")

    if st.button("Load Pit Data", key="uc_load"):
        with st.spinner("Loading…"):
            session = load_session(year, gp, "R")
        if session:
            _show_real_pit_deltas(session)


def _render_gap_evolution(gap, net_delta, pit_loss, out_lap_penalty,
                            fresh_gain, rival_deg, laps_ahead):
    """Visualise the gap trajectory through the undercut sequence."""
    laps = list(range(0, laps_ahead + 6))
    # Phase 1: before pit (gap stays roughly constant, maybe slight change)
    # Phase 2: you pit → gap explodes by pit_loss + out_lap_penalty
    # Phase 3: you claw back fresh_gain per lap, rival degrades

    gaps = []
    for lap in laps:
        if lap == 0:
            gaps.append(gap)
        elif lap < 2:  # you haven't pitted yet — tiny degradation diff
            gaps.append(gap + (rival_deg - 0.04) * lap)
        elif lap == 2:  # you pit
            gaps.append(gap + pit_loss + out_lap_penalty)
        else:
            # Claw back fresh_gain per lap + rival deg per lap
            gaps.append(gap + pit_loss + out_lap_penalty - (fresh_gain + rival_deg) * (lap - 2))

    ahead_lap = next((i for i, g in enumerate(gaps) if g < 0), None)

    fig = go.Figure()

    # Shade regions
    fig.add_hrect(y0=0, y1=max(gaps) * 1.1, fillcolor="#E8002D", opacity=0.05, line_width=0)
    fig.add_hline(y=0, line=dict(color="#E8002D", width=1.5, dash="dash"),
                  annotation_text="Track position boundary", annotation_position="right")

    colors = ["#39FF14" if g < 0 else "#E8002D" for g in gaps]
    phases = ["Before pit", "Before pit", "You pit"] + ["Post-pit recovery"] * (len(laps) - 3)

    fig.add_trace(go.Scatter(
        x=laps,
        y=gaps,
        mode="lines+markers",
        line=dict(color="#FFD700", width=2.5),
        marker=dict(
            color=colors,
            size=8,
            line=dict(color="#0A0A0A", width=1),
        ),
        hovertemplate="Lap offset: %{x}<br>Gap to rival: %{y:.2f}s<extra></extra>",
        name="Your gap to rival",
    ))

    if ahead_lap is not None:
        fig.add_annotation(
            x=ahead_lap, y=0,
            text=f"Emerged ahead at lap +{ahead_lap}",
            showarrow=True, arrowhead=2, arrowcolor="#39FF14",
            font=dict(color="#39FF14", family="JetBrains Mono", size=10),
            bgcolor="#0A0A0A",
        )

    fig.add_vline(x=2, line=dict(color="#888", width=1, dash="dot"),
                  annotation_text="Pit stop", annotation_position="top")

    fig.update_layout(
        xaxis_title="Lap offset from pit decision",
        yaxis_title="Gap to rival (s)  [negative = you're ahead]",
    )
    apply_base(fig, "Undercut Gap Trajectory", height=350)
    st.plotly_chart(fig, use_container_width=True)


def _show_real_pit_deltas(session):
    """Show actual pit stop stationary times from race."""
    try:
        laps = session.laps.copy()
        pit_laps = laps[laps["PitInTime"].notna()].copy()

        pit_laps["StopTime"] = (
            laps["PitOutTime"] - laps["PitInTime"]
        ).dt.total_seconds()

        valid = pit_laps[pit_laps["StopTime"].between(1.5, 30)].copy()
        if valid.empty:
            st.info("No valid pit data found.")
            return

        mean_stop = valid["StopTime"].mean()
        min_stop = valid["StopTime"].min()
        max_stop = valid["StopTime"].max()
        best_drv = valid.loc[valid["StopTime"].idxmin(), "Driver"]

        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"""
            <div class="metric-card">
                <div class="label">Fastest Stop</div>
                <div class="value" style="color:#39FF14;font-family:'JetBrains Mono',monospace;">
                    {min_stop:.2f}s
                </div>
                <div class="delta">{best_drv}</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div class="metric-card">
                <div class="label">Average Stop</div>
                <div class="value" style="font-family:'JetBrains Mono',monospace;">{mean_stop:.2f}s</div>
            </div>
            """, unsafe_allow_html=True)
        with c3:
            st.markdown(f"""
            <div class="metric-card">
                <div class="label">Slowest Stop</div>
                <div class="value" style="color:#E8002D;font-family:'JetBrains Mono',monospace;">{max_stop:.2f}s</div>
            </div>
            """, unsafe_allow_html=True)

        st.info(f"💡 Use {mean_stop:.1f}s as the 'Pit-lane delta' base in the calculator above (add ~2s for entry/exit penalty).")

    except Exception as e:
        st.warning(f"Could not load pit data: {e}")
