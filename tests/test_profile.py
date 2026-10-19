import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ContributionStatistics(unittest.TestCase):
    def load(self):
        path = ROOT / 'scripts' / 'generate_profile.py'
        self.assertTrue(path.exists(), 'The asset-only generator must exist')
        spec = importlib.util.spec_from_file_location('profile_generator', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_no_activity_returns_zero_streaks(self):
        stats = self.load().streaks([
            {'date': '2026-10-18', 'contributionCount': 0},
            {'date': '2026-10-19', 'contributionCount': 0},
        ])
        self.assertEqual(stats, {'current': 0, 'longest': 0, 'active': 0})

    def test_today_can_remain_empty_while_yesterdays_streak_is_current(self):
        stats = self.load().streaks([
            {'date': '2026-10-16', 'contributionCount': 0},
            {'date': '2026-10-17', 'contributionCount': 1},
            {'date': '2026-10-18', 'contributionCount': 2},
            {'date': '2026-10-19', 'contributionCount': 0},
        ])
        self.assertEqual(stats, {'current': 2, 'longest': 2, 'active': 2})

    def test_missing_dates_break_a_streak(self):
        stats = self.load().streaks([
            {'date': '2026-10-15', 'contributionCount': 3},
            {'date': '2026-10-17', 'contributionCount': 1},
            {'date': '2026-10-18', 'contributionCount': 0},
            {'date': '2026-10-19', 'contributionCount': 1},
        ])
        self.assertEqual(stats, {'current': 1, 'longest': 1, 'active': 3})


if __name__ == '__main__':
    unittest.main()
