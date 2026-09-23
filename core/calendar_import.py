"""
AI 日程批量导入模块

通过 Gemini Vision API 解析备忘录截图，提取结构化日程数据，
支持用户编辑后批量写入 Google Calendar。

写入策略：按天整日替换——对每个成功解析出日程的日期，先删除绑定日历中
当天所有带起止时间的事件，再写入新日程。解析失败或当天无日程则跳过、不清空。
"""
import base64
import re
from collections import defaultdict
from datetime import datetime, timedelta
from io import BytesIO

import requests
from PIL import Image

from core.auth import get_calendar_service
from core.classification_memory import load_examples

# 11 个固定日程分类
DEFAULT_CATEGORIES = [
    "睡眠", "工作", "餐饮", "运动", "学习",
    "社交", "家庭", "娱乐", "拖延", "通勤", "收拾打扮", "深度复盘/灵感", "潮流穿搭", "其他"
]


def _build_gemini_prompt(few_shot_examples: list[dict]) -> str:
    """构建 Gemini 解析提示词，包含 few-shot 示例。"""
    examples_text = ""
    if few_shot_examples:
        examples_text = "\n\n以下是一些分类示例供参考：\n"
        for ex in few_shot_examples[-20:]:  # 最多取最近 20 个
            examples_text += f"- 事件：{ex['event']} → 分类：{ex['category']}\n"

    prompt = f"""
你是一个日程助手。请解析这张备忘录截图中的日程信息。

格式说明：
- 时间段格式：开始时间-结束时间 事件名称 评分
- 评分是 0-10 的数字（可选）
- 缩进的内容是备注信息，不是独立事件
- 24:00 表示当天结束/第二天00:00

输出要求：
严格按照 JSON 数组格式输出，每个事件包含：
- start_time: 开始时间（HH:MM 格式）
- end_time: 结束时间（HH:MM 格式）
- event: 事件名称
- score: 评分（数字，支持小数如 7.5，无评分则为 null）
- notes: 备注信息（缩进内容，无备注则为空字符串）
- category: 从以下分类中选择最合适的一个：{', '.join(DEFAULT_CATEGORIES)}

分类规则：
- 睡眠：睡觉、午睡、休息
- 工作：工作相关任务、会议、项目
- 餐饮：早中晚餐、吃饭、做饭
- 运动：锻炼、跑步、健身、散步
- 学习：看书、学习、课程、技能训练
- 社交：和朋友聚会、非家人电话/聊天、酒吧、聚餐
- 家庭：和家人通话、家务、陪伴家人
- 娱乐：看电影、打游戏、刷视频、休闲活动
- 拖延：无效时间、发呆、拖延
- 通勤：上下班/出行途中、乘车、开车、步行去某地
- 收拾打扮：洗漱、化妆、换衣服、整理仪容
- 深度复盘/灵感：复盘、日记、反思、总结、灵感记录、冥想、规划
- 潮流穿搭：穿搭、搭配、选衣服、时尚、造型、购物、逛街买衣服
- 其他：不属于以上任何分类

重要：基于语义理解分类，不要只看关键词。例如"午饭吃汉堡王"属于餐饮，因为核心是吃饭。
{examples_text}
只输出 JSON 数组，不要有任何其他文字。
"""
    return prompt


# 已下线，即使 secrets 里写了也要跳过
_RETIRED_GEMINI_MODELS = {
    "gemini-2.0-flash-exp",
    "gemini-2.0-flash",
    "gemini-2.0-flash-001",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-002",
    "gemini-1.5-pro",
}

# 按额度/兼容性优先的 Flash 视觉模型（须出现在 ListModels 结果里才会使用）
_GEMINI_MODEL_CANDIDATES = (
    "gemini-2.5-flash",
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash",
    "gemini-flash-latest",
)

_GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


class _GeminiTextResponse:
    def __init__(self, text: str):
        self.text = text


def _model_id(name: str) -> str:
    return name.replace("models/", "").strip()


def _is_retired_model(name: str) -> bool:
    mid = _model_id(name).lower()
    return mid in _RETIRED_GEMINI_MODELS or "2.0-flash-exp" in mid


def _list_generate_content_models(api_key: str) -> list[str]:
    url = f"{_GEMINI_API_BASE}/models"
    resp = requests.get(url, params={"key": api_key}, timeout=30)
    resp.raise_for_status()
    names = []
    for model in resp.json().get("models", []):
        methods = model.get("supportedGenerationMethods", [])
        if "generateContent" in methods:
            names.append(_model_id(model.get("name", "")))
    return [n for n in names if n]


def _choose_gemini_models(api_key: str, preferred: str) -> list[str]:
    available = _list_generate_content_models(api_key)
    available_set = set(available)
    chosen: list[str] = []

    def add(name: str):
        mid = _model_id(name)
        if not mid or _is_retired_model(mid) or mid in chosen:
            return
        if mid in available_set:
            chosen.append(mid)

    add(preferred)
    for name in _GEMINI_MODEL_CANDIDATES:
        add(name)
    if not chosen:
        for name in available:
            if "flash" in name and "tts" not in name and "image" not in name and not _is_retired_model(name):
                chosen.append(name)
                break
    if not chosen:
        chosen.extend([n for n in available if not _is_retired_model(n)][:3])
    return chosen


def _image_to_inline_part(img) -> dict:
    buf = BytesIO()
    fmt = (img.format or "PNG").upper()
    if fmt == "JPG":
        fmt = "JPEG"
    if fmt not in ("PNG", "JPEG", "WEBP"):
        fmt = "PNG"
    img.save(buf, format=fmt)
    mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[fmt]
    return {
        "inline_data": {
            "mime_type": mime,
            "data": base64.b64encode(buf.getvalue()).decode("ascii"),
        }
    }


def _extract_gemini_text(payload: dict) -> str:
    candidates = payload.get("candidates") or []
    if not candidates:
        raise RuntimeError(f"Gemini 返回空结果: {payload}")
    parts = candidates[0].get("content", {}).get("parts") or []
    texts = [p.get("text", "") for p in parts if p.get("text")]
    text = "\n".join(texts).strip()
    if not text:
        raise RuntimeError(f"Gemini 未返回文本: {payload}")
    return text


def _generate_content_rest(api_key: str, model_name: str, prompt: str, img) -> str:
    url = f"{_GEMINI_API_BASE}/models/{_model_id(model_name)}:generateContent"
    body = {
        "contents": [{
            "role": "user",
            "parts": [
                {"text": prompt},
                _image_to_inline_part(img),
            ],
        }]
    }
    resp = requests.post(url, params={"key": api_key}, json=body, timeout=120)
    if resp.status_code in (404, 400) and _is_model_unavailable_text(resp.text):
        raise LookupError(resp.text)
    if not resp.ok:
        raise RuntimeError(f"Gemini HTTP {resp.status_code}: {resp.text[:500]}")
    return _extract_gemini_text(resp.json())


def _is_model_unavailable_text(msg: str) -> bool:
    lower = msg.lower()
    return (
        "404" in lower
        or "not_found" in lower
        or "not found" in lower
        or "is not supported" in lower
        or "not available" in lower
    )


def _generate_with_available_model(prompt, img, api_key: str, st, os):
    """Call generateContent over REST, using a live model from ListModels."""
    preferred = ""
    try:
        preferred = str(st.secrets.get("GEMINI_MODEL", "") or "").strip()
    except Exception:
        preferred = ""
    if not preferred:
        preferred = (os.getenv("GEMINI_MODEL") or "").strip()

    last_error = None
    tried: list[str] = []
    try:
        candidates = _choose_gemini_models(api_key, preferred)
    except Exception as e:
        raise RuntimeError(f"无法列出 Gemini 模型: {e}") from e

    if not candidates:
        raise RuntimeError("ListModels 未返回任何可用的 generateContent 模型")

    for model_name in candidates:
        tried.append(model_name)
        try:
            text = _generate_content_rest(api_key, model_name, prompt, img)
            return _GeminiTextResponse(text)
        except LookupError as e:
            last_error = e
            continue
        except Exception as e:
            last_error = e
            if _is_model_unavailable_text(str(e)):
                continue
            raise

    raise RuntimeError(
        f"没有可用的 Gemini 模型（已尝试: {', '.join(tried)}）。最后错误: {last_error}"
    ) from last_error


def parse_schedule_screenshot(image_bytes: bytes, schedule_date: str) -> list[dict]:
    """
    解析备忘录截图，返回结构化日程列表。

    Args:
        image_bytes: 图片字节数据
        schedule_date: 日程日期（YYYY-MM-DD）

    Returns:
        [{"start": "2026-08-13T08:00:00", "end": "2026-08-13T09:00:00",
          "event": "晨练", "score": 8, "notes": "跑步5km", "category": "运动"}, ...]
    """
    # 加载 few-shot 示例
    examples = load_examples()

    # 配置 Gemini
    import os
    import streamlit as st

    api_key = st.secrets.get("GEMINI_API_KEY", os.getenv("GEMINI_API_KEY", ""))
    if not api_key:
        raise ValueError("未配置 GEMINI_API_KEY，请在 secrets.toml 中添加")

    # 压缩图片（避免超出 API 限制）
    img = Image.open(BytesIO(image_bytes))
    if img.width > 1024:
        ratio = 1024 / img.width
        new_size = (1024, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    prompt = _build_gemini_prompt(examples)
    response = _generate_with_available_model(prompt, img, api_key, st, os)

    # 解析 JSON 响应
    import json
    text = response.text.strip()
    # 移除可能的 markdown 代码块标记
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*$", "", text)

    parsed = json.loads(text)

    # 转换为标准格式，处理时间规范化
    base_date = datetime.strptime(schedule_date, "%Y-%m-%d")
    events = []

    for item in parsed:
        start_dt = _normalize_datetime(base_date, item["start_time"])
        end_dt = _normalize_datetime(base_date, item["end_time"])

        # 处理跨午夜情况
        if end_dt <= start_dt:
            end_dt += timedelta(days=1)

        events.append({
            "start": start_dt.isoformat(),
            "end": end_dt.isoformat(),
            "event": item["event"],
            "score": item.get("score"),
            "notes": item.get("notes", ""),
            "category": item.get("category", "其他"),
        })

    return events


def _normalize_datetime(base_date: datetime, time_str: str) -> datetime:
    """将时间字符串（HH:MM）转换为 datetime，处理 24:00 特殊情况。"""
    hour, minute = map(int, time_str.split(":"))

    if hour == 24:
        # 24:00 = 次日 00:00
        return base_date + timedelta(days=1, hours=0, minutes=minute)

    return base_date.replace(hour=hour, minute=minute, second=0, microsecond=0)


def _parse_event_datetime(value: str) -> datetime:
    """Parse Google Calendar dateTime, stripping a trailing Asia/Shanghai offset if present."""
    return datetime.fromisoformat(value.replace("+08:00", "").replace("Z", ""))


def _delete_timed_events_for_day(
    service,
    day_date: str,
    all_calendar_ids: list[str],
    log_callback=None,
) -> int:
    """
    整日替换的删除阶段：删除所有日历中与当天 [00:00, 次日 00:00) 时间重叠的带钟点事件。

    - 跳过全天事件（只有 start.date / end.date，无 dateTime）
    - 跨天旧事件：整条删除
    - 重复事件：list 使用 singleEvents=True，删除展开后的实例 ID = 只取消当天这一次
    - 若解析未产出任何日程，调用方不应调用本函数（不清空）

    Args:
        service: Google Calendar API service
        day_date: YYYY-MM-DD（按 Asia/Shanghai 当天视图理解）
        all_calendar_ids: 要扫描的日历 ID 列表
        log_callback: 可选日志回调

    Returns:
        成功删除的事件数量
    """
    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    day_start = datetime.strptime(day_date, "%Y-%m-%d")
    day_end = day_start + timedelta(days=1)
    # Google Calendar API 要求 RFC3339；与写入时区一致
    query_start = day_start.strftime("%Y-%m-%dT00:00:00+08:00")
    query_end = day_end.strftime("%Y-%m-%dT00:00:00+08:00")

    events_to_delete = []  # [(cal_id, event_id, summary, time_range), ...]
    seen_ids: set[tuple[str, str]] = set()

    for cal_id in all_calendar_ids:
        try:
            page_token = None
            while True:
                events_result = service.events().list(
                    calendarId=cal_id,
                    timeMin=query_start,
                    timeMax=query_end,
                    singleEvents=True,
                    orderBy="startTime",
                    pageToken=page_token,
                ).execute()

                for evt in events_result.get("items", []):
                    evt_start = evt.get("start", {}).get("dateTime")
                    evt_end = evt.get("end", {}).get("dateTime")

                    # 全天事件：保留不删
                    if not evt_start or not evt_end:
                        continue

                    evt_start_dt = _parse_event_datetime(evt_start)
                    evt_end_dt = _parse_event_datetime(evt_end)

                    # 与当天窗口有任何时间重叠则整条删除
                    if evt_end_dt > day_start and evt_start_dt < day_end:
                        event_id = evt.get("id")
                        if not event_id or not cal_id:
                            continue
                        key = (cal_id, event_id)
                        if key in seen_ids:
                            continue
                        seen_ids.add(key)
                        events_to_delete.append((
                            cal_id,
                            event_id,
                            evt.get("summary", "未知"),
                            f"{evt_start[:16]} - {evt_end[11:16]}",
                        ))

                page_token = events_result.get("nextPageToken")
                if not page_token:
                    break

        except Exception as e:
            error_msg = str(e)
            if "403" not in error_msg and "404" not in error_msg:
                log(f"⚠️ 查询日历失败 (跳过): {error_msg[:50]}")
            continue

    if events_to_delete:
        log(f"📋 {day_date} 发现 {len(events_to_delete)} 个带时间事件待删除（整日替换）")
    else:
        log(f"✓ {day_date} 当天无带时间旧事件")

    deleted_count = 0
    for cal_id, event_id, summary, time_range in events_to_delete:
        try:
            service.events().delete(calendarId=cal_id, eventId=event_id).execute()
            deleted_count += 1
            log(f"✓ 已删除: {summary} ({time_range})")
        except Exception as e:
            error_msg = str(e)
            if "403" not in error_msg and "404" not in error_msg and "410" not in error_msg:
                log(f"✗ 删除失败: {summary} - {error_msg[:50]}")

    if events_to_delete:
        log(f"🗑️ {day_date} 删除完成: 成功 {deleted_count}/{len(events_to_delete)} 个")
    return deleted_count


def insert_events_batch(events: list[dict], calendar_mapping: dict[str, str], log_callback=None) -> int:
    """
    按天整日替换后批量写入 Google Calendar。

    对每个出现在 events 中的日期：先清空绑定账号下各日历当天的带时间事件，
    再写入该日的新日程。某日若没有任何事件（例如解析失败未纳入列表），则跳过、不清空。
    同一天多批事件若合并进本列表，以列表内容为准（后解析的图应覆盖前图时，
    由调用方保证只保留最后一张图的结果）。

    Args:
        events: 事件列表（parse_schedule_screenshot 返回格式）
        calendar_mapping: 分类到日历 ID 的映射 {"睡眠": "cal_id_1", ...}
        log_callback: 可选的日志回调函数，用于输出日志到 UI

    Returns:
        成功写入的事件数量
    """
    service = get_calendar_service()
    success_count = 0

    def log(msg):
        if log_callback:
            log_callback(msg)
        else:
            print(msg)

    if not events:
        log("✓ 无日程可写入，跳过（不清空任何日期）")
        return 0

    from core.calendar_sync import list_calendars
    all_calendars = list_calendars()
    all_calendar_ids = [cal["id"] for cal in all_calendars]

    # 按日期分组；保持首次出现的日期顺序
    events_by_day: dict[str, list[dict]] = defaultdict(list)
    day_order: list[str] = []
    for event in events:
        day = event["start"].split("T")[0]
        if day not in events_by_day:
            day_order.append(day)
        events_by_day[day].append(event)

    for day in day_order:
        day_events = events_by_day[day]
        if not day_events:
            continue

        log(f"\n📅 整日替换: {day}（{len(day_events)} 条新日程）")
        _delete_timed_events_for_day(service, day, all_calendar_ids, log_callback)

        for event in day_events:
            category = event.get("category", "其他")
            calendar_id = calendar_mapping.get(category, "primary")

            summary = event["event"]
            if event.get("score") is not None:
                summary = f"{summary} {event['score']}/10"

            body = {
                "summary": summary,
                "description": event.get("notes", ""),
                "start": {"dateTime": event["start"], "timeZone": "Asia/Shanghai"},
                "end": {"dateTime": event["end"], "timeZone": "Asia/Shanghai"},
            }

            try:
                service.events().insert(calendarId=calendar_id, body=body).execute()
                success_count += 1
                log(f"✅ 已写入: {event['event']} ({event['start'][11:16]}-{event['end'][11:16]})")
            except Exception as e:
                log(f"❌ 写入失败: {event['event']} - {str(e)[:50]}")
                continue

    return success_count


def list_calendar_categories() -> dict[str, str]:
    """
    列出所有日历作为分类选项。

    Returns:
        {"日历名称": "calendar_id", ...}
    """
    from core.calendar_sync import list_calendars
    calendars = list_calendars()
    return {cal["summary"]: cal["id"] for cal in calendars}


def create_calendar_category(name: str, color_id: str = "1") -> str:
    """
    创建新的日历分类。

    Args:
        name: 日历名称
        color_id: 颜色 ID（1-24，Google Calendar 预定义颜色）

    Returns:
        新建日历的 ID
    """
    service = get_calendar_service()
    calendar = {
        "summary": name,
        "timeZone": "Asia/Shanghai",
    }
    created = service.calendars().insert(body=calendar).execute()

    # 设置颜色
    service.calendarList().update(
        calendarId=created["id"],
        body={"colorId": color_id}
    ).execute()

    return created["id"]
