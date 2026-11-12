"""Observed stint and session pace; these are not isolated tyre-wear models."""

import numpy as np
import pandas as pd

from f1lab.data import valid_laps

TREND_COLUMNS = ["Driver", "Stint", "Compound", "Green laps", "First lap", "Last lap",
                 "Pace change (s/tyre lap)"]
SUMMARY_COLUMNS = ["Driver", "Stint", "Compound", "Laps", "First lap", "Last lap",
                   "Tyre age min", "Tyre age max", "Best lap (s)", "Median lap (s)",
                   "Green laps", "Pace change (s/tyre lap)"]


def session_pace(session, drivers, phase="Whole session"):
    """Return valid laps with the fields needed for compound/stint/age views."""
    parts = []
    for driver in drivers:
        laps = valid_laps(session, driver, phase).copy()
        if laps.empty:
            continue
        laps["Driver"] = driver
        laps["LapSeconds"] = pd.to_timedelta(laps["LapTime"]).dt.total_seconds()
        start = laps["LapStartTime"] if "LapStartTime" in laps else laps.get("Time")
        laps["SessionMinutes"] = pd.to_timedelta(start, errors="coerce").dt.total_seconds() / 60
        for column in ("Compound", "Stint", "TyreLife", "TrackStatus"):
            if column not in laps:
                laps[column] = pd.NA
        parts.append(pd.DataFrame(laps))
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def stint_trends(laps):
    """Fit green-flag pace against tyre age only with >=3 usable, distinct ages.

    Positive slopes indicate slower observed pace. Fuel, traffic and track
    changes are not controlled, so neither sign should be presented as measured
    tyre wear.
    """
    required = {"Driver", "Stint", "Compound", "LapNumber", "TyreLife", "LapSeconds", "TrackStatus"}
    if laps.empty or not required.issubset(laps.columns):
        return pd.DataFrame(columns=TREND_COLUMNS)
    green = laps.loc[laps["TrackStatus"].astype(str).eq("1")].copy()
    rows = []
    for (driver, stint, compound), group in green.groupby(["Driver", "Stint", "Compound"], dropna=False):
        fit = group.dropna(subset=["TyreLife", "LapSeconds"])
        fit = fit.loc[np.isfinite(fit["TyreLife"]) & np.isfinite(fit["LapSeconds"])]
        slope = None
        if len(fit) >= 3 and fit["TyreLife"].nunique() >= 3:
            slope = float(np.polyfit(fit["TyreLife"], fit["LapSeconds"], 1)[0])
        rows.append({
            "Driver": driver, "Stint": int(stint) if pd.notna(stint) else stint,
            "Compound": compound, "Green laps": len(fit),
            "First lap": int(group["LapNumber"].min()),
            "Last lap": int(group["LapNumber"].max()),
            "Pace change (s/tyre lap)": slope,
        })
    return pd.DataFrame(rows, columns=TREND_COLUMNS)


def stint_summary(laps):
    """Per-stint description plus the optional green-flag pace slope."""
    if laps.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    trends = stint_trends(laps)
    rows = []
    for (driver, stint, compound), group in laps.groupby(["Driver", "Stint", "Compound"], dropna=False):
        green = group.loc[group["TrackStatus"].astype(str).eq("1")]
        match = trends.loc[(trends["Driver"] == driver)
                           & (trends["Stint"] == (int(stint) if pd.notna(stint) else stint))
                           & (trends["Compound"] == compound)]
        slope = match["Pace change (s/tyre lap)"].iloc[0] if not match.empty else None
        rows.append({
            "Driver": driver,
            "Stint": int(stint) if pd.notna(stint) else stint,
            "Compound": compound,
            "Laps": len(group),
            "First lap": int(group["LapNumber"].min()),
            "Last lap": int(group["LapNumber"].max()),
            "Tyre age min": float(group["TyreLife"].min()) if group["TyreLife"].notna().any() else None,
            "Tyre age max": float(group["TyreLife"].max()) if group["TyreLife"].notna().any() else None,
            "Best lap (s)": float(group["LapSeconds"].min()),
            "Median lap (s)": float(group["LapSeconds"].median()),
            "Green laps": len(green),
            "Pace change (s/tyre lap)": slope,
        })
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
