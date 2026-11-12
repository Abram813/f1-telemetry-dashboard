"""Optional real-data acceptance checks using Streamlit's AppTest.

Run from the repository root:
    uv run python tests/integration_smoke.py

Requires internet on the first run (or a populated FastF1 cache). The offline
unit suite is separate and deliberately blocks external requests.
"""

from pathlib import Path

import streamlit as st
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[1] / "app.py"


def check_clean(app):
    assert not app.exception, [item.message for item in app.exception]
    assert not app.error, [item.value for item in app.error]


def choice(app, label):
    return next(item for item in app.selectbox if item.label == label)


def dataframe_with(app, column):
    for frame in app.dataframe:
        if column in frame.value.columns:
            return frame.value
    raise AssertionError(f"No dataframe with column {column!r}: "
                         f"{[list(frame.value.columns) for frame in app.dataframe]}")


def main():
    app = AppTest.from_file(str(APP), default_timeout=240).run()
    check_clean(app)
    assert [item.value for item in app.metric][:2] == ["1:26.209", "1:26.023"]
    assert any("Original exercise loaded" in item.value for item in app.success)

    app.number_input[0].set_value(3700).run()
    app.number_input[1].set_value(4200).run()
    check_clean(app)
    assert app.slider[0].value == (3700, 4200)
    assert any("+11.1 m" in item.value for item in app.info)

    section = dataframe_with(app, "Braking observation")
    assert set(section["Braking observation"]) == {"Off → On observed in section"}
    assert sorted(section["Lowest speed (km/h)"].tolist()) == [216.0, 225.0]
    assert sorted(section["First brake-on sample (m)"].round(1).tolist()) == [3905.3, 3916.4]
    labels = {item.label for item in app.get("download_button")}
    assert "Download selected samples · CSV" in labels
    assert "Download interactive chart · HTML" in labels

    app.number_input[0].set_value(3916).run()
    app.number_input[1].set_value(3920).run()
    check_clean(app)
    assert any("already braking" in item.value for item in app.warning)
    assert not any("+11.1 m" in item.value for item in app.info)

    app.slider[0].set_value((2500, 3000)).run()
    check_clean(app)
    assert [item.value for item in app.number_input] == [2500, 3000]
    section = dataframe_with(app, "Braking observation")
    assert set(section["Braking observation"]) == {"No brake-on samples"}

    app.slider[0].set_value((3900, 3900)).run()
    check_clean(app)
    assert any("end distance greater" in item.value for item in app.warning)

    app.radio[0].set_value("Q3").run()
    check_clean(app)
    assert app.metric[1].value == "1:26.134"
    print("PASS: original demo, linked section controls, no-braking range, invalid range, Q3")

    choice(app, "Grand Prix").set_value("Spanish Grand Prix").run()
    choice(app, "Session").set_value("Race").run()
    next(item for item in app.button if item.label == "Load session").click().run()
    check_clean(app)

    stint = dataframe_with(app, "Pace change (s/tyre lap)")
    assert not stint.empty
    assert stint["Pace change (s/tyre lap)"].notna().any()
    summary = dataframe_with(app, "Tyre age min")
    assert set(summary["Compound"]).issubset({"SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"})
    audit = dataframe_with(app, "Reason")
    assert {"Included", "Reason", "LapNumber"}.issubset(audit.columns)
    print("PASS: race session, compound/stint/tyre-age pace, green-flag trend, lap-inclusion audit")


if __name__ == "__main__":
    main()
