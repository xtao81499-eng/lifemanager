"""Unit + live checks for 23:30–00:00 / 24:00 day-end events."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.calendar_import import (  # noqa: E402
    build_event_datetimes,
    normalize_event_times,
    insert_events_batch,
)


class MidnightEndTests(unittest.TestCase):
    def test_build_00_00_rolls_to_next_day(self):
        start, end = build_event_datetimes("2026-09-01", "23:30", "00:00")
        self.assertEqual(start, "2026-09-01T23:30:00")
        self.assertEqual(end, "2026-09-02T00:00:00")

    def test_build_24_00_rolls_to_next_day(self):
        start, end = build_event_datetimes("2026-09-01", "23:30", "24:00")
        self.assertEqual(start, "2026-09-01T23:30:00")
        self.assertEqual(end, "2026-09-02T00:00:00")

    def test_normalize_fixes_same_day_midnight_bug(self):
        # Reproduce the table write-back bug
        ev = normalize_event_times(
            {
                "start": "2026-09-01T23:30:00",
                "end": "2026-09-01T00:00:00",
                "event": "睡觉",
                "category": "睡眠",
            }
        )
        self.assertEqual(ev["end"], "2026-09-02T00:00:00")
        self.assertLess(ev["start"], ev["end"])

    def test_normal_same_day_unchanged(self):
        start, end = build_event_datetimes("2026-09-01", "21:00", "22:30")
        self.assertEqual(start, "2026-09-01T21:00:00")
        self.assertEqual(end, "2026-09-01T22:30:00")

    def test_insert_batch_accepts_table_bug_shape(self):
        """Events rebuilt as same-day 00:00 must still write after normalize."""

        class _Exec:
            def __init__(self, payload):
                self._payload = payload

            def execute(self):
                return self._payload() if callable(self._payload) else self._payload

        class API:
            def __init__(self):
                self.inserted = []

            def list(self, **kwargs):
                return _Exec({"items": [], "nextPageToken": None})

            def delete(self, **kwargs):
                return _Exec({})

            def insert(self, calendarId, body):
                self.inserted.append(body)

                def payload():
                    return {"id": "x"}

                return _Exec(payload)

        class Svc:
            def __init__(self, api):
                self._api = api

            def events(self):
                return self._api

        api = API()
        events = [
            {
                "start": "2026-09-01T23:30:00",
                "end": "2026-09-01T00:00:00",  # bug shape from UI
                "event": "睡觉",
                "score": 7.0,
                "notes": "",
                "category": "睡眠",
            }
        ]
        with patch("core.calendar_import.get_calendar_service", return_value=Svc(api)), patch(
            "core.calendar_sync.list_calendars",
            return_value=[{"id": "sleep", "summary": "睡眠", "accessRole": "owner"}],
        ):
            n = insert_events_batch(events, {"睡眠": "sleep"}, log_callback=lambda m: None)
        self.assertEqual(n, 1)
        self.assertEqual(api.inserted[0]["end"]["dateTime"], "2026-09-02T00:00:00")
        self.assertEqual(api.inserted[0]["start"]["dateTime"], "2026-09-01T23:30:00")


if __name__ == "__main__":
    unittest.main()
