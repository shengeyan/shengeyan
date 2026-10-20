import importlib.util
import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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

    def test_render_retires_commit_details_in_refresh_and_offline_modes(self):
        legacy = json.loads((ROOT / 'assets/deep-space/data.json').read_text())
        legacy['commits'] = [{
            'messageHeadline': 'private-detail-sentinel', 'oid': 'abc1234',
            'committedDate': '2026-10-19T00:00:00Z',
            'url': 'https://github.com/example/repo/commit/abc1234', 'repo': 'example',
        }]
        legacy['user']['repositories']['nodes'][0]['defaultBranchRef'] = {
            'target': {'history': {'nodes': [{'messageHeadline': 'private-detail-sentinel'}]}}
        }
        retired = ['recent-commits.md', 'activity-cn.svg', 'activity-cn-mobile.svg',
                   'activity-en.svg', 'activity-en-mobile.svg']
        for refresh in (False, True):
            with self.subTest(refresh=refresh), tempfile.TemporaryDirectory() as directory:
                module = self.load()
                output = Path(directory)
                snapshot = output / 'data.json'
                snapshot.write_text(json.dumps(legacy))
                for name in retired:
                    (output / name).write_text('private-detail-sentinel')
                arguments = ['generate_profile.py'] + (['--refresh'] if refresh else [])
                with patch.object(module, 'OUT', output), patch('sys.argv', arguments), \
                        patch.object(module, 'refresh', return_value=copy.deepcopy(legacy)), \
                        patch('sys.stdout', new_callable=io.StringIO):
                    module.main()
                saved = json.loads(snapshot.read_text())
                self.assertNotIn('commits', saved.keys())
                self.assertTrue(all('defaultBranchRef' not in repo
                                    for repo in saved['user']['repositories']['nodes']))
                self.assertEqual(saved['user']['contributionsCollection'],
                                 legacy['user']['contributionsCollection'])
                self.assertTrue(all(not (output / name).exists() for name in retired))
                for asset in output.iterdir():
                    self.assertNotIn('private-detail-sentinel', asset.read_text())


if __name__ == '__main__':
    unittest.main()
