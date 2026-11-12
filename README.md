# F1 Telemetry Dashboard

A pit-wall dashboard for real historical Formula 1 laps. Select a season, Grand Prix, session, two drivers and a lap for each driver; compare speed, throttle and brake against distance; inspect a corner section; and read race stint pace by compound, stint and tyre age.

Built with [FastF1](https://github.com/theOehrly/Fast-F1). The public telemetry is sampled, so the dashboard separates a **recorded brake-on sample** from the exact instant a driver pressed the pedal.

Repository: <https://github.com/Abram813/f1-telemetry-dashboard>

[![fresh-clone-ci](https://github.com/Abram813/f1-telemetry-dashboard/actions/workflows/ci.yml/badge.svg)](https://github.com/Abram813/f1-telemetry-dashboard/actions/workflows/ci.yml)

## What the dashboard shows

- Season, Grand Prix, session, qualifying phase, two drivers and one lap per driver.
- A **fastest valid lap** shortcut for each driver, plus individual valid laps.
- Official lap times, the faster driver and the whole-lap time difference.
- Three linked charts: speed in km/h, throttle percentage and brake On/Off against distance in metres.
- A distance slider and numeric bounds. The same section drives the chart shading, the measurements and the CSV export. Zooming or panning any chart keeps all three panels on the same distance range.
- Each driver's minimum speed in the selected section.
- The first recorded brake-on sample in the section, the previous Off sample and the observed condition.
- An explicit **already braking at the start of the section** state. It is not treated as a new braking onset.
- CSV export of the selected samples and a standalone interactive HTML chart.
- For Race and Sprint sessions: lap pace by tyre compound, stint and tyre age, plus a lap-sequence view and green-flag pace-change table.
- A complete lap-inclusion audit explaining which laps were included and why other laps were excluded.

## Quick start

Requires Python 3.14 and [uv](https://docs.astral.sh/uv/). From the repository folder, run these exact commands:

```bash
uv venv --python 3.14
uv pip install -r requirements.txt
uv run streamlit run app.py
```

Open <http://127.0.0.1:8501>. The first load needs internet access and can take a few minutes while FastF1 downloads the session. Later loads use `cache/`.

The launch command works from a folder whose path contains spaces; the app and CI tests are exercised that way.

## The built-in demo

The app opens on **2021 → British Grand Prix → Qualifying**, **All qualifying**, **VER** and **HAM**, each on the fastest valid lap.

Click **Use the 3,700–4,200 m section from the original exercise** (or set **From** to `3700` and **To** to `4200`) to reproduce the original comparison:

| Measurement | Hamilton | Verstappen |
|---|---:|---:|
| Official lap time | 1:26.023 | 1:26.209 |
| Minimum speed in 3,700–4,200 m | 216.0 km/h | 225.0 km/h |
| First recorded brake-on sample | ≈3,916.4 m | ≈3,905.3 m |

Hamilton's recorded brake-on sample is about **11.1 m farther** into the lap. That is a difference between sampled telemetry rows, not a measurement of the exact pedal-application instant. The app reports the signed difference as `HAM − VER = +11.1 m`.

Run the same calculation outside the UI:

```bash
uv run python scripts/verify_exercise.py
```

## How laps and braking are handled

A valid lap has a positive recorded lap time, accurate timing, no deletion flag and no pit-in/pit-out timestamp. The fastest option is the fastest remaining lap in the chosen qualifying phase. The Race pace tab prints the included lap numbers and an audit table with an exclusion reason for every other lap.

Braking is a boolean On/Off channel. The first brake-on sample is the first sampled On row inside the section. If the section begins while the trace is already On, the dashboard reports **Already On at first section sample** and does not compare it as a new onset. A braking-position difference is shown only when both drivers have an observed Off → On transition in the section.

Race pace is an **observed** view. The green-flag slope needs at least three laps with distinct tyre ages; fuel burn, traffic, weather, strategy and track conditions are not controlled. It is not measured tyre wear or a causal degradation estimate.

## Tests

Offline unit tests, with external data and model requests blocked:

```bash
uv run python tests/run_offline.py
```

Real-data checks, using FastF1 (internet or a populated cache required):

```bash
uv run python scripts/verify_exercise.py
uv run python tests/integration_smoke.py
```

The full CI smoke test starts the exact README command, waits for Streamlit's health endpoint, runs the AppTest acceptance checks, and confirms a clean shutdown:

```bash
uv run python tests/ci_smoke.py
```

## Continuous integration

`.github/workflows/ci.yml` runs a fresh clone into a path containing spaces on Windows and macOS. It records the OS, CPU architecture, Python version and uv version, runs the offline tests with network access blocked, reproduces the 2021 British GP exercise from real data, and starts the app for the acceptance action and clean-shutdown check.

The workflow matrix is:

- `windows-latest` — Windows x64
- `macos-15` — macOS arm64 (Apple Silicon)
- `macos-15-intel` — macOS x86_64 (Intel)

**Mac architectures verified: `arm64` and `x86_64`.** Both ran the full fresh-clone workflow.

## Actual test results

Final GitHub Actions run: <https://github.com/Abram813/f1-telemetry-dashboard/actions/runs/43282091657> (commit `458268a`). The local run used a fresh clone at a path containing spaces: `/private/var/folders/.../opencode/F1 Telemetry Dashboard Test`.

| Environment | OS / CPU architecture | Python | uv | Offline tests (network blocked) | Real-data exercise | App start + action + shutdown |
|---|---|---|---:|---|---|---|
| Local fresh clone | macOS 26.6.2 / arm64 (Apple M1 Pro) | 3.14.2 | 0.13.7 (Homebrew aarch64) | 16 tests OK (0.367 s) | PASS (`+11.128 m`) | PASS, graceful, exit 0, port closed |
| `windows-latest` | Windows Server 2025 (10.0.26100) / x64 (AMD64) | 3.14.10 | 0.13.7 (x86_64-pc-windows-msvc) | 16 tests OK (0.730 s) | PASS | PASS, graceful, port closed |
| `macos-15` | macOS 15.8.2 / arm64 | 3.14.10 | 0.13.7 (aarch64-apple-darwin) | 16 tests OK (0.610 s) | PASS | PASS, graceful, port closed |
| `macos-15-intel` | macOS 15.7.9 / x86_64 (Intel) | 3.14.7 | 0.13.7 (x86_64-apple-darwin) | 16 tests OK (1.325 s) | PASS | PASS, graceful, port closed |

Windows reports shutdown code `3221225786` (`STATUS_CONTROL_C_EXIT`) and macOS arm64 reports `130` (`SIGINT`) because the harness sends the platform's interrupt. Both are expected graceful shutdown signals; the health port was closed in every run.

## Two-minute VS Code walkthrough

1. In VS Code, choose **File → Open Folder** and open this repository. Trust the workspace when prompted.
2. Open the integrated terminal with **Control+`** (macOS: **Command+`**).
3. Run `uv venv --python 3.14`, then `uv pip install -r requirements.txt`, then `uv run streamlit run app.py`.
4. Open <http://127.0.0.1:8501>. The default is the 2021 British GP qualifying demo. Wait for the first FastF1 load.
5. Confirm the two official times are **1:26.209** (VER) and **1:26.023** (HAM), with Hamilton shown as faster.
6. Click **Use the 3,700–4,200 m section from the original exercise**. The section table should show minimum speeds of 225.0 and 216.0 km/h, first brake-on samples near 3,905.3 m and 3,916.4 m, and a `+11.1 m` difference.
7. Drag across the speed chart. Speed, throttle and brake should zoom together. Double-click to reset. Move the distance slider and confirm the measurements change.
8. Open the **Race pace** tab. Load **2021 → Spanish Grand Prix → Race** to see compound colours, stint lines, tyre-age points and the included/excluded lap audit.
9. Use **Download selected samples · CSV** and **Download interactive chart · HTML** to export the current section.
10. Press **Control+C** in the terminal and confirm Streamlit stops without leaving the port open.
