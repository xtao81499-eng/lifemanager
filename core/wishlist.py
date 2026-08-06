"""
购物清单 / 存钱目标追踪 — Google Drive JSON persistence.

Stores 'lifemanager_wishlist.json' in the user's Google Drive.
Falls back to local data/wishlist.json if Drive is unavailable.
"""
import base64
import json
import uuid
from datetime import date
from io import BytesIO
from pathlib import Path

from PIL import Image

DRIVE_FILENAME = "lifemanager_wishlist.json"
LOCAL_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "wishlist.json"

_drive_file_id: str | None = None


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
    empty = json.dumps({"items": []}, ensure_ascii=False).encode("utf-8")
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
        return {"items": []}


def _save(data: dict) -> None:
    from googleapiclient.http import MediaInMemoryUpload
    LOCAL_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_DATA_FILE.write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    try:
        service = _get_drive_service()
        file_id = _find_or_create_file(service)
        content = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        media = MediaInMemoryUpload(content, mimetype="application/json")
        service.files().update(fileId=file_id, media_body=media).execute()
    except Exception:
        pass


def _compress_image(image_bytes: bytes, max_width: int = 200) -> str:
    img = Image.open(BytesIO(image_bytes))
    if img.mode == "RGBA":
        img = img.convert("RGB")
    ratio = max_width / img.width
    new_size = (max_width, int(img.height * ratio))
    img = img.resize(new_size, Image.LANCZOS)
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=75)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def load_items() -> list[dict]:
    return _load().get("items", [])


def add_item(name: str, image_bytes: bytes | None, target: float) -> dict:
    data = _load()
    item = {
        "id": str(uuid.uuid4())[:8],
        "name": name,
        "image": _compress_image(image_bytes) if image_bytes else "",
        "target": target,
        "saved": 0,
        "history": [],
    }
    data.setdefault("items", []).append(item)
    _save(data)
    return item


def add_savings(item_id: str, amount: float) -> dict | None:
    data = _load()
    for item in data.get("items", []):
        if item["id"] == item_id:
            item["saved"] = max(0, item.get("saved", 0) + amount)
            item.setdefault("history", []).append({
                "date": str(date.today()),
                "amount": amount,
            })
            _save(data)
            return item
    return None


def remove_item(item_id: str) -> None:
    data = _load()
    data["items"] = [i for i in data.get("items", []) if i["id"] != item_id]
    _save(data)


def update_image(item_id: str, image_bytes: bytes) -> None:
    data = _load()
    for item in data.get("items", []):
        if item["id"] == item_id:
            item["image"] = _compress_image(image_bytes)
            _save(data)
            return
