"""
utils/data.py — FastF1 session loading, caching helpers, shared constants
Includes OpenF1 API fallbacks for pit stop and team data
"""

import os
import fastf1
import fastf1.plotting
import pandas as pd
import numpy as np
import requests
import streamlit as st

# ── Cache directory ──────────────────────────────────────────────────────────
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".f1cache")
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

# ── Official team colours ────────────────────────────────────────────────────
TEAM_COLORS = {
    "Mercedes":        "#00D2BE",
    "Ferrari":         "#E8002D",
    "McLaren":         "#FF8000",
    "Red Bull":        "#3671C6",
    "Red Bull Racing": "#3671C6",
    "Williams":        "#64C4FF",
    "Aston Martin":    "#358C75",
    "Alpine":          "#FF87BC",
    "Racing Bulls":    "#6692FF",
    "RB F1 Team":      "#6692FF",
    "Haas":            "#B6BABD",
    "Haas F1 Team":    "#B6BABD",
    "Audi":            "#C9B430",
    "Sauber":          "#C9B430",
    "Kick Sauber":     "#52E252",
    "Cadillac":        "#CC1E4A",
    "AlphaTauri":      "#6692FF",
    "Alfa Romeo":      "#B12039",
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

# Driver → team map for years when FastF1 team data is sparse
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

DRIVER_TEAMS_2025 = {
    "VER": "Red Bull Racing", "LAW": "Red Bull Racing",
    "LEC": "Ferrari",         "HAM": "Ferrari",
    "NOR": "McLaren",         "PIA": "McLaren",
    "RUS": "Mercedes",        "ANT": "Mercedes",
    "ALB": "Williams",        "SAI": "Williams",
    "TSU": "Racing Bulls",    "HAD": "Racing Bulls",
    "ALO": "Aston Martin",    "STR": "Aston Martin",
    "GAS": "Alpine",          "DOO": "Alpine",
    "OCO": "Haas",            "BEA": "Haas",
    "HUL": "Sauber",          "BOR": "Sauber",
}

DRIVER_TEAMS_LOOKUP = {2026: DRIVER_TEAMS_2026, 2025: DRIVER_TEAMS_2025}

AVAILABLE_YEARS = list(range(2025, 2018, -1))


# ── Session loading ──────────────────────────────────────────────────────────

@st.cache_data(ttl=3600, show_spinner=False)
def get_event_schedule(year: int) -> pd.DataFrame:
    try:
        return fastf1.get_event_schedule(year, include_testing=False)
    except Exception as e:
        st.error(f"Could not load schedule: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def load_session(year: int, gp: str, session_type: str = "R"):
    try:
        session = fastf1.get_session(year, gp, session_type)
        session.load(telemetry=False, weather=True, messages=True)
        return session
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def load_session_with_telemetry(year: int, gp: str, session_type: str = "R"):
    try:
        session = fastf1.get_session(year, gp, session_type)
        session.load(telemetry=True, weather=True, messages=True)
        return session
    except Exception:
        return None


# ── Team data helpers ────────────────────────────────────────────────────────

def get_team_map(session) -> dict:
    """
    Return {driver_abbreviation: team_name} from all available sources.
    Priority: session.results > session.laps > hardcoded lookup > OpenF1
    """
    team_map = {}

    # 1. session.results — most reliable
    try:
        res = session.results[["Abbreviation", "TeamName"]].dropna()
        team_map = dict(zip(res["Abbreviation"], res["TeamName"]))
        if team_map:
            return team_map
    except Exception:
        pass

    # 2. session.laps Team column
    try:
        laps_teams = (
            session.laps[["Driver", "Team"]]
            .dropna(subset=["Team"])
            .drop_duplicates(subset=["Driver"])
        )
        if not laps_teams.empty:
            return dict(zip(laps_teams["Driver"], laps_teams["Team"]))
    except Exception:
        pass

    # 3. Hardcoded lookup by year
    try:
        year = session.event["EventDate"].year
        lookup = DRIVER_TEAMS_LOOKUP.get(year, {})
        if lookup:
            return lookup
    except Exception:
        pass

    # 4. OpenF1 API fallback
    try:
        year = session.event["EventDate"].year
        gp_round = session.event["RoundNumber"]
        url = f"https://api.openf1.org/v1/drivers?session_key=latest&year={year}"
        r = requests.get(url, timeout=8)
        if r.status_code == 200:
            drivers_data = r.json()
            for d in drivers_data:
                abbr = d.get("name_acronym", "")
                team = d.get("team_name", "")
                if abbr and team:
                    team_map[abbr] = team
            if team_map:
                return team_map
    except Exception:
        pass

    return team_map


def enrich_laps_with_teams(laps: pd.DataFrame, session) -> pd.DataFrame:
    """
    Add 'Team' column to a laps DataFrame using all available sources.
    Always returns a DataFrame — Team column may be 'Unknown' if no data found.
    """
    laps = laps.copy()
    team_map = get_team_map(session)

    if team_map:
        laps["Team"] = laps["Driver"].map(team_map).fillna("Unknown")
    else:
        laps["Team"] = "Unknown"

    return laps


# ── Pit stop helpers ─────────────────────────────────────────────────────────

def get_pit_stops(session) -> pd.DataFrame:
    """
    Return pit stop DataFrame with columns:
    Driver, LapNumber, StopTime, Team, Compound
    
    Priority: FastF1 PitInTime/PitOutTime > OpenF1 /pit endpoint > Jolpica
    """

    # 1. FastF1 native pit data
    try:
        laps = session.laps.copy()
        pit_laps = laps[laps["PitInTime"].notna()].copy()
        pit_laps["StopTime"] = (
            laps["PitOutTime"] - laps["PitInTime"]
        ).dt.total_seconds()
        valid = pit_laps[pit_laps["StopTime"].between(1.5, 60)].copy()

        if not valid.empty:
            team_map = get_team_map(session)
            valid["Team"] = valid["Driver"].map(team_map).fillna("Unknown")
            cols = [c for c in ["Driver", "LapNumber", "StopTime", "Team", "Compound"] if c in valid.columns]
            return valid[cols].reset_index(drop=True)
    except Exception:
        pass

    # 2. OpenF1 /pit endpoint — requires session_key, field is stop_duration
    try:
        # Get session_key from FastF1 session object
        session_key = None
        try:
            session_key = session.session_info.get("Key") or session._session_key
        except Exception:
            pass
        if not session_key:
            try:
                year = session.event["EventDate"].year
                gp_round = int(session.event["RoundNumber"])
                s_url = f"https://api.openf1.org/v1/sessions?year={year}&meeting_key={gp_round}&session_name=Race"
                sr = requests.get(s_url, timeout=8)
                if sr.status_code == 200 and sr.json():
                    session_key = sr.json()[0].get("session_key")
            except Exception:
                pass

        if session_key:
            url = f"https://api.openf1.org/v1/pit?session_key={session_key}"
            r = requests.get(url, timeout=10)
            if r.status_code == 200 and r.json():
                pit_data = r.json()
                df = pd.DataFrame(pit_data)
                if not df.empty and "pit_duration" in df.columns:
                    df = df.rename(columns={
                        "driver_number": "DriverNum",
                        "lap_number": "LapNumber",
                        "pit_duration": "StopTime",
                    })
                    df["StopTime"] = pd.to_numeric(df["StopTime"], errors="coerce")
                    df = df[df["StopTime"].between(1.5, 60)]
                    # Map driver number → abbreviation
                    try:
                        num_map = dict(zip(
                            session.results["DriverNumber"].astype(str),
                            session.results["Abbreviation"]
                        ))
                        df["Driver"] = df["DriverNum"].astype(str).map(num_map).fillna("???")
                    except Exception:
                        df["Driver"] = df["DriverNum"].astype(str)
                    team_map = get_team_map(session)
                    df["Team"] = df["Driver"].map(team_map).fillna("Unknown")
                    return df[["Driver", "LapNumber", "StopTime", "Team"]].reset_index(drop=True)
    except Exception:
        pass

    # 3. Jolpica fallback
    try:
        year = session.event["EventDate"].year
        gp_round = int(session.event["RoundNumber"])
        url = f"https://api.jolpi.ca/ergast/f1/{year}/{gp_round}/pitstops.json?limit=100"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            data = r.json()
            stops = data["MRData"]["RaceTable"]["Races"]
            if stops:
                pit_list = stops[0].get("PitStops", [])
                rows = []
                for p in pit_list:
                    # duration is a string like "25.627"
                    try:
                        raw = p.get("duration", "0")
                        # Ergast format: "1:23.456" or "23.456"
                        if ":" in str(raw):
                            parts = str(raw).split(":")
                            duration = int(parts[0]) * 60 + float(parts[1])
                        else:
                            duration = float(raw)
                    except Exception:
                        duration = 0
                    rows.append({
                        "Driver": p.get("driverId", "").upper()[:3],
                        "LapNumber": int(p.get("lap", 0)),
                        "StopTime": duration,
                        "Team": "Unknown",
                    })
                df = pd.DataFrame(rows)
                df = df[df["StopTime"].between(1.5, 60)]
                team_map = get_team_map(session)
                df["Team"] = df["Driver"].map(team_map).fillna("Unknown")
                return df.reset_index(drop=True)
    except Exception:
        pass

    return pd.DataFrame(columns=["Driver", "LapNumber", "StopTime", "Team"])


# ── Lap cleaning ─────────────────────────────────────────────────────────────

def get_clean_laps(session) -> pd.DataFrame:
    """
    Return laps filtered for analysis:
    - IsAccurate == True
    - No in/out laps
    - No safety car laps
    - LapTime within 110% of session median
    """
    laps = session.laps.copy()
    laps = laps[laps["IsAccurate"] == True]
    laps = laps[laps["PitInTime"].isna() & laps["PitOutTime"].isna()]

    if "TrackStatus" in laps.columns:
        laps = laps[~laps["TrackStatus"].str.contains("4|5|6|7", na=False)]

    median_lap = laps["LapTime"].median()
    if pd.notna(median_lap):
        laps = laps[laps["LapTime"] < median_lap * 1.10]

    if "LapTime" in laps.columns:
        laps["LapTimeSec"] = laps["LapTime"].dt.total_seconds()

    return laps.reset_index(drop=True)


def fuel_correct(laps: pd.DataFrame, total_laps: int, correction_per_lap: float = 0.057) -> pd.DataFrame:
    laps = laps.copy()
    if "LapTimeSec" not in laps.columns:
        return laps
    laps["FuelCorrection"] = (total_laps - laps["LapNumber"]) * correction_per_lap
    laps["LapTimeCorr"] = laps["LapTimeSec"] - laps["FuelCorrection"]
    return laps


# ── Misc helpers ─────────────────────────────────────────────────────────────

def get_team_color(team_name: str) -> str:
    for key, color in TEAM_COLORS.items():
        if key.lower() in str(team_name).lower():
            return color
    return "#888888"


def format_laptime(seconds: float) -> str:
    if pd.isna(seconds) or seconds <= 0:
        return "—"
    m = int(seconds // 60)
    s = seconds % 60
    return f"{m}:{s:06.3f}"


def get_race_name_list(year: int) -> list:
    schedule = get_event_schedule(year)
    if schedule.empty:
        return []
    return schedule["EventName"].tolist()


@st.cache_data(ttl=86400, show_spinner=False)
def get_standings(year: int, round_number: int = None) -> tuple:
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
