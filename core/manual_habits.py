"""
Manual habit tracking — Google Drive JSON persistence.

Stores 'lifemanager_manual_habits.json' in the user's Google Drive.
Falls back to local data/manual_habits.json if Drive is unavailable.
"""
import json
from pathlib import Path

DRIVE_FILENAME = "lifemanager_manual_habits.json"
LOCAL_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "manual_habits.json"

_drive_file_id: str | None = None  # module-level cache for Drive file ID


def _get_drive_service():
    from core.auth import get_drive_service
    return get_drive_service()


def _find_or_create_file(service) -> str:
    global _drive_file_id
    if _drive_file_id:
        return _drive_file_id

    results = service.files().list(
        q=f"name='{DRIVE_FILENAME}' and trashed=false",
        spaces="drive",
        fields="files(id)",
        pageSize=1,
    ).execute()

    files = results.get("files", [])
    if files:
        _drive_file_id = files[0]["id"]
        return _drive_file_id

    from googleapiclient.http import MediaInMemoryUpload
    empty = json.dumps({}, ensure_ascii=False).encode("utf-8")
    media = MediaInMemoryUpload(empty, mimetype="application/json")
    f = service.files().create(
        body={"name": DRIVE_FILENAME, "mimeType": "application/json"},
        media_body=media,
        fields="id",
    ).execute()
    _drive_file_id = f["id"]
    return _drive_file_id


def _load() -> dict:
    try:
        service = _get_drive_service()
        file_id = _find_or_create_file(service)
        content = service.files().get_media(fileId=file_id).execute()
        return json.loads(content.decode("utf-8"))
    except Exception:
        if LOCAL_DATA_FILE.exists():
            return json.loads(LOCAL_DATA_FILE.read_text(encoding="utf-8"))
        return {}


def _save(data: dict) -> None:
    from googleapiclient.http import MediaInMemoryUpload
    try:
        service = _get_drive_service()
        file_id = _find_or_create_file(service)
        content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        media = MediaInMemoryUpload(content, mimetype="application/json")
        service.files().update(fileId=file_id, media_body=media).execute()
    except Exception:
        LOCAL_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_DATA_FILE.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )


def get_checked_dates(habit: str) -> set[str]:
    """Return set of ISO date strings where habit was checked."""
    return set(_load().get(habit, []))


def toggle(habit: str, date_str: str) -> bool:
    """Toggle a date for a habit. Returns new state (True=checked)."""
    data = _load()
    dates = set(data.get(habit, []))
    if date_str in dates:
        dates.discard(date_str)
        checked = False
    else:
        dates.add(date_str)
        checked = True
    data[habit] = sorted(dates)
    _save(data)
    return checked
