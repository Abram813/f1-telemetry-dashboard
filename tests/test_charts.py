import unittest

import pandas as pd

from f1lab.charts import pace_chart, telemetry_chart


class ChartTests(unittest.TestCase):
    def telemetry(self):
        return pd.DataFrame({
            "Distance": [3700, 3800, 3900, 4000],
            "Speed": [300, 290, 270, 230],
            "Throttle": [100, 90, 20, 0],
            "Brake": pd.array([False, False, True, True], dtype="boolean"),
        })

    def test_telemetry_panels_share_one_x_axis(self):
        figure = telemetry_chart([self.telemetry(), self.telemetry()], ["A", "B"], 3700, 4000, "Test")
        for axis in ("xaxis", "xaxis2", "xaxis3"):
            self.assertEqual(figure.layout[axis].matches, "x3")
        self.assertEqual(list(figure.layout.xaxis.range), [3700, 4000])

    def test_pace_chart_uses_tyre_age_and_compound_colour(self):
        laps = pd.DataFrame({
            "Driver": ["VER", "VER", "HAM", "HAM"],
            "Stint": [1, 1, 1, 1],
            "Compound": ["SOFT", "SOFT", "MEDIUM", "MEDIUM"],
            "LapNumber": [2, 3, 2, 3],
            "TyreLife": [1, 2, 1, 2],
            "LapSeconds": [90.0, 90.2, 91.0, 91.1],
            "TrackStatus": ["1", "1", "1", "1"],
        })
        figure = pace_chart(laps, ["VER", "HAM"], "Test")
        self.assertEqual(len(figure.data), 2)
        self.assertEqual(list(figure.data[0].x), [1, 2])
        self.assertIn("SOFT", figure.data[0].name)
        self.assertIn("MEDIUM", figure.data[1].name)


if __name__ == "__main__":
    unittest.main()
