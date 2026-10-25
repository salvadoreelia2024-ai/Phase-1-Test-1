"""Independent invariants for the actual snapshot shipped to the browser."""
import json
import math
from pathlib import Path
import unittest
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


class PublishedSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.snapshot = json.loads((ROOT / 'public/data/snapshot.json').read_text())

    def test_truthful_fixture_and_instrument(self):
        s = self.snapshot
        self.assertEqual(s['schemaVersion'], 1)
        self.assertIn(s['mode'], ('demo', 'live'))
        self.assertEqual(s['instrument']['symbol'], 'CL=F')
        self.assertIs(s['model']['calibrated'], False,
                      'Do not advertise calibration without independently verified results')
        self.assertGreater(s['referencePrice'], 0)
        self.assertEqual(len(s['horizons']), 10)
        self.assertEqual(len(set(h['id'] for h in s['horizons'])), 10)
        self.assertEqual(s['levels'], sorted(set(s['levels'])))

    def test_every_published_probability_and_range_is_valid(self):
        s = self.snapshot
        for horizon in s['horizons']:
            self.assertEqual(len(horizon['results']), len(s['levels']))
            for row in horizon['results']:
                for p in (row['touch'], row['finish'], *row['range']):
                    self.assertTrue(math.isfinite(p))
                    self.assertGreaterEqual(p, 0)
                    self.assertLessEqual(p, 1)
                self.assertLessEqual(row['finish'], row['touch'] + 1e-6)
                self.assertLessEqual(row['range'][0], row['range'][1])
                self.assertEqual(len(row['targetBeforeStop']), len(s['levels']))
                for p in row['targetBeforeStop']:
                    if p is not None:
                        self.assertGreaterEqual(p, 0)
                        self.assertLessEqual(p, row['touch'] + 1e-6)

    def test_more_time_never_reduces_touch_probability(self):
        horizons = self.snapshot['horizons']
        for before, after in zip(horizons, horizons[1:]):
            self.assertLessEqual(before['tradingHours'], after['tradingHours'])
            for old, new in zip(before['results'], after['results']):
                self.assertLessEqual(old['touch'], new['touch'] + 1e-6)

    def test_farther_target_never_more_likely(self):
        s = self.snapshot
        for h in s['horizons']:
            lower = [r['touch'] for level, r in zip(s['levels'], h['results'])
                     if level < s['referencePrice']]
            upper = [r['touch'] for level, r in zip(s['levels'], h['results'])
                     if level > s['referencePrice']]
            for a, b in zip(lower, lower[1:]):
                self.assertLessEqual(a, b + 1e-6)
            for a, b in zip(upper, upper[1:]):
                self.assertGreaterEqual(a + 1e-6, b)

    def test_scenarios_ordered_and_finite(self):
        s = self.snapshot
        for h in s['horizons']:
            times = [p['hours'] for p in h['scenario']]
            self.assertEqual(times, sorted(times))
            for p in h['scenario']:
                self.assertGreater(p['p10'], 0)
                self.assertLessEqual(p['p10'], p['p50'])
                self.assertLessEqual(p['p50'], p['p90'])
                self.assertTrue(all(math.isfinite(p[k]) for k in ('p10', 'p50', 'p90')))
            for k in ('p10', 'p50', 'p90'):
                self.assertAlmostEqual(h['scenario'][0][k], s['referencePrice'], places=2)


class PublicationFailureTests(unittest.TestCase):
    def test_provider_failure_preserves_published_bytes(self):
        from engine.update import update
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'snapshot.json'
            original = b'{"id":"previous","mode":"live"}'
            output.write_bytes(original)
            database = Path(directory) / 'archive.sqlite'
            with patch('engine.update.collect_market', side_effect=RuntimeError('provider offline')):
                with self.assertRaisesRegex(RuntimeError, 'provider offline'):
                    update(output, database, paths=1000)
            self.assertEqual(output.read_bytes(), original)
            import sqlite3
            with sqlite3.connect(database) as db:
                row = db.execute("SELECT status FROM pulls WHERE domain='update'").fetchone()
                self.assertEqual(row[0], 'error')

    def test_failed_publication_can_retry_same_input(self):
        from engine.update import update
        import sqlite3
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'snapshot.json'
            previous = {'id':'demo', 'mode':'demo'}
            output.write_text(json.dumps(previous))
            database = Path(directory) / 'archive.sqlite'
            row = {'timestamp':'2026-10-20T15:00:00Z', 'close':98., 'high':99., 'low':97.}
            market = {'CL=F':[row], '^IXIC':[], 'BZ=F':[], '^OVX':[]}
            candidate = {'id':'live', 'mode':'live', 'generatedAt':row['timestamp']}
            with patch('engine.update.collect_market', return_value=market), \
                 patch('engine.update.build_snapshot', return_value=candidate) as build, \
                 patch('engine.update.collect_eia_headlines', return_value=[]), \
                 patch('engine.update.publish', return_value=(candidate, {}, [])), \
                 patch('engine.update.atomic_json', side_effect=OSError('disk unavailable')):
                with self.assertRaisesRegex(OSError, 'disk unavailable'):
                    update(output, database, paths=1000)
                self.assertIsNone(build.call_args.kwargs['previous'])
            self.assertEqual(json.loads(output.read_text()), previous)
            with patch('engine.update.collect_market', return_value=market), \
                 patch('engine.update.build_snapshot', return_value=candidate), \
                 patch('engine.update.collect_eia_headlines', return_value=[]), \
                 patch('engine.update.publish', return_value=(candidate, {}, [])):
                update(output, database, paths=1000)
            self.assertEqual(json.loads(output.read_text())['id'], 'live')

    def test_archive_refresh_does_not_duplicate_bar(self):
        from engine.ingest import connect, archive_bars, archived_bars
        with tempfile.TemporaryDirectory() as directory:
            db = connect(Path(directory) / 'archive.sqlite')
            row = {'timestamp':'2026-10-20T15:00:00Z', 'close':98., 'high':99., 'low':97.}
            archive_bars(db, 'CL=F', [row])
            archive_bars(db, 'CL=F', [{**row, 'close':98.5}])
            bars = archived_bars(db, 'CL=F')
            self.assertEqual(len(bars), 1)
            self.assertEqual(bars[0]['close'], 98.5)
            self.assertEqual(archived_bars(db, 'BZ=F'), [])
            db.close()


if __name__ == '__main__':
    unittest.main()
