from datetime import datetime
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('remind', Path(__file__).with_name('remind.py'))
remind = importlib.util.module_from_spec(spec)
spec.loader.exec_module(remind)


class ScheduleTests(unittest.TestCase):
    config = {'start_date': '2026-11-08', 'days': 7, 'hours': [9, 15, 22]}

    def test_all_daily_slots_and_last_day(self):
        for day in range(8, 15):
            for hour in self.config['hours']:
                self.assertIsNotNone(remind.due_slot(self.config, datetime(2026, 11, day, hour)))

    def test_no_send_before_start_after_expiry_or_missed_slot(self):
        for value in ['2026-11-07T09:00', '2026-11-15T09:00',
                      '2026-11-08T08:59', '2026-11-08T09:10', '2026-11-08T12:00']:
            self.assertIsNone(remind.due_slot(self.config, datetime.fromisoformat(value)))

    def test_failed_or_ambiguous_delivery_is_not_retried(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.json'
            config.write_text(json.dumps(dict(self.config, helper='fake-helper.py',
                                             project='test', title='test', message='test')))
            with patch.object(remind, 'due_slot', return_value='2026-11-08T09:00'), \
                    patch.object(remind.subprocess, 'run', side_effect=OSError) as send:
                self.assertEqual(remind.run(config), 1)
                self.assertEqual(remind.run(config), 0)
                self.assertEqual(send.call_count, 1)


if __name__ == '__main__':
    unittest.main()
