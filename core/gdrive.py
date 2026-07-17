"""
Google Drive 文档读取模块
从指定文件夹获取最新文档，导出为纯文本。
"""
import os
import re
from datetime import date

from core.auth import get_drive_service

FOLDER_ID = os.getenv("GDRIVE_REFLECTION_FOLDER_ID", "")


def fetch_latest_doc(folder_id: str = "") -> dict | None:
    """获取指定文件夹中按修改时间排序的最新 Google Docs 文档，返回 {title, text, date}。"""
    fid = folder_id or FOLDER_ID
    if not fid:
        return None

    service = get_drive_service()

    results = (
        service.files()
        .list(
            q=f"'{fid}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false",
            orderBy="modifiedTime desc",
            pageSize=1,
            fields="files(id, name, modifiedTime)",
        )
        .execute()
    )

    files = results.get("files", [])
    if not files:
        return None

    doc = files[0]
    text = (
        service.files()
        .export(fileId=doc["id"], mimeType="text/plain")
        .execute()
        .decode("utf-8")
    )

    mod_date = doc.get("modifiedTime", "")[:10]

    return {"title": doc["name"], "text": text, "date": mod_date}


def extract_suggestions(text: str) -> list[str]:
    """从文档文本中提取「建议」「改进方案」「行动项」等条目。"""
    suggestions: list[str] = []

    section_pattern = re.compile(
        r"(?:建议|改进方案|改进|行动项|Action\s*Items?|Suggestions?|下一步|改善措施|优化方向|待改进|反思要点)[：:\s]*\n([\s\S]*?)(?=\n[^\s\-•·\d]|\Z)",
        re.IGNORECASE,
    )

    for m in section_pattern.finditer(text):
        block = m.group(1)
        items = re.findall(
            r"[-•·\*]?\s*\d*[\.、）)]?\s*(.+)",
            block,
        )
        suggestions.extend(item.strip() for item in items if item.strip())

    if not suggestions:
        bullet_pattern = re.compile(
            r"(?:[-•·\*]|\d+[\.、）)])\s*(.+(?:建议|改进|优化|提升|注意|避免|尝试|调整|坚持).+)",
        )
        suggestions = [m.strip() for m in bullet_pattern.findall(text) if m.strip()]

    seen = set()
    deduped = []
    for s in suggestions:
        if s not in seen:
            seen.add(s)
            deduped.append(s)

    return deduped


def get_reflection_insights(folder_id: str = "") -> dict:
    """
    主入口：获取最新反思文档并提取建议。
    返回 {"title": str, "date": str, "suggestions": list[str], "is_today": bool}
    """
    doc = fetch_latest_doc(folder_id)
    if not doc:
        return {"title": "", "date": "", "suggestions": [], "is_today": False}

    suggestions = extract_suggestions(doc["text"])
    is_today = doc["date"] == str(date.today())

    return {
        "title": doc["title"],
        "date": doc["date"],
        "suggestions": suggestions,
        "is_today": is_today,
    }
