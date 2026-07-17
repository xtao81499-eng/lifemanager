"""
事件标题解析器
支持格式:
  [分类] 任务描述 (评分/10)
  [分类] 任务描述 评分/10
  09:00-10:00 [分类] 任务描述 7.5/10
"""
import re
from dataclasses import dataclass


@dataclass
class ParsedEvent:
    category: str
    task: str
    score: float | None
    raw: str


# 匹配 [中文/英文分类]
CATEGORY_PATTERN = re.compile(r"\[([^\]]+)\]")
# 匹配评分: 7.5/10, (8/10), （8.5/10）
SCORE_PATTERN = re.compile(r"[（(]?\s*(\d+(?:\.\d+)?)\s*/\s*10\s*[）)]?")
# 匹配时间前缀: 09:00-10:00
TIME_PREFIX_PATTERN = re.compile(r"^\d{1,2}:\d{2}\s*[-–]\s*\d{1,2}:\d{2}\s*")


def parse_event_title(title: str) -> ParsedEvent:
    """解析日历事件标题，提取分类、任务名和评分。"""
    raw = title
    working = title.strip()

    # 移除时间前缀
    working = TIME_PREFIX_PATTERN.sub("", working)

    # 提取分类
    cat_match = CATEGORY_PATTERN.search(working)
    category = cat_match.group(1) if cat_match else "未分类"
    if cat_match:
        working = working[: cat_match.start()] + working[cat_match.end() :]

    # 提取评分
    score_match = SCORE_PATTERN.search(working)
    score = float(score_match.group(1)) if score_match else None
    if score_match:
        working = working[: score_match.start()] + working[score_match.end() :]

    task = working.strip()

    return ParsedEvent(category=category, task=task, score=score, raw=raw)
