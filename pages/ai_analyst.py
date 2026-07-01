"""
pages/ai_analyst.py — Groq-powered AI race strategy analyst with data context
"""

import streamlit as st
import json
import pandas as pd
import numpy as np
from utils.data import (
    load_session, get_race_name_list, get_clean_laps,
    AVAILABLE_YEARS, fuel_correct, get_team_color
)

SYSTEM_PROMPT = """You are PitWall AI, an expert Formula 1 race strategy analyst.
You have deep knowledge of F1 strategy: undercuts, overcuts, tyre degradation, pit windows,
safety car strategy, DRS/active aero systems, and the 2026 regulations.

You are specifically helping analyse Cadillac Formula 1 Team's 2026 season.
The team is in its debut season, running the MAC-26 chassis with Ferrari power units.
Drivers: Sergio Pérez (#11) and Valtteri Bottas. They have 0 points after 8 rounds.

Key 2026 context:
- DRS replaced by active aerodynamics (X-mode/Z-mode) 
- Overtake Mode: extra electrical boost within 1s of rival
- Mercedes dominating early with Antonelli (171pts) and Russell (131pts)
- Cadillac best result: Pérez P10 at Monaco, then penalised to P15

When given race data (lap times, tyre compounds, pit stops), analyse it like a professional
strategy engineer. Be specific with numbers. Explain trade-offs clearly.
Keep responses concise but insightful — you're on the pit wall, not writing an essay.
Use technical F1 terminology correctly.

If asked about strategy decisions, explain using:
1. The quantitative reasoning (lap delta, pit loss, undercut window)
2. What actually happened
3. What the alternative was and why it may/may not have worked
"""


def render(groq_key: str = ""):
    st.markdown("""
    <div style="margin-bottom:1.5rem;">
        <div style="font-family:'Exo 2',sans-serif;font-weight:900;font-size:2rem;letter-spacing:-0.03em;">
            AI Analyst
        </div>
        <div style="font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#666;text-transform:uppercase;letter-spacing:0.1em;">
            Groq · llama-3.3-70b-versatile · Race strategy intelligence
        </div>
    </div>
    """, unsafe_allow_html=True)

    if not groq_key:
        st.markdown("""
        <div style="background:#111;border:1px solid #E8002D;border-radius:4px;padding:1.5rem;text-align:center;">
            <div style="font-family:'Exo 2',sans-serif;font-weight:700;font-size:1.1rem;margin-bottom:0.5rem;">
                🔑 Groq API Key Required
            </div>
            <div style="font-family:'JetBrains Mono',monospace;font-size:0.75rem;color:#888;">
                Enter your key in the sidebar to activate the AI Analyst.<br>
                Free at <a href="https://console.groq.com" style="color:#E8002D;">console.groq.com</a> — no credit card needed.
            </div>
        </div>
        """, unsafe_allow_html=True)
        return

    # ── Load race context ─────────────────────────────────────────────────
    st.markdown("### LOAD RACE CONTEXT")
    st.markdown('<div style="font-family:JetBrains Mono,monospace;font-size:0.7rem;color:#555;margin-bottom:1rem;">Loading a race gives the AI specific lap times, compounds, and pit data to reason from.</div>', unsafe_allow_html=True)

    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        year = st.selectbox("Season", AVAILABLE_YEARS, key="ai_year")
    with c2:
        races = get_race_name_list(year)
        if not races:
            st.warning("Could not load schedule.")
            return
        gp = st.selectbox("Grand Prix", races, index=min(7, len(races)-1), key="ai_gp")
    with c3:
        load_btn = st.button("Load Race Data", key="ai_load")

    context_str = ""

    if load_btn or st.session_state.get("ai_context"):
        if load_btn:
            with st.spinner(f"Loading {gp} {year} for AI context…"):
                session = load_session(year, gp, "R")
            if session:
                context_str = _build_race_context(session, gp, year)
                st.session_state["ai_context"] = context_str
                st.session_state["ai_context_label"] = f"{gp} {year}"
                st.success(f"✓ Race context loaded: {gp} {year}")
        else:
            context_str = st.session_state.get("ai_context", "")

        if context_str:
            label = st.session_state.get("ai_context_label", "Race")
            st.markdown(f"""
            <div style="background:#111;border:1px solid #222;border-radius:4px;padding:0.5rem 1rem;
                 font-family:'JetBrains Mono',monospace;font-size:0.7rem;color:#555;margin-bottom:1rem;">
                📊 Context loaded: <span style="color:#39FF14;">{label}</span>
                — AI can now answer specific questions about this race.
            </div>
            """, unsafe_allow_html=True)

    # ── Quick prompts ─────────────────────────────────────────────────────
    st.markdown("### QUICK ANALYSIS")
    quick_prompts = [
        "Summarise the race strategy overview",
        "Which team had the best tyre management?",
        "Were there any undercut opportunities?",
        "What should Cadillac's strategy focus be to score their first point?",
        "How does the 2026 active aero change strategy vs DRS?",
        "Explain Pérez's Monaco penalty and what it means strategically",
    ]

    cols = st.columns(3)
    for i, prompt in enumerate(quick_prompts):
        with cols[i % 3]:
            if st.button(prompt, key=f"qp_{i}"):
                st.session_state["ai_input"] = prompt

    # ── Chat interface ────────────────────────────────────────────────────
    st.markdown('<hr style="border:none;border-top:1px solid #222;margin:1.5rem 0;">', unsafe_allow_html=True)
    st.markdown("### ANALYST CHAT")

    if "ai_messages" not in st.session_state:
        st.session_state["ai_messages"] = []

    # Display history
    for msg in st.session_state["ai_messages"]:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-user">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-ai">{msg["content"]}</div>', unsafe_allow_html=True)

    # Input
    user_input = st.text_input(
        "Ask the analyst…",
        value=st.session_state.pop("ai_input", ""),
        placeholder="e.g. Was a 2-stop the right call? How can Cadillac score their first point?",
        key="ai_chat_input",
    )

    col_send, col_clear = st.columns([1, 5])
    with col_send:
        send = st.button("Send →", key="ai_send")
    with col_clear:
        if st.button("Clear chat", key="ai_clear"):
            st.session_state["ai_messages"] = []
            st.rerun()

    if send and user_input.strip():
        _handle_chat(user_input.strip(), context_str, groq_key)


def _build_race_context(session, gp: str, year: int) -> str:
    """Build a compact JSON summary of the race for the LLM context."""
    try:
        context = {"race": f"{gp} {year}", "summary": {}}

        # Results
        try:
            results = session.results[["Abbreviation", "FullName", "TeamName", "Position", "Points", "Status"]].copy()
            results = results.sort_values("Position").head(11)
            context["top_11"] = results.to_dict("records")
        except Exception:
            pass

        # Tyre strategies
        try:
            laps = session.laps.copy()
            stints = (
                laps.groupby(["Driver", "Stint", "Compound", "Team"])
                .agg(start_lap=("LapNumber", "min"), end_lap=("LapNumber", "max"))
                .reset_index()
            )
            stints["laps"] = stints["end_lap"] - stints["start_lap"] + 1
            context["tyre_strategies"] = stints[["Driver", "Team", "Stint", "Compound", "start_lap", "laps"]].to_dict("records")
        except Exception:
            pass

        # Pit stops
        try:
            pit_laps = laps[laps["PitInTime"].notna()].copy()
            pit_laps["StopTime"] = (laps["PitOutTime"] - laps["PitInTime"]).dt.total_seconds()
            valid = pit_laps[pit_laps["StopTime"].between(1.5, 15)].copy()
            context["pit_stops"] = valid[["Driver", "LapNumber", "Compound", "StopTime"]].round(2).to_dict("records")
        except Exception:
            pass

        # Pace summary
        try:
            clean = get_clean_laps(session)
            if not clean.empty:
                pace = clean.groupby("Driver")["LapTimeSec"].agg(["median", "min", "count"]).round(3)
                pace.columns = ["median_pace", "best_lap", "clean_laps"]
                context["driver_pace"] = pace.reset_index().to_dict("records")
        except Exception:
            pass

        # Total laps
        try:
            context["total_laps"] = int(session.laps["LapNumber"].max())
        except Exception:
            pass

        return json.dumps(context, default=str, indent=2)

    except Exception as e:
        return f"Race context partially loaded ({e})"


def _handle_chat(user_input: str, context_str: str, groq_key: str):
    """Send message to Groq and stream response."""
    try:
        from groq import Groq
    except ImportError:
        st.error("Groq package not installed. Run: pip install groq")
        return

    client = Groq(api_key=groq_key)

    # Build messages
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if context_str:
        messages.append({
            "role": "user",
            "content": f"Here is the race data context for this session:\n\n```json\n{context_str}\n```\n\nPlease use this data when answering questions."
        })
        messages.append({
            "role": "assistant",
            "content": "Race data loaded. I have the lap times, tyre strategies, pit stops, and pace data ready. What would you like to analyse?"
        })

    # Add chat history
    for msg in st.session_state["ai_messages"][-6:]:  # last 6 for context window efficiency
        messages.append(msg)

    # Add current message
    messages.append({"role": "user", "content": user_input})

    # Add to display history
    st.session_state["ai_messages"].append({"role": "user", "content": user_input})

    try:
        with st.spinner("Analyst thinking…"):
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                max_tokens=1000,
                temperature=0.3,  # lower = more deterministic/factual
            )
            ai_reply = response.choices[0].message.content

        st.session_state["ai_messages"].append({"role": "assistant", "content": ai_reply})
        st.rerun()

    except Exception as e:
        err = str(e)
        if "429" in err:
            st.warning("Rate limit hit. Wait 60s and try again (Groq free tier: 30 req/min).")
        elif "401" in err or "auth" in err.lower():
            st.error("Invalid Groq API key. Check your key at console.groq.com.")
        else:
            st.error(f"Groq error: {err}")
