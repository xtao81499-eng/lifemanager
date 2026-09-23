"""Seed stacked sleep on 2026-09-02 then full-day replace; assert no stack."""
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

DAY = "2026-09-02"


def main():
    service = get_calendar_service()
    calendars = list_calendars()
    writable = _writable_calendar_ids(calendars)
    sleep_id = None
    for cal in calendars:
        if cal.get("summary") == "睡眠" and cal.get("id") in writable:
            sleep_id = cal["id"]
            break
    if not sleep_id:
        raise SystemExit("sleep calendar not found")
    print("sleep calendar:", sleep_id)

    # Stack 8 sleep events like the bug
    for i in range(8):
        service.events().insert(
            calendarId=sleep_id,
            body={
                "summary": f"睡觉 SEED-{i} 7.0/10",
                "start": {"dateTime": f"{DAY}T00:00:00", "timeZone": "Asia/Shanghai"},
                "end": {"dateTime": f"{DAY}T07:30:00", "timeZone": "Asia/Shanghai"},
            },
        ).execute()

    before = len(_list_timed_events_overlapping_day(service, sleep_id, DAY))
    print("sleep before:", before)
    assert before >= 8, before

    mapping = {cal["summary"]: cal["id"] for cal in calendars if cal.get("id") in writable}
    mapping.setdefault("睡眠", sleep_id)
    new_events = [
        {
            "start": f"{DAY}T00:00:00",
            "end": f"{DAY}T07:30:00",
            "event": "睡觉",
            "score": 7.0,
            "notes": "verify",
            "category": "睡眠",
        },
        {
            "start": f"{DAY}T08:00:00",
            "end": f"{DAY}T09:00:00",
            "event": "VERIFY-COMMUTE",
            "score": 7,
            "notes": "",
            "category": "通勤" if "通勤" in mapping else "睡眠",
        },
    ]
    # remap second event category if needed
    if new_events[1]["category"] not in mapping:
        new_events[1]["category"] = "睡眠"

    written = insert_events_batch(new_events, mapping, log_callback=print)
    print("written:", written)

    sleep_after = _list_timed_events_overlapping_day(service, sleep_id, DAY)
    print("sleep after count:", len(sleep_after))
    for e in sleep_after:
        print(" ", e.get("summary"), e.get("start"))

    total = 0
    for cid in writable:
        total += len(_list_timed_events_overlapping_day(service, cid, DAY))
    print("day total timed:", total)

    if len(sleep_after) != 1:
        print("FAIL: expected exactly 1 sleep event")
        return 1
    if "SEED-" in (sleep_after[0].get("summary") or ""):
        print("FAIL: seed remain")
        return 1
    if total != 2:
        print("FAIL: expected exactly 2 timed events for the day")
        return 1
    print("PASS: sleep not stacked; day has exact new set")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
