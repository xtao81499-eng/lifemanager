"""Prove full-day replace clears many duplicates even when some queries flake."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.calendar_import import (  # noqa: E402
    _delete_timed_events_for_day,
    _writable_calendar_ids,
    insert_events_batch,
)


def _quiet_log(_msg: str) -> None:
    return None


class _Exec:
    def __init__(self, payload):
        self._payload = payload

    def execute(self):
        if isinstance(self._payload, Exception):
            raise self._payload
        if callable(self._payload):
            return self._payload()
        return self._payload


class FakeEventsAPI:
    def __init__(self, store: dict[str, list[dict]], fail_first_n: dict[str, int] | None = None):
        self.store = store
        self.fail_first_n = fail_first_n or {}
        self.list_calls: dict[str, int] = {}
        self.delete_calls = 0
        self.insert_calls = 0

    def list(self, calendarId, **kwargs):
        self.list_calls[calendarId] = self.list_calls.get(calendarId, 0) + 1
        remaining = self.fail_first_n.get(calendarId, 0)
        if remaining > 0:
            self.fail_first_n[calendarId] = remaining - 1
            return _Exec(RuntimeError("transient query failure"))

        def payload():
            return {"items": list(self.store.get(calendarId, [])), "nextPageToken": None}

        return _Exec(payload)

    def delete(self, calendarId, eventId):
        def payload():
            items = self.store.get(calendarId, [])
            self.store[calendarId] = [e for e in items if e.get("id") != eventId]
            self.delete_calls += 1
            return {}

        return _Exec(payload)

    def insert(self, calendarId, body):
        def payload():
            self.insert_calls += 1
            evt = {
                "id": f"new-{self.insert_calls}",
                "summary": body["summary"],
                "start": body["start"],
                "end": body["end"],
            }
            self.store.setdefault(calendarId, []).append(evt)
            return evt

        return _Exec(payload)


class FakeService:
    def __init__(self, events_api: FakeEventsAPI):
        self._events = events_api

    def events(self):
        return self._events


def _dup_event(i: int, day: str = "2026-09-04") -> dict:
    return {
        "id": f"dup-{i}",
        "summary": "奇怪松上班 7.0/10",
        "start": {"dateTime": f"{day}T11:00:00+08:00"},
        "end": {"dateTime": f"{day}T19:00:00+08:00"},
    }


class DayReplaceTests(unittest.TestCase):
    def test_writable_calendar_filter(self):
        cals = [
            {"id": "work", "accessRole": "owner"},
            {"id": "holiday", "accessRole": "reader"},
            {"id": "primary", "accessRole": "owner"},
        ]
        ids = _writable_calendar_ids(cals, extra_ids=["mapped"])
        self.assertEqual(ids, ["work", "primary", "mapped"])

    @patch("time.sleep", return_value=None)
    def test_clears_many_duplicates_with_flaky_calendar(self, _sleep):
        """Reproduce the bug: one calendar has dozens of dups; another flakes."""
        day = "2026-09-04"
        store = {
            "work": [_dup_event(i) for i in range(40)],
            "commute": [
                {
                    "id": "c1",
                    "summary": "通勤 6.5/10",
                    "start": {"dateTime": f"{day}T08:00:00+08:00"},
                    "end": {"dateTime": f"{day}T09:00:00+08:00"},
                }
            ],
            "flaky": [_dup_event(999)],
        }
        api = FakeEventsAPI(store, fail_first_n={"flaky": 2})
        service = FakeService(api)

        deleted = _delete_timed_events_for_day(
            service,
            day,
            ["work", "commute", "flaky"],
            log_callback=_quiet_log,
            max_passes=5,
        )

        self.assertGreaterEqual(deleted, 42)
        self.assertEqual(len(store["work"]), 0)
        self.assertEqual(len(store["commute"]), 0)
        self.assertEqual(len(store["flaky"]), 0)

    def test_keeps_all_day_events(self):
        day = "2026-09-04"
        store = {
            "primary": [
                {
                    "id": "allday",
                    "summary": "生日",
                    "start": {"date": day},
                    "end": {"date": "2026-09-05"},
                },
                _dup_event(1),
            ]
        }
        api = FakeEventsAPI(store)
        deleted = _delete_timed_events_for_day(
            FakeService(api), day, ["primary"], log_callback=_quiet_log
        )
        self.assertEqual(deleted, 1)
        self.assertEqual(len(store["primary"]), 1)
        self.assertEqual(store["primary"][0]["id"], "allday")

    @patch("time.sleep", return_value=None)
    def test_insert_events_batch_replaces_day(self, _sleep):
        day = "2026-09-04"
        store = {"work": [_dup_event(i) for i in range(25)]}
        api = FakeEventsAPI(store)
        service = FakeService(api)
        calendars = [{"id": "work", "summary": "工作", "accessRole": "owner"}]

        new_events = [
            {
                "start": f"{day}T11:00:00",
                "end": f"{day}T19:00:00",
                "event": "奇怪松上班",
                "score": 7.0,
                "notes": "",
                "category": "工作",
            }
        ]

        with patch("core.calendar_import.get_calendar_service", return_value=service), patch(
            "core.calendar_sync.list_calendars", return_value=calendars
        ):
            written = insert_events_batch(
                new_events, {"工作": "work"}, log_callback=_quiet_log
            )

        self.assertEqual(written, 1)
        self.assertEqual(len(store["work"]), 1)
        self.assertIn("奇怪松上班", store["work"][0]["summary"])
        self.assertEqual(api.delete_calls, 25)
        self.assertEqual(api.insert_calls, 1)

    @patch("time.sleep", return_value=None)
    def test_aborts_write_if_all_queries_fail(self, _sleep):
        store = {"broken": [_dup_event(1)]}
        api = FakeEventsAPI(store, fail_first_n={"broken": 99})
        with self.assertRaises(RuntimeError):
            _delete_timed_events_for_day(
                FakeService(api), "2026-09-04", ["broken"], log_callback=_quiet_log
            )


    def test_parses_non_shanghai_offsets(self):
        from core.calendar_import import _parse_event_datetime

        # UTC noon == 20:00 Shanghai
        dt = _parse_event_datetime("2026-09-04T12:00:00+00:00")
        self.assertEqual(dt.hour, 20)
        self.assertIsNone(dt.tzinfo)
        # Already Shanghai
        dt2 = _parse_event_datetime("2026-09-04T11:00:00+08:00")
        self.assertEqual(dt2.hour, 11)

    def test_lists_events_with_mixed_offsets(self):
        day = "2026-09-04"
        store = {
            "work": [
                {
                    "id": "utc",
                    "summary": "utc event",
                    "start": {"dateTime": "2026-09-04T03:00:00+00:00"},  # 11:00 SH
                    "end": {"dateTime": "2026-09-04T04:00:00+00:00"},
                },
                {
                    "id": "sh",
                    "summary": "sh event",
                    "start": {"dateTime": "2026-09-04T12:00:00+08:00"},
                    "end": {"dateTime": "2026-09-04T13:00:00+08:00"},
                },
            ]
        }
        api = FakeEventsAPI(store)
        deleted = _delete_timed_events_for_day(
            FakeService(api), day, ["work"], log_callback=_quiet_log
        )
        self.assertEqual(deleted, 2)
        self.assertEqual(store["work"], [])


if __name__ == "__main__":
    unittest.main()

