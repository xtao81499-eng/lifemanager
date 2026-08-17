"""
AI 日程批量导入模块

通过 Gemini Vision API 解析备忘录截图，提取结构化日程数据，
支持用户编辑后批量写入 Google Calendar。
"""
import re
from datetime import datetime, timedelta
from io import BytesIO

import google.generativeai as genai
from PIL import Image

from core.auth import get_calendar_service
from core.classification_memory import load_examples

# 10 个固定日程分类
DEFAULT_CATEGORIES = [
    "睡眠", "工作", "餐饮", "运动", "学习",
    "社交", "家庭", "娱乐", "拖延", "其他"
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
- score: 评分（整数，无评分则为 null）
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
- 其他：不属于以上任何分类

重要：基于语义理解分类，不要只看关键词。例如"午饭吃汉堡王"属于餐饮，因为核心是吃饭。
{examples_text}
只输出 JSON 数组，不要有任何其他文字。
"""
    return prompt


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

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-3.6-flash")

    # 压缩图片（避免超出 API 限制）
    img = Image.open(BytesIO(image_bytes))
    if img.width > 1024:
        ratio = 1024 / img.width
        new_size = (1024, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)

    # 调用 Gemini Vision API
    prompt = _build_gemini_prompt(examples)
    response = model.generate_content([prompt, img])

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


def insert_events_batch(events: list[dict], calendar_mapping: dict[str, str]) -> int:
    """
    批量写入事件到 Google Calendar。

    Args:
        events: 事件列表（parse_schedule_screenshot 返回格式）
        calendar_mapping: 分类到日历 ID 的映射 {"睡眠": "cal_id_1", ...}

    Returns:
        成功写入的事件数量
    """
    service = get_calendar_service()
    success_count = 0

    for event in events:
        category = event.get("category", "其他")
        calendar_id = calendar_mapping.get(category, "primary")

        # 构建事件体
        body = {
            "summary": event["event"],
            "description": event.get("notes", ""),
            "start": {"dateTime": event["start"], "timeZone": "Asia/Shanghai"},
            "end": {"dateTime": event["end"], "timeZone": "Asia/Shanghai"},
        }

        # 添加评分到描述
        if event.get("score") is not None:
            score_line = f"\n\n评分: {event['score']}/10"
            body["description"] = (body["description"] + score_line).strip()

        try:
            service.events().insert(calendarId=calendar_id, body=body).execute()
            success_count += 1
        except Exception as e:
            print(f"写入事件失败: {event['event']} - {e}")
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
