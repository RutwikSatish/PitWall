import streamlit as st
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

st.set_page_config(
    page_title="PitWall — F1 Strategy Intelligence",
    page_icon="🏎️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Exo+2:wght@300;400;600;700;900&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
    --red:     #E8002D;
    --white:   #FFFFFF;
    --dark:    #0A0A0A;
    --panel:   #111111;
    --border:  #222222;
    --muted:   #888888;
    --accent:  #E8002D;
    --yellow:  #FFD700;
    --green:   #39FF14;
    --gap:     1.5rem;
}

html, body, [data-testid="stAppViewContainer"] {
    background-color: var(--dark) !important;
    color: var(--white) !important;
    font-family: 'Exo 2', sans-serif;
}

[data-testid="stSidebar"] {
    background-color: var(--panel) !important;
    border-right: 1px solid var(--border) !important;
}

[data-testid="stSidebar"] * { color: var(--white) !important; }

h1, h2, h3, h4 {
    font-family: 'Exo 2', sans-serif;
    font-weight: 900;
    letter-spacing: -0.02em;
}

.metric-card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-left: 3px solid var(--red);
    border-radius: 4px;
    padding: 1rem 1.25rem;
    margin-bottom: 0.75rem;
}

.metric-card .label {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 0.25rem;
}

.metric-card .value {
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--white);
    line-height: 1;
}

.metric-card .delta {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    color: var(--muted);
    margin-top: 0.2rem;
}

.team-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 2px;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.7rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}

.stTabs [data-baseweb="tab-list"] {
    background: var(--panel);
    border-bottom: 1px solid var(--border);
    gap: 0;
}

.stTabs [data-baseweb="tab"] {
    background: transparent;
    color: var(--muted) !important;
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    border: none;
    padding: 0.75rem 1.5rem;
}

.stTabs [aria-selected="true"] {
    background: transparent !important;
    color: var(--white) !important;
    border-bottom: 2px solid var(--red) !important;
}

.stSelectbox > div, .stSlider > div {
    background: var(--panel) !important;
    border-color: var(--border) !important;
    color: var(--white) !important;
}

.stButton > button {
    background: var(--red) !important;
    color: var(--white) !important;
    border: none !important;
    border-radius: 3px !important;
    font-family: 'Exo 2', sans-serif !important;
    font-weight: 700 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.08em !important;
    padding: 0.5rem 1.5rem !important;
    transition: opacity 0.15s !important;
}

.stButton > button:hover { opacity: 0.85 !important; }

div[data-testid="stMarkdownContainer"] p {
    font-family: 'Exo 2', sans-serif;
    color: var(--white);
}

.pitwall-header {
    display: flex;
    align-items: baseline;
    gap: 0.75rem;
    margin-bottom: 0.25rem;
}

.pitwall-logo {
    font-family: 'Exo 2', sans-serif;
    font-weight: 900;
    font-size: 1.6rem;
    color: var(--white);
    letter-spacing: -0.03em;
}

.pitwall-logo span { color: var(--red); }

.pitwall-sub {
    font-family: 'JetBrains Mono', monospace;
    font-size: 0.65rem;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.12em;
}

.section-rule {
    border: none;
    border-top: 1px solid var(--border);
    margin: 1.5rem 0;
}

.stAlert {
    background: var(--panel) !important;
    border: 1px solid var(--border) !important;
    color: var(--white) !important;
}

.compound-SOFT   { background:#E8002D; color:#fff; }
.compound-MEDIUM { background:#FFD700; color:#000; }
.compound-HARD   { background:#FFFFFF; color:#000; }
.compound-INTERMEDIATE { background:#39FF14; color:#000; }
.compound-WET    { background:#0080FF; color:#fff; }

/* Chat bubbles for AI analyst */
.chat-user {
    background: var(--border);
    border-radius: 8px 8px 2px 8px;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
    font-size: 0.9rem;
    max-width: 80%;
    margin-left: auto;
}

.chat-ai {
    background: #1a1a1a;
    border: 1px solid var(--border);
    border-left: 3px solid var(--red);
    border-radius: 2px 8px 8px 8px;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
    font-size: 0.9rem;
    max-width: 85%;
    line-height: 1.6;
}

.stTextInput input {
    background: var(--panel) !important;
    border: 1px solid var(--border) !important;
    color: var(--white) !important;
    font-family: 'Exo 2', sans-serif !important;
}

.stMarkdown code {
    background: var(--panel);
    color: var(--green);
    font-family: 'JetBrains Mono', monospace;
    padding: 0.1em 0.4em;
    border-radius: 3px;
    font-size: 0.85em;
}
</style>
""", unsafe_allow_html=True)

# ── Sidebar nav ─────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div class="pitwall-header" style="margin-bottom:1.5rem;">
        <div class="pitwall-logo">PIT<span>WALL</span></div>
        <div class="pitwall-sub">F1 Strategy Intel</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="pitwall-sub" style="margin-bottom:0.5rem;">Navigation</div>', unsafe_allow_html=True)

    page = st.radio(
        "",
        [
            "🏁  Race Overview",
            "🔴  Tyre Strategy",
            "📉  Tyre Degradation",
            "⚔️  Undercut Analyser",
            "🎲  Strategy Simulator",
            "🏎️  Team Comparison",
            "🤖  AI Analyst",
        ],
        label_visibility="collapsed",
    )

    st.markdown('<hr class="section-rule">', unsafe_allow_html=True)

    st.markdown('<div class="pitwall-sub" style="margin-bottom:0.5rem;">API Keys</div>', unsafe_allow_html=True)

    import os
    # Auto-load from Streamlit secrets
    try:
        _secret_key = st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        _secret_key = ""

    if _secret_key:
        os.environ["GROQ_API_KEY"] = _secret_key
        groq_key = _secret_key
        st.success("✓ Groq connected", icon="🔑")
    else:
        groq_key = st.text_input(
            "Groq API Key", type="password",
            placeholder="gsk_...",
            help="Required for AI Analyst. Free at console.groq.com"
        )
        if groq_key:
            os.environ["GROQ_API_KEY"] = groq_key
            st.success("✓ Groq connected", icon="🔑")

    st.markdown('<hr class="section-rule">', unsafe_allow_html=True)
    st.markdown("""
    <div style="font-family:'JetBrains Mono',monospace; font-size:0.6rem; color:#555; line-height:1.8;">
    DATA SOURCES<br>
    FastF1 · OpenF1 API<br>
    Jolpica (Ergast)<br><br>
    SEASON<br>
    2018 – 2025<br>
    (2026 partial)<br><br>
    BUILT FOR<br>
    Cadillac F1 Team<br>
    Graduate Application
    </div>
    """, unsafe_allow_html=True)


# ── Page routing ─────────────────────────────────────────────────────────────
if page == "🏁  Race Overview":
    from pages._race_overview import render
    render()
elif page == "🔴  Tyre Strategy":
    from pages._tyre_strategy import render
    render()
elif page == "📉  Tyre Degradation":
    from pages._tyre_degradation import render
    render()
elif page == "⚔️  Undercut Analyser":
    from pages._undercut import render
    render()
elif page == "🎲  Strategy Simulator":
    from pages._simulator import render
    render()
elif page == "🏎️  Team Comparison":
    from pages._team_comparison import render
    render()
elif page == "🤖  AI Analyst":
    from pages._ai_analyst import render
    render(groq_key)
