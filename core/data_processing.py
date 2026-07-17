"""
数据处理层：将 Google Calendar 事件转为结构化 DataFrame
"""
import pandas as pd
from datetime import datetime

from core.parser import parse_event_title


def events_to_dataframe(events: list[dict]) -> pd.DataFrame:
    """将原始事件列表转为带解析字段的 DataFrame。"""
    rows = []
    for event in events:
        title = event.get("summary", "")
        if not title:
            continue

        parsed = parse_event_title(title)

        start_raw = event.get("start", {})
        end_raw = event.get("end", {})
        start_str = start_raw.get("dateTime", start_raw.get("date", ""))
        end_str = end_raw.get("dateTime", end_raw.get("date", ""))

        try:
            start_dt = pd.to_datetime(start_str)
            end_dt = pd.to_datetime(end_str)
            duration_hours = (end_dt - start_dt).total_seconds() / 3600
        except Exception:
            start_dt = None
            end_dt = None
            duration_hours = 0

        calendar_name = event.get("_calendar_name", "")

        rows.append({
            "date": start_dt.date() if start_dt else None,
            "start": start_dt,
            "end": end_dt,
            "duration_hours": round(duration_hours, 2),
            "category": parsed.category if parsed.category != "未分类" else calendar_name,
            "task": parsed.task,
            "score": parsed.score,
            "detail": (event.get("description") or "").strip(),
            "raw_title": parsed.raw,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def daily_summary(df: pd.DataFrame) -> pd.DataFrame:
    """按天聚合：每日总时长、平均评分、事件数。"""
    if df.empty:
        return pd.DataFrame()

    scored = df.dropna(subset=["score"])
    daily_score = scored.groupby("date")["score"].mean().rename("avg_score")
    daily_hours = df.groupby("date")["duration_hours"].sum().rename("total_hours")
    daily_count = df.groupby("date")["task"].count().rename("event_count")

    return pd.concat([daily_hours, daily_score, daily_count], axis=1).reset_index()


def category_summary(df: pd.DataFrame) -> pd.DataFrame:
    """按分类聚合：总时长和平均评分。"""
    if df.empty:
        return pd.DataFrame()

    result = df.groupby("category").agg(
        total_hours=("duration_hours", "sum"),
        avg_score=("score", "mean"),
        count=("task", "count"),
    ).reset_index()

    return result.sort_values("total_hours", ascending=False)


def sleep_work_correlation(df: pd.DataFrame) -> pd.DataFrame:
    """计算睡眠时长与次日工作评分的关联数据。"""
    if df.empty:
        return pd.DataFrame()

    sleep = df[df["category"] == "睡眠"].groupby("date").agg(
        sleep_hours=("duration_hours", "sum"),
        sleep_score=("score", "mean"),
    )

    work = df[df["category"] == "工作"].groupby("date").agg(
        work_hours=("duration_hours", "sum"),
        work_score=("score", "mean"),
    )

    # 睡眠日期 +1 天 = 次日工作
    sleep.index = sleep.index + pd.Timedelta(days=1)

    merged = sleep.join(work, how="inner")
    return merged.reset_index()
