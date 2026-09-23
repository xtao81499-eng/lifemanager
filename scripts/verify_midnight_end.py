"""Live: write 23:30-00:00 sleep via the same path as the UI bug shape."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.auth import get_calendar_service
from core.calendar_import import (
    _list_timed_events_overlapping_day,
    _writable_calendar_ids,
    build_event_datetimes,
    insert_events_batch,
)
from core.calendar_sync import list_calendars

DAY = "2026-09-01"


def main():
    # Prove the UI rebuild path
    start, end = build_event_datetimes(DAY, "23:30", "00:00")
    print("built:", start, "->", end)
    assert end == "2026-09-02T00:00:00", end

    service = get_calendar_service()
    calendars = list_calendars()
    writable = _writable_calendar_ids(calendars)
    sleep_id = next(c["id"] for c in calendars if c.get("summary") == "睡眠")
    mapping = {c["summary"]: c["id"] for c in calendars if c["id"] in writable}

    # Clear day first
    from core.calendar_import import _delete_timed_events_for_day

    _delete_timed_events_for_day(service, DAY, writable, log_callback=print)

    # Two events: normal + midnight-end in the BUGGY same-date shape
    events = [
        {
            "start": f"{DAY}T22:30:00",
            "end": f"{DAY}T23:30:00",
            "event": "洗漱收拾",
            "score": 6.7,
            "notes": "",
            "category": "收拾打扮" if "收拾打扮" in mapping else "睡眠",
        },
        {
            "start": f"{DAY}T23:30:00",
            "end": f"{DAY}T00:00:00",  # intentional bug shape
            "event": "睡觉",
            "score": 7.0,
            "notes": "midnight-end verify",
            "category": "睡眠",
        },
    ]
    written = insert_events_batch(events, mapping, log_callback=print)
    print("written", written)
    assert written == 2, written

    sleep_items = _list_timed_events_overlapping_day(service, sleep_id, DAY)
    titles = [e.get("summary") for e in sleep_items]
    print("sleep items:", titles)
    assert any(t and t.startswith("睡觉") for t in titles), titles

    # Cleanup
    _delete_timed_events_for_day(service, DAY, writable, log_callback=print)
    after = sum(len(_list_timed_events_overlapping_day(service, c, DAY)) for c in writable)
    print("after cleanup", after)
    assert after == 0
    print("PASS: midnight-end sleep writes successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
