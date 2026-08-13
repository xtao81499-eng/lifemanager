"""
日程分类记忆模块 — Few-shot 学习持久化

保存用户对日程分类的修正，作为 few-shot 示例反馈给 Gemini，
逐步提升分类准确率。
"""
import json
from pathlib import Path

DRIVE_FILENAME = "lifemanager_classification_examples.json"
LOCAL_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "classification_examples.json"

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
    empty = json.dumps([], ensure_ascii=False).encode("utf-8")
    media = MediaInMemoryUpload(empty, mimetype="application/json")
    f = service.files().create(
        body={"name": DRIVE_FILENAME, "mimeType": "application/json"},
        media_body=media,
        fields="id",
    ).execute()
    _drive_file_id = f["id"]
    return _drive_file_id


def load_examples() -> list[dict]:
    """加载所有分类示例。返回格式: [{"event": "和爸爸电话", "category": "家庭"}, ...]"""
    try:
        service = _get_drive_service()
        file_id = _find_or_create_file(service)
        content = service.files().get_media(fileId=file_id).execute()
        return json.loads(content.decode("utf-8"))
    except Exception:
        if LOCAL_DATA_FILE.exists():
            return json.loads(LOCAL_DATA_FILE.read_text(encoding="utf-8"))
        return []


def save_examples(examples: list[dict]) -> None:
    """保存分类示例到 Drive + 本地。"""
    from googleapiclient.http import MediaInMemoryUpload

    LOCAL_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCAL_DATA_FILE.write_text(
        json.dumps(examples, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    try:
        service = _get_drive_service()
        file_id = _find_or_create_file(service)
        content = json.dumps(examples, ensure_ascii=False, indent=2).encode("utf-8")
        media = MediaInMemoryUpload(content, mimetype="application/json")
        service.files().update(fileId=file_id, media_body=media).execute()
    except Exception:
        pass


def add_example(event: str, category: str) -> None:
    """添加单个分类示例。"""
    examples = load_examples()
    # 去重：相同 event 只保留最新分类
    examples = [ex for ex in examples if ex["event"] != event]
    examples.append({"event": event, "category": category})
    save_examples(examples)


def add_batch_examples(corrections: list[dict]) -> None:
    """批量添加分类示例。corrections: [{"event": "...", "category": "..."}, ...]"""
    examples = load_examples()
    existing = {ex["event"]: ex for ex in examples}

    for corr in corrections:
        existing[corr["event"]] = corr

    save_examples(list(existing.values()))
