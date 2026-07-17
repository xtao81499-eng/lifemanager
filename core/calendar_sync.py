"""
Google Calendar 事件抓取模块
"""
from datetime import datetime, timedelta, timezone

from core.auth import get_calendar_service


def list_calendars() -> list[dict]:
    """列出用户所有可见日历。"""
    service = get_calendar_service()
    result = service.calendarList().list().execute()
    return result.get("items", [])


def fetch_events(calendar_id: str = "primary", days: int = 7) -> list[dict]:
    """获取指定日历最近 N 天的事件。"""
    service = get_calendar_service()

    now = datetime.now(timezone.utc)
    time_min = (now - timedelta(days=days)).isoformat()
    time_max = now.isoformat()

    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=500,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    return events_result.get("items", [])


def fetch_all_events(days: int = 7) -> list[dict]:
    """获取所有日历最近 N 天的事件。"""
    calendars = list_calendars()
    all_events = []

    for cal in calendars:
        cal_id = cal["id"]
        events = fetch_events(calendar_id=cal_id, days=days)
        for event in events:
            event["_calendar_name"] = cal.get("summary", "未知")
        all_events.extend(events)

    all_events.sort(key=lambda e: e.get("start", {}).get("dateTime", ""))
    return all_events
