from types import SimpleNamespace
import unittest

import fastf1
import pandas as pd

from f1lab.data import choose_lap, lap_inclusion, valid_laps


class LapSelectionTests(unittest.TestCase):
    def test_fastest_selection_excludes_deleted_pit_and_inaccurate_laps(self):
        rows = []
        for number, seconds in enumerate([86, 80, 81, 82, 83, 87], start=1):
            rows.append({
                "Driver": "VER", "DriverNumber": "33", "LapNumber": number,
                "LapTime": pd.Timedelta(seconds=seconds), "IsAccurate": number != 5,
                "Deleted": number == 2,
                "PitInTime": pd.Timedelta(seconds=1) if number == 3 else pd.NaT,
                "PitOutTime": pd.Timedelta(seconds=1) if number == 4 else pd.NaT,
                "Compound": "SOFT", "TyreLife": number, "Stint": 1,
                "TrackStatus": "1",
            })
        session = SimpleNamespace(laps=fastf1.core.Laps(rows))
        laps = valid_laps(session, "VER")
        self.assertEqual(laps["LapNumber"].tolist(), [1, 6])
        self.assertEqual(choose_lap(laps)["LapNumber"], 1)
        self.assertEqual(choose_lap(laps, 6)["LapNumber"], 6)
        with self.assertRaises(ValueError):
            choose_lap(laps, 2)

    def test_inclusion_audit_explains_every_exclusion(self):
        rows = []
        for number, seconds in enumerate([86, 80, 81, 82, 83, 87], start=1):
            rows.append({
                "Driver": "VER", "DriverNumber": "33", "LapNumber": number,
                "LapTime": pd.Timedelta(seconds=seconds), "IsAccurate": number != 5,
                "Deleted": number == 2,
                "PitInTime": pd.Timedelta(seconds=1) if number == 3 else pd.NaT,
                "PitOutTime": pd.Timedelta(seconds=1) if number == 4 else pd.NaT,
                "Compound": "SOFT", "TyreLife": number, "Stint": 1,
                "TrackStatus": "1",
            })
        session = SimpleNamespace(laps=fastf1.core.Laps(rows))
        audit = lap_inclusion(session, "VER")
        reasons = dict(zip(audit["LapNumber"], audit["Reason"]))
        self.assertEqual(reasons[2], "Deleted lap")
        self.assertEqual(reasons[3], "Pit in/out lap")
        self.assertEqual(reasons[4], "Pit in/out lap")
        self.assertEqual(reasons[5], "Inaccurate timing")
        self.assertEqual(set(audit.loc[audit["Included"], "LapNumber"]), {1, 6})


if __name__ == "__main__":
    unittest.main()
