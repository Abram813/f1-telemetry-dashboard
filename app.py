"""Run with: uv run streamlit run app.py"""

from datetime import date
import math

import pandas as pd
import streamlit as st

from f1lab.analysis import (
    STATUS_LABELS, braking_difference, format_lap_time, format_section_value,
    select_section, summarize_section,
)
from f1lab.charts import pace_chart, stint_sequence_chart, telemetry_chart
from f1lab.data import (
    cache_directory, choose_lap, get_schedule, lap_inclusion, lap_seconds,
    lap_telemetry, load_session, valid_laps,
)
from f1lab.pace import session_pace, stint_summary, stint_trends

st.set_page_config(page_title="F1 Telemetry Dashboard", page_icon="🏁", layout="wide")
st.markdown("""
<style>
 .block-container {max-width:1450px;padding-top:4.5rem;padding-bottom:3rem;}
 h1 {letter-spacing:-.04em !important;}
 [data-testid="stMetric"] {background:white;border:1px solid #e3e8ef;
   border-radius:12px;padding:16px 20px;}
 [data-testid="stMetricValue"] {font-variant-numeric:tabular-nums;}
 .eyebrow {color:#b34b24;font-size:12px;letter-spacing:.15em;font-weight:700;}
 [data-testid="stSidebar"] {border-right:1px solid #e3e8ef;}
</style>
""", unsafe_allow_html=True)


@st.cache_data(ttl=3600, show_spinner=False)
def cached_schedule(year):
    return get_schedule(year)


@st.cache_resource(ttl=3600, max_entries=4, show_spinner=False)
def cached_session(year, event, session_name):
    return load_session(year, event, session_name)


def show_load_error(message, error):
    st.error(message)
    st.caption("A first download needs internet access. Some sessions or telemetry may be unavailable.")
    with st.expander("Error details"):
        st.code(str(error))
    if st.button("Retry loading", key="retry"):
        cached_schedule.clear()
        cached_session.clear()
        st.rerun()
    st.stop()


def lap_description(lap):
    compound = lap.get("Compound", "Unknown compound")
    age = lap.get("TyreLife")
    stint = lap.get("Stint")
    tyre = f" · tyre age {int(age)} laps" if pd.notna(age) else ""
    run = f" · stint {int(stint)}" if pd.notna(stint) else ""
    return f"Lap {int(lap['LapNumber'])} · {compound}{tyre}{run}"


def included_numbers(audit):
    return ", ".join(str(int(number)) for number in audit.loc[audit["Included"], "LapNumber"])


def excluded_summary(audit):
    excluded = audit.loc[~audit["Included"]]
    if excluded.empty:
        return "None"
    return "; ".join(
        f"lap {int(row.LapNumber)} ({row.Reason})"
        for row in excluded.itertuples()
    )


st.sidebar.markdown("## 🏁 F1 Telemetry Dashboard")
st.sidebar.caption("A pit-wall view of real historical laps: speed, throttle, braking, lap timing and race stint pace.")
seasons = list(range(max(2021, date.today().year), 2017, -1))
year = st.sidebar.selectbox("Season", seasons, index=seasons.index(2021), key="year")
try:
    with st.spinner("Finding events…"):
        schedule = cached_schedule(year)
except Exception as exc:
    show_load_error("Could not load the season schedule.", exc)
events = schedule["EventName"].tolist()
event = st.sidebar.selectbox(
    "Grand Prix", events,
    index=events.index("British Grand Prix") if "British Grand Prix" in events else 0,
    key=f"event_{year}",
)
event_row = schedule.loc[schedule["EventName"] == event].iloc[0]
sessions = [event_row[f"Session{i}"] for i in range(1, 6)
            if pd.notna(event_row.get(f"Session{i}")) and event_row.get(f"Session{i}")]
if not sessions:
    st.sidebar.error("This event has no sessions in the schedule.")
    st.stop()
session_name = st.sidebar.selectbox(
    "Session", sessions,
    index=sessions.index("Qualifying") if "Qualifying" in sessions else 0,
    key=f"session_{year}_{event}",
)
requested = (year, event, session_name)
load_clicked = st.sidebar.button("Load session", type="primary", width="stretch")
if "loaded_spec" not in st.session_state or load_clicked:
    st.session_state.loaded_spec = requested
if requested != st.session_state.loaded_spec:
    st.sidebar.info("Press Load session to apply this selection.")
st.sidebar.divider()
st.sidebar.caption("Historical data via FastF1. The first load can take a few minutes; later views use the local cache.")
st.sidebar.caption(f"Cache: {cache_directory()}")

spec = st.session_state.loaded_spec
try:
    with st.spinner("Loading lap timing and telemetry…"):
        session = cached_session(*spec)
except Exception as exc:
    show_load_error("Could not load this session.", exc)

st.markdown('<div class="eyebrow">F1 TELEMETRY DASHBOARD / PIT WALL</div>', unsafe_allow_html=True)
st.title(f"{spec[1]} · {spec[0]}")
st.caption(f"{session.name} · Compare two valid laps, inspect a linked telemetry section, and read race stint pace.")

qualifying = session.name in ("Qualifying", "Sprint Qualifying", "Sprint Shootout")
phase = st.radio(
    "Qualifying phase", ["All qualifying", "Q1", "Q2", "Q3"], horizontal=True,
    key=f"phase_{spec}",
) if qualifying else "Whole session"

try:
    laps_by_driver = {
        code: valid_laps(session, code, phase)
        for code in sorted(session.laps["Driver"].dropna().unique())
    }
except (ValueError, IndexError) as exc:
    st.info(f"Lap data for this phase is unavailable: {exc}")
    st.stop()
drivers = [code for code, laps in laps_by_driver.items() if not laps.empty]
if len(drivers) < 2:
    st.info("Fewer than two drivers have valid laps in this selection. Choose another phase or session.")
    st.stop()

names = {}
for _, result in session.results.iterrows():
    code, full_name = result.get("Abbreviation"), result.get("FullName")
    if pd.notna(code) and pd.notna(full_name):
        names[code] = f"{full_name} ({code})"


def choose_driver_lap(column, side, available, preferred):
    with column:
        driver = st.selectbox(
            f"Driver {side}", available,
            index=available.index(preferred) if preferred in available else 0,
            format_func=lambda code: names.get(code, code),
            key=f"driver_{side}_{spec}_{phase}",
        )
        laps = laps_by_driver[driver]
        options = [None] + [int(number) for number in laps["LapNumber"]]

        def label(number):
            if number is None:
                fastest = choose_lap(laps)
                return f"Fastest valid lap · {format_lap_time(lap_seconds(fastest))}"
            lap = laps.loc[laps["LapNumber"] == number].iloc[0]
            return f"Lap {number} · {format_lap_time(lap_seconds(lap))} · {lap['Compound']}"

        number = st.selectbox(
            f"Lap {side}", options, format_func=label,
            key=f"lap_{side}_{spec}_{phase}_{driver}",
            help="The first option is the fastest valid lap in the selected phase.",
        )
        lap = choose_lap(laps, number)
        st.caption(lap_description(lap))
        return driver, lap, number


left, right = st.columns(2, gap="large")
driver_a, lap_a, number_a = choose_driver_lap(left, "A", drivers, "VER")
driver_b, lap_b, number_b = choose_driver_lap(
    right, "B", [code for code in drivers if code != driver_a], "HAM",
)
selected_drivers = [driver_a, driver_b]
laps = [lap_a, lap_b]
times = [lap_seconds(lap) for lap in laps]
first, second, third = st.columns(3)
first.metric(f"{driver_a} · lap {int(lap_a['LapNumber'])}", format_lap_time(times[0]))
second.metric(f"{driver_b} · lap {int(lap_b['LapNumber'])}", format_lap_time(times[1]))
gap = times[1] - times[0]
if gap == 0:
    third.metric("Official lap-time difference", "0.000 s", delta="Equal lap times", delta_color="off")
else:
    winner = driver_a if gap > 0 else driver_b
    third.metric("Faster official lap", winner, delta=f"{abs(gap):.3f} s", delta_color="off")
    st.caption(f"Official timing: {winner} was faster by {abs(gap):.3f} s. "
               "The section measurements below are separate from the full-lap gap.")
if qualifying and phase == "All qualifying":
    st.caption("All qualifying can compare laps from different phases. Select Q1, Q2 or Q3 for a closer comparison.")

is_original = (
    spec == (2021, "British Grand Prix", "Qualifying")
    and phase == "All qualifying"
    and {driver_a, driver_b} == {"VER", "HAM"}
    and number_a is None and number_b is None
)
if is_original:
    st.success(
        "Original exercise loaded: 2021 British GP qualifying, VER and HAM, fastest valid laps. "
        "Set the section to 3,700–4,200 m to reproduce the braking comparison."
    )

telemetry_tab, pace_tab, method_tab = st.tabs(["Telemetry", "Race pace", "Data & method"])
with telemetry_tab:
    try:
        telemetry = [lap_telemetry(lap) for lap in laps]
    except Exception as exc:
        st.warning(f"Telemetry is unavailable for the selected lap: {exc}")
        telemetry = None
    if telemetry is not None:
        lower = max(0, math.ceil(max(data["Distance"].min() for data in telemetry)))
        upper = math.floor(min(data["Distance"].max() for data in telemetry))
        if lower >= upper:
            st.warning("These laps do not have an overlapping distance range.")
        else:
            window_key = (f"window_{spec}_{phase}_{driver_a}_{int(lap_a['LapNumber'])}"
                          f"_{driver_b}_{int(lap_b['LapNumber'])}")
            from_key, to_key = f"{window_key}_from", f"{window_key}_to"
            if window_key not in st.session_state:
                st.session_state[window_key] = (lower, upper)
                st.session_state[from_key], st.session_state[to_key] = lower, upper

            def sync_slider():
                st.session_state[from_key], st.session_state[to_key] = st.session_state[window_key]

            def sync_fields():
                first_value, last_value = st.session_state[from_key], st.session_state[to_key]
                if first_value <= last_value:
                    st.session_state[window_key] = (first_value, last_value)

            if is_original and st.button(
                "Use the 3,700–4,200 m section from the original exercise",
                key=f"use_demo_{window_key}",
            ):
                st.session_state[window_key] = (3700, 4200)
                st.session_state[from_key], st.session_state[to_key] = 3700, 4200
                st.rerun()

            st.slider(
                "Distance window (metres)", lower, upper, step=1, key=window_key,
                on_change=sync_slider,
                help="This range controls the chart shading, the measurements and the exported section.",
            )
            from_column, to_column = st.columns(2)
            start = from_column.number_input(
                "From (m)", lower, upper, step=1, key=from_key, on_change=sync_fields,
            )
            end = to_column.number_input(
                "To (m)", lower, upper, step=1, key=to_key, on_change=sync_fields,
            )
            if start >= end:
                st.warning("Choose an end distance greater than the start distance.")
            else:
                title = f"{spec[0]} {spec[1]} · {session.name} · {phase}"
                labels = [f"{driver} · lap {int(lap['LapNumber'])}"
                          for driver, lap in zip(selected_drivers, laps)]
                summaries = [summarize_section(data, start, end) for data in telemetry]
                figure = telemetry_chart(telemetry, labels, start, end, title, summaries)
                st.plotly_chart(
                    figure, width="stretch", theme=None, key="telemetry_chart",
                    config={"displaylogo": False, "scrollZoom": True},
                    alt="Speed, throttle percentage and brake on/off by distance for two selected laps.",
                )
                st.caption("Drag or scroll to zoom. All three panels share one distance axis, so they show the "
                           "same section; double-click to reset. The slider and numeric bounds define the measured "
                           "and exported section.")

                st.markdown("#### Section measurements")
                rows = [{
                    "Driver": driver,
                    "Samples": summary.samples,
                    "Lowest speed (km/h)": summary.minimum_speed,
                    "First brake-on sample (m)": summary.brake_distance,
                    "Speed at first brake-on (km/h)": summary.brake_speed,
                    "Previous Off sample (m)": summary.previous_distance,
                    "Braking observation": STATUS_LABELS[summary.brake_status],
                } for driver, summary in zip(selected_drivers, summaries)]
                st.dataframe(pd.DataFrame(rows).round(1), hide_index=True, width="stretch")

                speed_columns = st.columns(2)
                for column, driver, summary in zip(speed_columns, selected_drivers, summaries):
                    column.metric(
                        f"{driver} · minimum speed in section",
                        format_section_value(summary.minimum_speed, " km/h"),
                    )

                for driver, summary in zip(selected_drivers, summaries):
                    if summary.brake_status == "active_at_start":
                        st.warning(
                            f"{driver} is already braking at the first sample inside "
                            f"{start:,.0f}–{end:,.0f} m. That first On sample is not a new "
                            "braking onset, so the dashboard cannot show where this braking began."
                        )
                    elif summary.brake_status == "unknown_previous_sample":
                        st.info(
                            f"{driver}'s previous brake sample is unknown, so the first On sample "
                            "cannot be confirmed as an Off → On transition."
                        )

                difference = braking_difference(*summaries)
                if difference is not None:
                    st.info(
                        f"First recorded brake-on sample difference ({driver_b} − {driver_a}): "
                        f"{difference:+.1f} m. Positive means {driver_b}'s recorded sample is farther "
                        "into the lap. This compares samples, not exact pedal-application instants."
                    )
                else:
                    st.caption(
                        "An onset difference is shown only when both traces include an observed "
                        "Off → On transition inside the section."
                    )
                st.caption(
                    "Distance is estimated from public telemetry. Braking is a boolean On/Off channel, "
                    "not brake pressure; the true pedal application lies between samples."
                )

                download_a, download_b = st.columns(2)
                csv_parts = []
                for data, driver, lap, seconds, summary in zip(
                    telemetry, selected_drivers, laps, times, summaries,
                ):
                    section = select_section(data, start, end)
                    section.insert(0, "Driver", driver)
                    section.insert(1, "LapNumber", int(lap["LapNumber"]))
                    section.insert(2, "LapTimeSeconds", seconds)
                    section.insert(3, "Year", spec[0])
                    section.insert(4, "Event", spec[1])
                    section.insert(5, "Session", spec[2])
                    section.insert(6, "Phase", phase)
                    section.insert(7, "SectionStart", start)
                    section.insert(8, "SectionEnd", end)
                    section.insert(9, "BrakingObservation", summary.brake_status)
                    csv_parts.append(section)
                stem = (f"{spec[0]}_{spec[1].replace(' ', '_')}_{driver_a}_{driver_b}"
                        f"_{start}-{end}m")
                download_a.download_button(
                    "Download selected samples · CSV",
                    pd.concat(csv_parts, ignore_index=True).to_csv(index=False).encode("utf-8"),
                    file_name=f"{stem}.csv", mime="text/csv", width="stretch",
                )
                download_b.download_button(
                    "Download interactive chart · HTML",
                    figure.to_html(full_html=True, include_plotlyjs=True).encode("utf-8"),
                    file_name=f"{stem}.html", mime="text/html", width="stretch",
                )

with pace_tab:
    race_session = session.name in ("Race", "Sprint")
    st.markdown("#### Race pace by compound, stint and tyre age")
    if not race_session:
        st.info("This view is available for Race and Sprint sessions. Load a race to inspect stint pace, "
                "tyre age and green-flag pace trends.")
    else:
        pace = session_pace(session, selected_drivers)
        if pace.empty:
            st.info("No valid laps are available for race pace analysis.")
        else:
            st.plotly_chart(
                pace_chart(pace, selected_drivers, "Observed lap time by tyre age"),
                theme=None, width="stretch",
            )
            st.caption("Each line is a stint; colour is the tyre compound; the x axis is tyre age. "
                       "Hover shows the lap number, compound, stint and track status. Only valid laps are plotted.")
            st.plotly_chart(
                stint_sequence_chart(pace, selected_drivers, "Stint sequence by lap number"),
                theme=None, width="stretch",
            )
            st.caption("The lap-number view keeps the stint order visible. The tyre-age view above is the one "
                       "to use when comparing pace at the same point in a tyre's life.")

            summary = stint_summary(pace)
            trends = stint_trends(pace)
            st.markdown("#### Stint summary")
            st.dataframe(summary.round(3), hide_index=True, width="stretch")
            st.download_button(
                "Download stint summary · CSV", summary.to_csv(index=False),
                file_name="stint_summary.csv", mime="text/csv",
            )

            st.markdown("#### Green-flag pace change with tyre age")
            st.caption("Positive values mean slower observed pace as the tyres age. A slope is shown only "
                       "for at least three green-flag laps with distinct tyre ages. This is observed pace, "
                       "not measured tyre wear; fuel, traffic and track conditions are not controlled.")
            if trends.empty:
                st.info("There are not enough supported green-flag stint data to estimate trends.")
            else:
                st.dataframe(trends.round(3), hide_index=True, width="stretch")

            st.markdown("#### Which laps are included in this pace view")
            st.markdown(
                "**Included:** completed laps with a positive recorded time, accurate timing, no deletion "
                "flag and no pit-in or pit-out timestamp. **Excluded:** laps failing any of those rules. "
                "The trend fit uses only green-flag laps (track status `1`) and needs at least three "
                "distinct tyre ages."
            )
            audit_frames = []
            for driver in selected_drivers:
                audit = lap_inclusion(session, driver, "Whole session")
                audit_frames.append(audit.assign(Driver=driver))
                st.markdown(f"**{driver}** — included laps: {included_numbers(audit) or 'none'}")
                st.caption(f"Excluded: {excluded_summary(audit)}")
            audit_table = pd.concat(audit_frames, ignore_index=True)
            with st.expander("Open the complete lap-inclusion audit"):
                display = audit_table.copy()
                display["LapTime"] = display["LapTime"].astype(str).replace("NaT", "Unavailable")
                st.dataframe(display, hide_index=True, width="stretch")
            st.caption("A pace trend describes these included laps only. It is not a causal estimate of "
                       "tyre degradation or a prediction of future stint pace.")

with method_tab:
    st.markdown("""
#### What the data supports

- **Official lap times** come from FastF1's timing data. The whole-lap gap uses those recorded times; the
  telemetry section is a separate measurement and does not by itself quantify time gained.
- **Valid lap rule:** completed, positive recorded lap time, accurate timing, no deletion flag and no
  pit-in/pit-out timestamp. The fastest option is the fastest remaining lap in the selected phase.
- **Telemetry is sampled.** Distance is estimated by FastF1 from speed and time. A first brake-on sample is
  the first *recorded* On row in the section, not the exact instant the pedal was pressed. Braking is a
  boolean signal, not brake pressure.
- **Already braking at the section start** is reported as a condition, not treated as a new onset. A
  difference is shown only when both drivers have an observed Off → On transition in the section.
- **Race pace** groups valid laps by compound, stint and tyre age. The green-flag slope is an observed pace
  change, not measured tyre wear; fuel burn, traffic, weather and strategy remain confounders.
- **Exports** contain only the sampled telemetry rows inside the selected distance window, or a standalone
  HTML copy of the interactive chart.

#### Reproduce the original 2021 British GP exercise

1. Load **2021 → British Grand Prix → Qualifying**.
2. Keep **All qualifying**, **VER**, **HAM**, and each driver's fastest valid lap.
3. Set the section to **3,700–4,200 m**.

Hamilton's selected lap is **1:26.023** and Verstappen's is **1:26.209**. Hamilton's first recorded
brake-on sample is about **3,916.4 m**; Verstappen's is about **3,905.3 m**, so Hamilton's sample is
about **11.1 m farther** into the lap. Those are sampled positions, not exact pedal-application points.
The included `scripts/verify_exercise.py` calculates and asserts these values from the data.
""")
