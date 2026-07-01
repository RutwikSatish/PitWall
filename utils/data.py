"""
utils/data.py — FastF1 session loading, caching helpers, shared constants
"""

import os
import fastf1
import fastf1.plotting
import pandas as pd
import numpy as np
import streamlit as st

# ── Cache directory ──────────────────────────────────────────────────────────
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".f1cache")
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

# ── Official team colours (2026 grid) ────────────────────────────────────────
TEAM_COLORS = {
    "Mercedes":      "#00D2BE",
    "Ferrari":       "#E8002D",
    "McLaren":       "#FF8000",
    "Red Bull":      "#3671C6",
    "Red Bull Racing":"#3671C6",
    "Williams":      "#64C4FF",
    "Aston Martin":  "#358C75",
    "Alpine":        "#FF87BC",
    "Racing Bulls":  "#6692FF",
    "Haas":          "#B6BABD",
    "Haas F1 Team":  "#B6BABD",
    "Audi":          "#C9B430",
    "Cadillac":      "#CC1E4A",
    "Kick Sauber":   "#52E252",
}

COMPOUND_COLORS = {
    "SOFT":         "#E8002D",
    "MEDIUM":       "#FFD700",
    "HARD":         "#FFFFFF",
    "INTERMEDIATE": "#39FF14",
    "WET":          "#0080FF",
    "UNKNOWN":      "#888888",
    "TEST_UNKNOWN": "#888888",
}

DRIVER_TEAMS_2026 = {
    "VER": "Red Bull Racing", "HAD": "Red Bull Racing",
    "LEC": "Ferrari",         "HAM": "Ferrari",
    "NOR": "McLaren",         "PIA": "McLaren",
    "RUS": "Mercedes",        "ANT": "Mercedes",
    "ALB": "Williams",        "SAI": "Williams",
    "LAW": "Racing Bulls",    "LIN": "Racing Bulls",
    "ALO": "Aston Martin",    "STR": "Aston Martin",
    "GAS": "Alpine",          "COL": "Alpine",
    "OCO": "Haas",            "BEA": "Haas",
    "HUL": "Audi",            "BOR": "Audi",
    "PER": "Cadillac",        "BOT": "Cadillac",
}

AVAILABLE_YEARS = list(range(2025, 2018, -1))  # FastF1 data goes back reliably to 2019


@st.cache_data(ttl=3600, show_spinner=False)
def get_event_schedule(year: int) -> pd.DataFrame:
    """Return the event schedule for a given year."""
    try:
        schedule = fastf1.get_event_schedule(year, include_testing=False)
        return schedule
    except Exception as e:
        st.error(f"Could not load schedule: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def load_session(year: int, gp: str, session_type: str = "R"):
    """
    Load a FastF1 session.
    session_type: 'R' = Race, 'Q' = Qualifying, 'FP1'/'FP2'/'FP3' = Practice
    """
    try:
        session = fastf1.get_session(year, gp, session_type)
        session.load(telemetry=False, weather=True, messages=True)
        return session
    except Exception as e:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def load_session_with_telemetry(year: int, gp: str, session_type: str = "R"):
    """Load session including telemetry — slower, use sparingly."""
    try:
        session = fastf1.get_session(year, gp, session_type)
        session.load(telemetry=True, weather=True, messages=True)
        return session
    except Exception as e:
        return None


def get_clean_laps(session) -> pd.DataFrame:
    """
    Return laps filtered for analysis:
    - IsAccurate == True
    - No in/out laps (PitInTime & PitOutTime NaT)
    - No safety car laps (TrackStatus not containing '4' or '5')
    - LapTime within 110% of session median
    """
    laps = session.laps.copy()
    laps = laps[laps["IsAccurate"] == True]

    # Drop obvious in/out laps
    laps = laps[laps["PitInTime"].isna() & laps["PitOutTime"].isna()]

    # Drop SC / VSC laps
    if "TrackStatus" in laps.columns:
        laps = laps[~laps["TrackStatus"].str.contains("4|5|6|7", na=False)]

    # Drop extreme outliers
    median_lap = laps["LapTime"].median()
    if pd.notna(median_lap):
        laps = laps[laps["LapTime"] < median_lap * 1.10]

    # Convert LapTime to seconds float
    if "LapTime" in laps.columns:
        laps["LapTimeSec"] = laps["LapTime"].dt.total_seconds()

    return laps.reset_index(drop=True)


def fuel_correct(laps: pd.DataFrame, total_laps: int, correction_per_lap: float = 0.057) -> pd.DataFrame:
    """
    Fuel-correct lap times: early laps are heavier → slower.
    Add `LapTimeCorr` column = LapTimeSec minus the fuel effect.
    correction_per_lap ≈ 0.057 s/lap (standard estimate).
    """
    laps = laps.copy()
    if "LapTimeSec" not in laps.columns:
        return laps
    # Fuel-corrected = raw - (remaining_fuel_contribution)
    # remaining laps = (total_laps - LapNumber) → heavier early, lighter late
    laps["FuelCorrection"] = (total_laps - laps["LapNumber"]) * correction_per_lap
    laps["LapTimeCorr"] = laps["LapTimeSec"] - laps["FuelCorrection"]
    return laps


def get_team_color(team_name: str) -> str:
    for key, color in TEAM_COLORS.items():
        if key.lower() in team_name.lower():
            return color
    return "#888888"


def format_laptime(seconds: float) -> str:
    """Format float seconds as M:SS.mmm"""
    if pd.isna(seconds) or seconds <= 0:
        return "—"
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}:{s:06.3f}"


def get_race_name_list(year: int) -> list:
    """Return list of GP names for a year."""
    schedule = get_event_schedule(year)
    if schedule.empty:
        return []
    return schedule["EventName"].tolist()


@st.cache_data(ttl=86400, show_spinner=False)
def get_standings(year: int, round_number: int = None) -> tuple:
    """Fetch driver & constructor standings via Jolpica."""
    import requests
    base = "https://api.jolpi.ca/ergast/f1"

    if round_number:
        d_url = f"{base}/{year}/{round_number}/driverStandings.json?limit=30"
        c_url = f"{base}/{year}/{round_number}/constructorStandings.json?limit=20"
    else:
        d_url = f"{base}/{year}/driverStandings.json?limit=30"
        c_url = f"{base}/{year}/constructorStandings.json?limit=20"

    try:
        dr = requests.get(d_url, timeout=10).json()
        cr = requests.get(c_url, timeout=10).json()

        d_list = dr["MRData"]["StandingsTable"]["StandingsLists"]
        c_list = cr["MRData"]["StandingsTable"]["StandingsLists"]

        drivers = d_list[0]["DriverStandings"] if d_list else []
        constructors = c_list[0]["ConstructorStandings"] if c_list else []
        return drivers, constructors
    except Exception:
        return [], []
