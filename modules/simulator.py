"""
pages/simulator.py — Monte Carlo 1-stop vs 2-stop race strategy simulator
"""

import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd
from utils.data import COMPOUND_COLORS, AVAILABLE_YEARS, get_race_name_list, load_session, get_clean_laps
from utils.plots import apply_base


def render():
    st.markdown("""
    <div style="margin-bottom:1.5rem;">
        <div style="font-family:'Exo 2',sans-serif;font-weight:900;font-size:2rem;letter-spacing:-0.03em;">
            Strategy Simulator
        </div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#666;text-transform:uppercase;letter-spacing:0.1em;">
            Monte Carlo · 1-stop vs 2-stop · Safety car sensitivity
        </div>
    </div>
    """, unsafe_allow_html=True)

    with st.expander("How does the Monte Carlo simulator work?", expanded=False):
        st.markdown("""
        Real F1 teams run **~300 million permutations** of each race using Monte Carlo simulation.
        This simplified version runs **10,000 simulated races** per strategy, sampling from
        realistic distributions of tyre degradation, safety car timing, and pit-stop variation.

        **What we model:**
        - Base lap time + per-compound degradation slope (s/lap)
        - Fuel effect: cars get faster as fuel burns off (~0.057s/lap)
        - Safety car probability: random SC deployment compresses the field (free pit stop)
        - Pit stop time: sampled from a normal distribution (mean ± std deviation)
        - Tyre compound delta: time delta between starting a stint on different compounds

        **Output:** Expected total race time ± standard deviation for each strategy,
        probability one beats the other, and optimal stop lap.
        """)

    # ── Parameters ─────────────────────────────────────────────────────────
    st.markdown("### RACE PARAMETERS")

    col1, col2, col3 = st.columns(3)
    with col1:
        total_laps = st.slider("Total race laps", 30, 78, 57, key="sim_laps")
        base_lap_time = st.slider("Base lap time (s)", 70.0, 105.0, 90.0, 0.5, key="sim_base")
        fuel_effect = st.slider("Fuel effect (s/lap)", 0.03, 0.10, 0.057, 0.001, key="sim_fuel",
                                 help="How much faster per lap as fuel burns off")

    with col2:
        soft_deg = st.slider("Soft deg rate (s/lap)", 0.05, 0.35, 0.14, 0.01, key="sim_sdeg")
        medium_deg = st.slider("Medium deg rate (s/lap)", 0.03, 0.20, 0.08, 0.01, key="sim_mdeg")
        hard_deg = st.slider("Hard deg rate (s/lap)", 0.02, 0.15, 0.05, 0.01, key="sim_hdeg")

    with col3:
        pit_loss = st.slider("Pit loss (s)", 15.0, 35.0, 22.0, 0.5, key="sim_pit")
        pit_std = st.slider("Stop time std dev (s)", 0.1, 2.0, 0.4, 0.1, key="sim_pitstd",
                             help="Variability in pit stop execution")
        sc_prob = st.slider("Safety car probability", 0.0, 1.0, 0.35, 0.05, key="sim_sc",
                             help="Probability of at least one safety car per race")

    # Compound deltas (time advantage/disadvantage at start of stint)
    st.markdown("**COMPOUND STEP DELTAS** (time difference at new-tyre phase)")
    cd1, cd2, cd3 = st.columns(3)
    with cd1:
        soft_vs_medium = st.slider("Soft vs Medium (s/lap faster)", 0.1, 0.8, 0.35, 0.05, key="sim_sm")
    with cd2:
        medium_vs_hard = st.slider("Medium vs Hard (s/lap faster)", 0.05, 0.5, 0.20, 0.05, key="sim_mh")
    with cd3:
        n_sims = st.select_slider("Simulations", [1000, 5000, 10000, 20000], value=10000, key="sim_n")

    # ── Strategy definitions ────────────────────────────────────────────────
    st.markdown('<hr style="border:none;border-top:1px solid #222;margin:1.5rem 0;">', unsafe_allow_html=True)
    st.markdown("### DEFINE STRATEGIES")

    strategies = {}

    s_col1, s_col2 = st.columns(2)
    with s_col1:
        st.markdown("**1-STOP STRATEGIES**")
        stop1_lap_1stop = st.slider("Stop lap (1-stop)", 10, total_laps - 10, total_laps // 2, key="sim_1s_lap")
        c1a, c1b = st.columns(2)
        with c1a:
            comp1_s1 = st.selectbox("Starting compound", ["SOFT","MEDIUM","HARD"], index=1, key="sim_c1a")
        with c1b:
            comp2_s1 = st.selectbox("2nd stint compound", ["HARD","MEDIUM","SOFT"], index=0, key="sim_c1b")
        strategies["1-Stop M→H"] = {
            "stops": [(stop1_lap_1stop, comp1_s1, comp2_s1)],
            "start": comp1_s1,
            "color": "#64C4FF",
        }

    with s_col2:
        st.markdown("**2-STOP STRATEGIES**")
        s1_lap = st.slider("First stop lap", 5, total_laps // 2, max(5, total_laps // 4), key="sim_2s1")
        s2_lap = st.slider("Second stop lap", total_laps // 3, total_laps - 5, max(total_laps // 3, (total_laps * 2) // 3), key="sim_2s2")
        c2a, c2b, c2c = st.columns(3)
        with c2a:
            comp2a = st.selectbox("Start", ["SOFT","MEDIUM","HARD"], index=0, key="sim_c2a")
        with c2b:
            comp2b = st.selectbox("Stint 2", ["MEDIUM","HARD","SOFT"], index=1, key="sim_c2b")
        with c2c:
            comp2c = st.selectbox("Stint 3", ["HARD","MEDIUM","SOFT"], index=0, key="sim_c2c")
        strategies["2-Stop S→M→H"] = {
            "stops": [(s1_lap, comp2a, comp2b), (s2_lap, comp2b, comp2c)],
            "start": comp2a,
            "color": "#E8002D",
        }

    if st.button("🎲  Run Monte Carlo Simulation", key="sim_run"):
        deg_rates = {"SOFT": soft_deg, "MEDIUM": medium_deg, "HARD": hard_deg}
        compound_deltas = {
            "SOFT": soft_vs_medium + medium_vs_hard,
            "MEDIUM": medium_vs_hard,
            "HARD": 0.0,
        }

        results = {}
        with st.spinner(f"Running {n_sims:,} race simulations per strategy…"):
            for name, strat in strategies.items():
                times = _run_monte_carlo(
                    n_sims=n_sims,
                    total_laps=total_laps,
                    base_lap_time=base_lap_time,
                    fuel_effect=fuel_effect,
                    stops=strat["stops"],
                    start_compound=strat["start"],
                    deg_rates=deg_rates,
                    compound_deltas=compound_deltas,
                    pit_loss=pit_loss,
                    pit_std=pit_std,
                    sc_prob=sc_prob,
                )
                results[name] = {"times": times, "color": strat["color"]}

        _render_simulation_results(results, strategies, total_laps)


def _run_monte_carlo(
    n_sims, total_laps, base_lap_time, fuel_effect,
    stops, start_compound, deg_rates, compound_deltas,
    pit_loss, pit_std, sc_prob
):
    """
    Vectorised Monte Carlo simulation.
    Returns array of total race times (n_sims,).
    """
    rng = np.random.default_rng(42)

    # Safety car: random lap (or None), saves ~20s if it occurs during pit window
    has_sc = rng.random(n_sims) < sc_prob
    sc_lap = rng.integers(5, total_laps - 5, size=n_sims)  # when SC occurs

    # Pit time variation
    pit_times = rng.normal(pit_loss, pit_std, size=(n_sims, len(stops)))
    pit_times = np.clip(pit_times, pit_loss - 3, pit_loss + 10)

    total_times = np.zeros(n_sims)

    # Build stint plan per simulation
    # Create stint schedule: list of (start_lap, end_lap, compound)
    stint_schedule = []
    current_compound = start_compound
    prev_lap = 1

    for i, (stop_lap, from_comp, to_comp) in enumerate(stops):
        stint_schedule.append((prev_lap, stop_lap, current_compound))
        current_compound = to_comp
        prev_lap = stop_lap + 1
    stint_schedule.append((prev_lap, total_laps, current_compound))

    # Simulate each stint
    for stint_idx, (s_start, s_end, compound) in enumerate(stint_schedule):
        deg_rate = deg_rates.get(compound, 0.08)
        comp_delta = compound_deltas.get(compound, 0.0)

        for lap in range(s_start, s_end + 1):
            tyre_age = lap - s_start + 1
            fuel_save = (total_laps - lap) * fuel_effect

            # Lap time = base + compound_starting_disadvantage + deg_rate*age - fuel_effect
            lap_time = base_lap_time + comp_delta + deg_rate * tyre_age - fuel_save
            # Add small random noise per lap
            lap_time += rng.normal(0, 0.05, n_sims)
            total_times += lap_time

        # Add pit time for this stop (if not last stint)
        if stint_idx < len(stops):
            stop_lap = stops[stint_idx][0]
            actual_pit = pit_times[:, stint_idx]

            # SC benefit: if SC occurs near stop, effective pit loss is ~5s instead
            sc_benefit = has_sc & (np.abs(sc_lap - stop_lap) <= 3)
            actual_pit = np.where(sc_benefit, np.maximum(5.0, actual_pit - 18.0), actual_pit)
            total_times += actual_pit

    return total_times


def _render_simulation_results(results: dict, strategies: dict, total_laps: int):
    """Display Monte Carlo results."""
    st.markdown('<hr style="border:none;border-top:1px solid #222;margin:1.5rem 0;">', unsafe_allow_html=True)
    st.markdown("### SIMULATION RESULTS")

    # Summary metrics
    metric_cols = st.columns(len(results))
    summary_data = {}
    for i, (name, res) in enumerate(results.items()):
        times = res["times"]
        mean_t = np.mean(times)
        std_t = np.std(times)
        summary_data[name] = {"mean": mean_t, "std": std_t, "color": res["color"]}

    # Find winner
    best = min(summary_data, key=lambda x: summary_data[x]["mean"])

    for i, (name, data) in enumerate(summary_data.items()):
        with metric_cols[i]:
            is_best = name == best
            border_color = "#39FF14" if is_best else data["color"]
            mins = int(data["mean"] // 60)
            secs = data["mean"] % 60
            st.markdown(f"""
            <div class="metric-card" style="border-left-color:{border_color};">
                <div class="label">{name}</div>
                <div class="value" style="font-family:'JetBrains Mono',monospace;font-size:1.3rem;">
                    {mins}:{secs:06.3f}
                </div>
                <div class="delta">σ = ±{data['std']:.2f}s</div>
                <div class="delta" style="color:{border_color};">
                    {'⭐ FASTEST' if is_best else f"+{data['mean'] - summary_data[best]['mean']:.2f}s vs best"}
                </div>
            </div>
            """, unsafe_allow_html=True)

    # Win probability
    if len(results) == 2:
        names = list(results.keys())
        t1, t2 = results[names[0]]["times"], results[names[1]]["times"]
        prob_1_wins = np.mean(t1 < t2)
        st.markdown(f"""
        <div style="background:#111;border:1px solid #222;border-radius:4px;padding:1rem;margin:1rem 0;
             font-family:'JetBrains Mono',monospace;font-size:0.85rem;">
            <span style="color:#888;">WIN PROBABILITY → </span>
            <span style="color:{results[names[0]]['color']};font-weight:700;">{names[0]}: {prob_1_wins:.1%}</span>
            <span style="color:#444;margin:0 0.5rem;">|</span>
            <span style="color:{results[names[1]]['color']};font-weight:700;">{names[1]}: {1-prob_1_wins:.1%}</span>
        </div>
        """, unsafe_allow_html=True)

    # Distribution chart
    fig = go.Figure()
    for name, res in results.items():
        times = res["times"]
        fig.add_trace(go.Histogram(
            x=times,
            name=name,
            nbinsx=80,
            opacity=0.7,
            marker_color=res["color"],
            hovertemplate=f"<b>{name}</b><br>Race time: %{{x:.1f}}s<br>Count: %{{y}}<extra></extra>",
        ))

    fig.update_layout(
        barmode="overlay",
        xaxis_title="Total Race Time (s)",
        yaxis_title="Frequency",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    apply_base(fig, f"Race Time Distribution ({n_sims if 'n_sims' in dir() else 10000:,} simulations)", height=380)
    st.plotly_chart(fig, use_container_width=True)

    # SC sensitivity
    st.markdown('<hr style="border:none;border-top:1px solid #222;margin:1.5rem 0;">', unsafe_allow_html=True)
    st.markdown("### SAFETY CAR SENSITIVITY")
    st.markdown('<div style="font-family:JetBrains Mono,monospace;font-size:0.7rem;color:#555;margin-bottom:1rem;">How does the strategy recommendation change as SC probability increases?</div>', unsafe_allow_html=True)
    _render_sc_sensitivity(results, strategies, total_laps)


def _render_sc_sensitivity(results: dict, strategies: dict, total_laps: int):
    """Show how each strategy's expected time changes with SC probability."""
    sc_probs = np.linspace(0, 1.0, 21)

    # Re-run simplified version just for mean times at different SC probs
    fig = go.Figure()

    for name, strat in strategies.items():
        means = []
        for sc_p in sc_probs:
            # Quick estimate: SC reduces pit loss for 1 stop per SC
            sc_savings = sc_p * 15.0 * len(strat["stops"])  # ~15s saving per stop when SC occurs
            # Base mean from simulation
            base_mean = np.mean(results[name]["times"])
            adjusted_mean = base_mean - sc_savings
            means.append(adjusted_mean)

        fig.add_trace(go.Scatter(
            x=sc_probs,
            y=means,
            mode="lines+markers",
            name=name,
            line=dict(color=strat["color"], width=2),
            marker=dict(size=5, color=strat["color"]),
            hovertemplate=f"<b>{name}</b><br>SC prob: %{{x:.0%}}<br>Expected time: %{{y:.1f}}s<extra></extra>",
        ))

    fig.update_layout(
        xaxis=dict(title="Safety Car Probability", tickformat=".0%"),
        yaxis_title="Expected Race Time (s)",
    )
    apply_base(fig, "Strategy Sensitivity to Safety Car", height=350)
    st.plotly_chart(fig, use_container_width=True)

    st.markdown(
        '<div style="font-family:JetBrains Mono,monospace;font-size:0.65rem;color:#555;">'
        'Multi-stop strategies benefit more from SC events (free pit windows). '
        'Higher SC probability shifts the advantage toward more stops.'
        '</div>',
        unsafe_allow_html=True
    )
