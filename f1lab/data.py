"""FastF1 access, cache configuration and auditable lap selection.

The public telemetry is sampled. A brake-on row is the first *recorded* sample
inside a distance window, not the exact instant the driver pressed the pedal.
"""

from pathlib import Path
from threading import RLock
import os

import fastf1
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIRECTORY = PROJECT_ROOT / "cache"
_LOCK = RLock()

AUDIT_COLUMNS = [
    "LapNumber", "LapTime", "LapSeconds", "Compound", "TyreLife", "Stint",
    "TrackStatus", "Included", "Reason",
]


def cache_directory() -> Path:
    """Return the FastF1 cache directory, overridable for CI or shared caches."""
    configured = os.environ.get("F1LAB_CACHE_DIR")
    path = Path(configured).expanduser() if configured else DEFAULT_CACHE_DIRECTORY
    return path.resolve()


def configure_cache() -> Path:
    path = cache_directory()
    path.mkdir(parents=True, exist_ok=True)
    fastf1.Cache.enable_cache(str(path))
    return path


def get_schedule(year):
    with _LOCK:
        configure_cache()
        schedule = fastf1.get_event_schedule(int(year), include_testing=False)
    if schedule.empty:
        raise ValueError("No events are available for that season.")
    return schedule


def load_session(year, event, session_name, telemetry=True):
    with _LOCK:
        configure_cache()
        session = fastf1.get_session(int(year), event, session_name)
        session.load(telemetry=telemetry, weather=False)
    if session.laps.empty:
        raise ValueError("This session has no lap timing data yet.")
    return session


def phase_laps(session, phase="All qualifying"):
    """Return the laps belonging to a qualifying phase, or the whole session."""
    if phase in ("Q1", "Q2", "Q3"):
        split = session.laps.split_qualifying_sessions()
        index = int(phase[-1]) - 1
        if index >= len(split) or split[index] is None or split[index].empty:
            return session.laps.iloc[0:0]
        return split[index]
    return session.laps


def lap_inclusion(session, driver, phase="All qualifying") -> pd.DataFrame:
    """Audit every lap for one driver and explain why it was included/excluded.

    Rules: a lap needs a positive recorded lap time, accurate timing, no
    deletion flag and no pit-in/pit-out timestamp. Unknown flags stay excluded
    rather than being silently treated as valid.
    """
    laps = phase_laps(session, phase).pick_drivers(driver).copy()
    if laps.empty:
        return pd.DataFrame(columns=AUDIT_COLUMNS)

    lap_time = pd.to_timedelta(laps["LapTime"], errors="coerce")
    seconds = lap_time.dt.total_seconds()

    reasons = pd.Series("", index=laps.index, dtype="object")
    missing = lap_time.isna()
    non_positive = (~missing) & (seconds <= 0)
    pit = pd.Series(False, index=laps.index)
    for column in ("PitInTime", "PitOutTime"):
        if column in laps:
            pit |= laps[column].notna()
    deleted = (laps["Deleted"].fillna(False).astype(bool)
               if "Deleted" in laps else pd.Series(False, index=laps.index))
    inaccurate = (~laps["IsAccurate"].eq(True)
                  if "IsAccurate" in laps else pd.Series(False, index=laps.index))

    reasons = reasons.mask(missing, "No recorded lap time")
    reasons = reasons.mask(non_positive, "Non-positive lap time")
    reasons = reasons.mask(reasons.eq("") & pit, "Pit in/out lap")
    reasons = reasons.mask(reasons.eq("") & deleted, "Deleted lap")
    reasons = reasons.mask(reasons.eq("") & inaccurate, "Inaccurate timing")
    included = reasons.eq("")

    audit = pd.DataFrame({
        "LapNumber": pd.to_numeric(laps["LapNumber"], errors="coerce"),
        "LapTime": lap_time,
        "LapSeconds": seconds,
        "Compound": laps.get("Compound", pd.Series(index=laps.index, dtype="object")),
        "TyreLife": pd.to_numeric(laps.get("TyreLife", pd.Series(index=laps.index)), errors="coerce"),
        "Stint": pd.to_numeric(laps.get("Stint", pd.Series(index=laps.index)), errors="coerce"),
        "TrackStatus": laps.get("TrackStatus", pd.Series(index=laps.index, dtype="object")).astype("string"),
        "Included": included,
        "Reason": reasons.mask(included, "Included"),
    }, index=laps.index)
    return audit.sort_values("LapNumber")[AUDIT_COLUMNS]


def valid_laps(session, driver, phase="All qualifying"):
    """Completed, accurate laps, excluding deleted laps and pit in/out laps."""
    audit = lap_inclusion(session, driver, phase)
    if audit.empty:
        return phase_laps(session, phase).iloc[0:0]
    keep = audit.loc[audit["Included"], "LapNumber"]
    laps = phase_laps(session, phase).pick_drivers(driver)
    laps = laps.loc[laps["LapNumber"].isin(keep)]
    return laps.sort_values("LapNumber")


def choose_lap(laps, lap_number=None):
    """Pick the fastest valid lap, or a specific lap number from a valid set."""
    if laps.empty:
        raise ValueError("No valid laps are available for this selection.")
    if lap_number is None:
        return laps.pick_fastest(only_by_time=True)
    selected = laps.loc[laps["LapNumber"] == lap_number]
    if selected.empty:
        raise ValueError("The selected lap is unavailable.")
    return selected.iloc[0]


def lap_telemetry(lap):
    """Load sampled car telemetry with an estimated distance channel."""
    with _LOCK:
        telemetry = lap.get_car_data().add_distance().copy()
    required = {"Distance", "Speed", "Throttle", "Brake"}
    if not required.issubset(telemetry.columns):
        raise ValueError("This lap does not have all four required telemetry channels.")
    telemetry = telemetry.dropna(subset=["Distance", "Speed"]).sort_values("Distance")
    if len(telemetry) < 2:
        raise ValueError("There are too few telemetry samples for this lap.")
    return telemetry


def lap_seconds(lap) -> float:
    return float(pd.to_timedelta(lap["LapTime"]).total_seconds())
