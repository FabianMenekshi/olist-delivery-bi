"""Publishing must preserve data, protect existing files and handle no denominator."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import pandas as pd

from src.results import OUTPUT_FILES, write_snapshot
from src.stats import add_intervals


class ResultsTests(unittest.TestCase):
    def setUp(self):
        self.frames = {
            'overview': pd.DataFrame([{
                'all_orders': 3, 'eligible_orders': 2, 'late_orders': 1, 'late_rate': .5,
            }]),
            'monthly': pd.DataFrame({
                'month': ['2018-01-01', '2018-02-01'],
                'all_orders': [3, 0], 'eligible_orders': [2, 0],
                'late_orders': [1, 0], 'late_rate': [.5, float('nan')],
            }),
            'states': add_intervals(pd.DataFrame({
                'customer_state': ['SP'], 'all_orders': [3],
                'eligible_orders': [2], 'late_orders': [1], 'late_rate': [.5],
            })),
            'quality': pd.DataFrame([{
                'check_name': 'order_count_reconciles', 'severity': 'error', 'issues': 0,
            }]),
        }

    def test_snapshot_retains_small_groups_null_rates_and_manual_readme(self):
        with TemporaryDirectory() as temporary:
            output = Path(temporary) / 'results'
            output.mkdir()
            (output / 'README.md').write_text('Manually reviewed text.')
            write_snapshot(self.frames, {'dataset_label': 'olist'}, output)
            self.assertEqual({p.name for p in output.iterdir()}, set(OUTPUT_FILES) | {'README.md'})
            self.assertEqual((output / 'README.md').read_text(), 'Manually reviewed text.')
            monthly = pd.read_csv(output / 'monthly.csv')
            self.assertEqual(monthly['eligible_orders'].tolist(), [2, 0])
            self.assertTrue(pd.isna(monthly.loc[1, 'late_rate']))
            self.assertEqual(pd.read_csv(output / 'states.csv')['customer_state'].tolist(), ['SP'])
            metadata = json.loads((output / 'provenance.json').read_text())
            for name, digest in metadata['output_sha256'].items():
                self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
            self.assertFalse((Path(temporary) / 'reports').exists())

    def test_existing_outputs_require_explicit_replace(self):
        with TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / 'monthly.csv').write_text('previous snapshot')
            with self.assertRaises(FileExistsError):
                write_snapshot(self.frames, {}, output)
            self.assertEqual((output / 'monthly.csv').read_text(), 'previous snapshot')

    def test_quality_failure_leaves_existing_snapshot_untouched(self):
        with TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / 'monthly.csv').write_text('previous snapshot')
            self.frames['quality'].loc[0, 'issues'] = 1
            with self.assertRaises(ValueError):
                write_snapshot(self.frames, {}, output, replace=True)
            self.assertEqual((output / 'monthly.csv').read_text(), 'previous snapshot')

    def test_render_failure_does_not_replace_existing_assets(self):
        with TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / 'monthly.csv').write_text('previous snapshot')
            with patch('src.results.draw_overview', side_effect=RuntimeError('render failed')):
                with self.assertRaises(RuntimeError):
                    write_snapshot(self.frames, {}, output, replace=True)
            self.assertEqual((output / 'monthly.csv').read_text(), 'previous snapshot')

    def test_no_eligible_deliveries_still_publishes_defined_counts(self):
        self.frames['overview'].loc[0, ['eligible_orders', 'late_orders', 'late_rate']] = [0, 0, float('nan')]
        self.frames['monthly']['eligible_orders'] = 0
        self.frames['monthly']['late_orders'] = 0
        self.frames['monthly']['late_rate'] = float('nan')
        self.frames['states'] = self.frames['states'].iloc[:0]
        with TemporaryDirectory() as temporary:
            output = Path(temporary)
            (output / 'monthly.csv').write_text('old contents')
            write_snapshot(self.frames, {}, output, replace=True)
            metadata = json.loads((output / 'provenance.json').read_text())
            self.assertIsNone(metadata['overview']['late_rate'])
            self.assertTrue(pd.read_csv(output / 'monthly.csv')['late_rate'].isna().all())


if __name__ == '__main__':
    unittest.main()
