"""
Live verification: clear timed events on a given day via the same code path as import.

Usage:
  python scripts/verify_day_replace.py 2026-09-04
  python scripts/verify_day_replace.py 2026-09-04 --dry-run

Requires config/token.json and working proxy (local).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.auth import get_calendar_service
from core.calendar_import import (
    _delete_timed_events_for_day,
    _list_timed_events_overlapping_day,
    _writable_calendar_ids,
)
from core.calendar_sync import list_calendars


def count_timed(service, calendar_ids: list[str], day: str) -> tuple[int, list[str]]:
    total = 0
    samples = []
    for cal_id in calendar_ids:
        try:
            items = _list_timed_events_overlapping_day(service, cal_id, day)
        except Exception as e:
            print(f"LIST FAIL {cal_id}: {e}")
            continue
        total += len(items)
        for evt in items[:3]:
            samples.append(f"{cal_id}|{evt.get('summary')}|{evt.get('start')}")
    return total, samples


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("day", help="YYYY-MM-DD")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    service = get_calendar_service()
    calendars = list_calendars()
    targets = _writable_calendar_ids(calendars)
    print(f"writable calendars: {len(targets)} / visible {len(calendars)}")

    before, samples = count_timed(service, targets, args.day)
    print(f"BEFORE {args.day}: {before} timed events")
    for s in samples[:10]:
        print("  sample:", s)

    if args.dry_run:
        print("dry-run only, exit")
        return 0 if before >= 0 else 1

    deleted = _delete_timed_events_for_day(service, args.day, targets)
    print(f"deleted: {deleted}")

    after, _ = count_timed(service, targets, args.day)
    print(f"AFTER {args.day}: {after} timed events")

    if after != 0:
        print("FAIL: leftovers remain")
        return 1
    print("PASS: day fully cleared of timed events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
