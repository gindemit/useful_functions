import datetime as dt
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('monitor', Path(__file__).with_name('monitor.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class MonitorTests(unittest.TestCase):
    def test_authentication_errors_are_not_capacity(self):
        self.assertEqual(m.classify(1, 'ServiceError: NotAuthenticated 401'), 'authentication_error')
        self.assertEqual(m.classify(1, 'ServiceError: TooManyRequests'), 'rate_limited')
        self.assertEqual(m.classify(0, 'nothing'), 'unverified')
        self.assertEqual(m.classify(0, 'All availability domains are currently out of A1 capacity'), 'no_capacity')

    def test_daily_counts_use_offset_and_separate_errors(self):
        text = '\n'.join([
            '2026-11-04T19:00:00+01:00 Starting Always Free A1 capacity check.',
            '2026-11-05T19:00:00.1234567+01:00 Starting Always Free A1 capacity check.',
            '2026-11-05T19:01:00+01:00 All availability domains are currently out of A1 capacity; the scheduled task will retry.',
            '2026-11-05T19:30:00+01:00 Starting Always Free A1 capacity check.',
            '2026-11-05T19:31:00+01:00 ERROR: NotAuthenticated',
            '  multiline error details',
        ])
        counts, latest = m.stats(text, dt.datetime.fromisoformat('2026-11-04T20:00:00+01:00'))
        self.assertEqual(counts, dict(runs=2, capacity_checks_ok=1, errors=1, provisioned=0))
        self.assertEqual(latest.hour, 19)
        self.assertEqual(latest.minute, 30)

    def test_ambiguous_telegram_failure_is_not_resent(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(m, 'DATA', Path(directory)), patch.object(m.subprocess, 'run', side_effect=m.subprocess.TimeoutExpired('helper', 150)) as run:
            self.assertFalse(m.notify('same', 'title', 'message'))
            self.assertFalse(m.notify('same', 'title', 'message'))
            self.assertEqual(run.call_count, 1)

    def test_success_is_reported_even_if_existing_email_fails(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(m, 'DATA', Path(directory)), patch.object(m, 'notify', return_value=True) as notify:
            m.save(m.DATA / 'oci-a1-running.json', dict(instance_id='test-instance', name='test-server'))
            m.success_alert()
            self.assertEqual(notify.call_args.args[0], 'instance-test-instance')

    def test_auth_failure_alert_and_next_success_reset_failure_count(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(m, 'DATA', Path(directory)), patch.object(m, 'notify', return_value=True) as notify, patch.object(m.subprocess, 'run') as run:
            run.return_value = m.subprocess.CompletedProcess([], 1, 'NotAuthenticated', '')
            self.assertEqual(m.check(), 1)
            self.assertEqual(m.read_json(m.DATA / 'oci-monitor-health.json', {})['outcome'], 'authentication_error')
            self.assertEqual(notify.call_args.args[1], 'Oracle checks need attention')
            run.return_value = m.subprocess.CompletedProcess([], 0, 'All availability domains are currently out of A1 capacity', '')
            self.assertEqual(m.check(), 0)
            health = m.read_json(m.DATA / 'oci-monitor-health.json', {})
            self.assertEqual(health['consecutive_failures'], 0)
            self.assertIn('last_verified', health)

    def test_daily_report_warns_when_no_checks_exist(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(m, 'DATA', Path(directory)), patch.object(m, 'notify', return_value=True) as notify:
            self.assertEqual(m.report(force=True), 0)
            self.assertIn('0 runs started', notify.call_args.args[2])
            self.assertIn('ATTENTION', notify.call_args.args[2])


if __name__ == '__main__':
    unittest.main()
