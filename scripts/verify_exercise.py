"""Verify the original 2021 British GP qualifying exercise from real data.

Run from the repository root:
    uv run python scripts/verify_exercise.py

The values are calculated, not hard-coded into the dashboard. This script
asserts the published lap times and the sampled braking-position difference.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from f1lab.analysis import braking_difference, summarize_section  # noqa: E402
from f1lab.data import choose_lap, lap_seconds, lap_telemetry, load_session, valid_laps  # noqa: E402

EXPECTED = {
    "HAM": {"lap_seconds": 86.023, "brake_distance": 3916.4},
    "VER": {"lap_seconds": 86.209, "brake_distance": 3905.3},
}
START, END = 3700, 4200


def main():
    session = load_session(2021, "British Grand Prix", "Qualifying")
    results = {}
    for driver in ("VER", "HAM"):
        laps = valid_laps(session, driver, "All qualifying")
        lap = choose_lap(laps)
        telemetry = lap_telemetry(lap)
        summary = summarize_section(telemetry, START, END)
        seconds = lap_seconds(lap)
        results[driver] = (seconds, summary)
        print(f"{driver}: lap {int(lap['LapNumber'])}, {seconds:.3f} s, "
              f"first recorded brake-on sample {summary.brake_distance:.1f} m, "
              f"minimum speed {summary.minimum_speed:.1f} km/h, "
              f"status {summary.brake_status}")
        expected = EXPECTED[driver]
        assert abs(seconds - expected["lap_seconds"]) < 0.001, (driver, seconds)
        assert abs(summary.brake_distance - expected["brake_distance"]) < 0.1, (
            driver, summary.brake_distance,
        )
        assert summary.brake_status == "observed_onset", (driver, summary.brake_status)

    difference = braking_difference(results["VER"][1], results["HAM"][1])
    print(f"HAM - VER first brake-on sample difference: {difference:+.3f} m")
    assert difference is not None
    assert 11.0 <= difference <= 11.2, difference
    print("PASS: 2021 British GP qualifying exercise reproduced from FastF1 data.")


if __name__ == "__main__":
    main()
