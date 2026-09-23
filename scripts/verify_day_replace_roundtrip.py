"""Live round-trip: seed duplicates -> day replace -> assert exact new set."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.auth import get_calendar_service
from core.calendar_import import (
    _list_timed_events_overlapping_day,
    _writable_calendar_ids,
    insert_events_batch,
)
from core.calendar_sync import list_calendars

DAY = "2026-09-04"
CAL_NAME_HINT = "工作"


def main():
    service = get_calendar_service()
    calendars = list_calendars()
    writable = _writable_calendar_ids(calendars)
    # Prefer a calendar whose summary looks like work; else first writable
    target = None
    for cal in calendars:
        if cal.get("id") in writable and CAL_NAME_HINT in (cal.get("summary") or ""):
            target = cal["id"]
            break
    if not target:
        target = writable[0]
    print("target calendar:", target)

    # Seed 12 duplicates in same slot (the bug shape)
    for i in range(12):
        service.events().insert(
            calendarId=target,
            body={
                "summary": f"SEED dup {i}",
                "start": {"dateTime": f"{DAY}T11:00:00", "timeZone": "Asia/Shanghai"},
                "end": {"dateTime": f"{DAY}T12:00:00", "timeZone": "Asia/Shanghai"},
            },
        ).execute()
    before = len(_list_timed_events_overlapping_day(service, target, DAY))
    print("seeded timed events on target day:", before)
    assert before >= 12, before

    mapping = {"工作": target}
    new_events = [
        {
            "start": f"{DAY}T09:00:00",
            "end": f"{DAY}T10:00:00",
            "event": "VERIFY-A",
            "score": 8,
            "notes": "roundtrip",
            "category": "工作",
        },
        {
            "start": f"{DAY}T14:00:00",
            "end": f"{DAY}T15:00:00",
            "event": "VERIFY-B",
            "score": 7,
            "notes": "roundtrip",
            "category": "工作",
        },
    ]
    written = insert_events_batch(new_events, mapping, log_callback=print)
    print("written:", written)

    # Count across all writable calendars for the day
    total = 0
    titles = []
    for cal_id in writable:
        items = _list_timed_events_overlapping_day(service, cal_id, DAY)
        total += len(items)
        titles.extend(e.get("summary", "") for e in items)

    print("AFTER total timed:", total)
    print("titles:", titles)
    if total != 2:
        print("FAIL: expected exactly 2 events after replace")
        return 1
    if not any("VERIFY-A" in t for t in titles) or not any("VERIFY-B" in t for t in titles):
        print("FAIL: expected VERIFY-A/B present")
        return 1
    if any("SEED dup" in t for t in titles):
        print("FAIL: seed duplicates still present")
        return 1
    print("PASS: replace left exactly the new day set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
