# PitWall — F1 Race Strategy Intelligence

> An open-source F1 strategy analysis tool built for the Cadillac Formula 1 Team Graduate Strategy Analyst application.

## What it does

PitWall is a 7-tab Streamlit app that replicates the kind of post-session and pre-race strategy analysis that F1 teams do professionally:

| Tab | What it shows |
|---|---|
| Race Overview | Championship standings, position trace, race results |
| Tyre Strategy | Stint timeline coloured by compound, pit stop times |
| Tyre Degradation | Deg curves per compound, fuel-corrected pace, team distributions |
| Undercut Analyser | Interactive undercut/overcut calculator with real race calibration |
| Strategy Simulator | Monte Carlo 1-stop vs 2-stop, safety car sensitivity |
| Team Comparison | Head-to-head pace, pit stop consistency, Cadillac 2026 trajectory |
| AI Analyst | Groq LLM chat loaded with real race context |

---

## Setup

### 1. Clone and install

```bash
git clone https://github.com/yourusername/pitwall.git
cd pitwall
pip install -r requirements.txt
```

### 2. Run

```bash
streamlit run app.py
```

---

## API Keys

### Groq API (required for AI Analyst tab)

1. Go to [console.groq.com](https://console.groq.com)
2. Sign up — **no credit card required**
3. Go to API Keys → Create API Key
4. Copy the key (starts with `gsk_...`)
5. Paste it into the sidebar of the app

**Free tier limits:** ~30 requests/min, 1,000 requests/day for llama-3.3-70b-versatile.
This is plenty for demo and application use.

### No other keys needed

FastF1 pulls data directly from F1's live timing API — no key required.
OpenF1 and Jolpica (Ergast) are also free and keyless.

---

## Data sources

| Source | What it provides | Key required? |
|---|---|---|
| FastF1 | Lap times, telemetry, tyre data, pit stops, results (2018–2026) | No |
| OpenF1 API | Near-real-time race data, position streams | No |
| Jolpica | Driver & constructor standings (Ergast replacement) | No |
| Groq API | LLM inference for AI Analyst | Yes (free) |

---

## Tech stack

```
Python 3.10+
streamlit 1.45      # UI framework
fastf1 3.4          # F1 data
plotly 5.24         # Interactive charts
pandas / numpy      # Data processing
groq 0.11           # LLM inference (Llama 3.3 70B)
requests            # Jolpica standings API
```

---

## Architecture

```
app.py                  ← Streamlit entry point, sidebar, routing
├── pages/
│   ├── race_overview.py      ← Standings + position trace
│   ├── tyre_strategy.py      ← Stint timeline
│   ├── tyre_degradation.py   ← Deg curves + pace distribution
│   ├── undercut.py           ← Undercut/overcut calculator
│   ├── simulator.py          ← Monte Carlo strategy engine
│   ├── team_comparison.py    ← Head-to-head + Cadillac trajectory
│   └── ai_analyst.py         ← Groq AI chat with race context
└── utils/
    ├── data.py               ← FastF1 loaders, caching, constants
    └── plots.py              ← Plotly dark theme factory
```

**Design principle:** All strategy maths is deterministic Python. Groq is only used for natural-language explanation — never for the numbers.

---

## Strategy engine notes

- **Fuel correction:** ~0.057s/lap improvement as fuel burns off, applied before pace comparison
- **Clean laps filter:** removes in/out laps, SC laps (TrackStatus 4/5/6/7), and laps >110% of session median
- **Degradation slope:** linear regression (polyfit) on median lap time vs tyre age per compound
- **Undercut maths:** `net_delta = (fresh_tyre_delta + rival_deg) × laps - pit_loss - out_lap_penalty`
- **Monte Carlo:** 10,000 simulations per strategy, vectorised with NumPy, sampling from normal distributions for pit stop time and safety car timing

---

## Disclaimer

This tool uses unofficial F1 data via FastF1 and is not affiliated with Formula 1, the FIA, or the Cadillac Formula 1 Team. Built as a personal portfolio project.
