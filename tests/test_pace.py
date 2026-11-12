import unittest

import pandas as pd

from f1lab.pace import stint_summary, stint_trends


class PaceTests(unittest.TestCase):
    def laps(self):
        return pd.DataFrame({
            "Driver": ["VER"] * 4, "Stint": [1] * 4, "Compound": ["SOFT"] * 4,
            "LapNumber": [2, 3, 4, 5], "TyreLife": [2, 3, 4, 5],
            "LapSeconds": [90.0, 90.2, 90.4, 150.0],
            "TrackStatus": ["1", "1", "1", "4"], "SessionMinutes": [2, 4, 6, 9],
        })

    def test_non_green_lap_does_not_distort_stint_trend(self):
        result = stint_trends(self.laps()).iloc[0]
        self.assertEqual(result["Green laps"], 3)
        self.assertAlmostEqual(result["Pace change (s/tyre lap)"], 0.2)

    def test_short_stint_is_not_given_a_trend(self):
        result = stint_trends(self.laps().iloc[:2]).iloc[0]
        self.assertTrue(pd.isna(result["Pace change (s/tyre lap)"]))

    def test_unknown_track_status_is_not_treated_as_green(self):
        laps = self.laps().drop(columns="TrackStatus")
        self.assertTrue(stint_trends(laps).empty)

    def test_stint_summary_reports_compound_and_tyre_age(self):
        result = stint_summary(self.laps()).iloc[0]
        self.assertEqual(result["Compound"], "SOFT")
        self.assertEqual(result["Laps"], 4)
        self.assertEqual(result["Tyre age min"], 2)
        self.assertEqual(result["Tyre age max"], 5)
        self.assertEqual(result["Green laps"], 3)


if __name__ == "__main__":
    unittest.main()
