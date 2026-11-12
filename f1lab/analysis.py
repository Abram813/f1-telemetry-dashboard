"""Small, testable calculations shared by the dashboard and verification script.

Distances are estimates from sampled public telemetry. A brake-on sample is
not an exact pedal-application position, and an empty selection is not zero.
"""

from dataclasses import dataclass
import math

import pandas as pd


@dataclass(frozen=True)
class SectionSummary:
    samples: int
    minimum_speed: float | None
    maximum_speed: float | None
    brake_distance: float | None
    brake_speed: float | None
    previous_distance: float | None
    brake_status: str


STATUS_LABELS = {
    "observed_onset": "Off → On observed in section",
    "active_at_start": "Already On at first section sample",
    "unknown_previous_sample": "Previous brake state unknown",
    "no_braking": "No brake-on samples",
    "no_samples": "No telemetry samples in range",
    "missing_brake_data": "Brake data incomplete or unavailable",
}


def validate_window(start: float, end: float) -> None:
    if not (math.isfinite(start) and math.isfinite(end)) or start >= end:
        raise ValueError("Choose a finite start distance smaller than the end distance.")


def select_section(telemetry: pd.DataFrame, start: float, end: float) -> pd.DataFrame:
    validate_window(start, end)
    if "Distance" not in telemetry:
        raise ValueError("Telemetry has no distance channel.")
    return telemetry.loc[telemetry["Distance"].between(start, end)].copy()


def first_braking_sample(telemetry, start_distance, end_distance):
    """Return the first brake-on row inside a range, or None (original lesson)."""
    section = select_section(telemetry, start_distance, end_distance)
    if "Brake" not in section:
        return None
    braking = section.loc[section["Brake"].eq(True).fillna(False)]
    return None if braking.empty else braking.iloc[0]


def summarize_section(telemetry: pd.DataFrame, start: float, end: float) -> SectionSummary:
    """Summarize a range, preserving unknowns and boundary uncertainty."""
    section = select_section(telemetry, start, end).sort_values("Distance", kind="stable")
    speeds = pd.to_numeric(section.get("Speed", pd.Series(dtype=float)), errors="coerce").dropna()
    minimum = float(speeds.min()) if not speeds.empty else None
    maximum = float(speeds.max()) if not speeds.empty else None
    base = dict(samples=len(section), minimum_speed=minimum, maximum_speed=maximum)

    def without_braking(status):
        return SectionSummary(**base, brake_distance=None, brake_speed=None,
                              previous_distance=None, brake_status=status)

    if section.empty:
        return without_braking("no_samples")
    if "Brake" not in section or section["Brake"].isna().all():
        return without_braking("missing_brake_data")

    brake_on = section["Brake"].eq(True).fillna(False).to_numpy()
    positions = brake_on.nonzero()[0]
    if len(positions) == 0:
        status = "missing_brake_data" if section["Brake"].isna().any() else "no_braking"
        return without_braking(status)

    position = int(positions[0])
    sample = section.iloc[position]
    previous_distance = None
    if position == 0:
        status = "active_at_start"
    elif pd.isna(section.iloc[position - 1]["Brake"]):
        status = "unknown_previous_sample"
    else:
        status = "observed_onset"
        previous_distance = float(section.iloc[position - 1]["Distance"])

    speed = sample.get("Speed")
    return SectionSummary(
        **base, brake_distance=float(sample["Distance"]),
        brake_speed=float(speed) if pd.notna(speed) else None,
        previous_distance=previous_distance, brake_status=status,
    )


def braking_difference(first: SectionSummary, second: SectionSummary) -> float | None:
    """B minus A, only when both ranges contain observed off-to-on transitions."""
    if first.brake_status != "observed_onset" or second.brake_status != "observed_onset":
        return None
    return second.brake_distance - first.brake_distance


def format_lap_time(seconds: float) -> str:
    if not math.isfinite(seconds) or seconds < 0:
        return "Unavailable"
    milliseconds = round(seconds * 1000)
    minutes, remainder = divmod(milliseconds, 60000)
    whole_seconds, fraction = divmod(remainder, 1000)
    return f"{minutes}:{whole_seconds:02d}.{fraction:03d}"


def format_section_value(value, unit="", digits=1) -> str:
    if value is None or not math.isfinite(value):
        return "Unavailable"
    return f"{value:.{digits}f}{unit}"
