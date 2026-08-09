"""
周复盘 KISS 模块 — Keep / Improve / Start / Stop

基于本周数据自动生成 KISS 四象限内容，支持用户手动编辑覆盖。
Google Drive JSON 持久化。
"""
import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

DRIVE_FILENAME = "lifemanager_weekly_review.json"
LOCAL_DATA_FILE = Path(__file__).resolve().parent.parent / "data" / "weekly_review.json"

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


def week_key(d: date | None = None) -> str:
    d = d or date.today()
    iso = d.isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def get_review(wk: str | None = None) -> dict | None:
    wk = wk or week_key()
    data = _load()
    return data.get(wk)


def save_review(review: dict, wk: str | None = None) -> None:
    wk = wk or week_key()
    data = _load()
    data[wk] = review
    _save(data)


def generate_kiss(df: pd.DataFrame, habit_data: dict | None = None) -> dict:
    """
    从本周 DataFrame 自动生成 KISS 四象限。
    df: 本周事件数据（含 category, score, duration_hours, date 列）
    habit_data: {"habit_name": ["date1", ...]} 手动习惯打卡数据
    """
    keep = []
    improve = []
    start = []
    stop = []

    if df.empty:
        return {"keep": ["暂无数据"], "improve": ["暂无数据"], "start": ["开始记录日程"], "stop": ["暂无数据"]}

    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_dates = set((week_start + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7))

    # --- KEEP: high-score categories, consistent habits ---
    cat_scores = df.groupby("category")["score"].mean().dropna()
    high_cats = cat_scores[cat_scores >= 7.5].sort_values(ascending=False)
    for cat in high_cats.index[:2]:
        keep.append(f"{cat}表现优秀 (均分{high_cats[cat]:.1f})")

    if habit_data:
        for habit, dates in habit_data.items():
            week_hits = len(set(dates) & week_dates)
            if week_hits >= 5:
                keep.append(f"{habit}坚持良好 ({week_hits}/7天)")

    if not keep:
        keep.append("继续保持当前节奏")

    # --- IMPROVE: below-average categories ---
    overall_avg = cat_scores.mean() if not cat_scores.empty else 5.0
    low_cats = cat_scores[cat_scores < overall_avg - 0.5].sort_values()
    for cat in low_cats.index[:2]:
        improve.append(f"{cat}评分偏低 (均分{low_cats[cat]:.1f})，尝试优化")

    cat_hours = df.groupby("category")["duration_hours"].sum()
    if "拖延" in cat_hours.index and cat_hours["拖延"] > 2:
        improve.append(f"拖延时间较多 ({cat_hours['拖延']:.1f}h)，减少无效时间")

    if not improve:
        improve.append("各项均衡，保持即可")

    # --- START: low-activity areas worth trying ---
    if habit_data:
        for habit, dates in habit_data.items():
            week_hits = len(set(dates) & week_dates)
            if week_hits <= 2:
                start.append(f"加强{habit}打卡 (本周仅{week_hits}天)")

    if "运动" in cat_hours.index:
        if cat_hours["运动"] < 3:
            start.append("增加运动时间 (本周不足3h)")
    elif "运动" not in cat_hours.index:
        start.append("开始规律运动")

    if not start:
        start.append("尝试新的学习方向或技能")

    # --- STOP: time wasters, low-value activities ---
    if "拖延" in cat_hours.index and cat_hours["拖延"] > 1:
        stop.append(f"减少拖延 ({cat_hours['拖延']:.1f}h)")

    low_score_events = df[df["score"].notna() & (df["score"] <= 4)]
    if not low_score_events.empty:
        worst = low_score_events.groupby("category")["duration_hours"].sum().sort_values(ascending=False)
        for cat in worst.index[:1]:
            if cat != "拖延":
                stop.append(f"减少低效{cat}时间")

    if not stop:
        stop.append("暂无需要停止的事项")

    return {
        "keep": keep[:3],
        "improve": improve[:3],
        "start": start[:3],
        "stop": stop[:3],
    }
