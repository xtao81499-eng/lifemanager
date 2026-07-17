"""
测试脚本：验证 Google Calendar API 认证 + 事件抓取 + 解析的完整流程。

使用方法:
  1. 将 credentials.json 放到 config/ 目录
  2. pip install -r requirements.txt
  3. python test_fetch.py

首次运行会打开浏览器完成 OAuth 授权。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from core.calendar_sync import fetch_all_events, list_calendars
from core.parser import parse_event_title


def main():
    print("=" * 60)
    print("  Life Manager — Google Calendar 连接测试")
    print("=" * 60)
    print()

    print("[1/3] 正在认证并获取所有日历...")
    try:
        calendars = list_calendars()
        print(f"  发现 {len(calendars)} 个日历:")
        for cal in calendars:
            print(f"    - {cal.get('summary', '未知')}")
        print()
        events = fetch_all_events(days=7)
    except FileNotFoundError as e:
        print(f"\n❌ 认证失败: {e}")
        return
    except Exception as e:
        print(f"\n❌ API 调用失败: {e}")
        return

    print(f"✅ 获取到 {len(events)} 条事件\n")

    if not events:
        print("⚠️  最近7天没有日历事件。请确认日历中有数据。")
        return

    print("[2/3] 解析事件标题...\n")
    print(f"{'分类':<8} {'评分':<6} {'任务'}")
    print("-" * 60)

    parsed_events = []
    for event in events:
        title = event.get("summary", "")
        if not title:
            continue
        parsed = parse_event_title(title)
        parsed_events.append(parsed)

        score_str = f"{parsed.score}/10" if parsed.score else "—"
        print(f"[{parsed.category:<6}] {score_str:<6} {parsed.task}")

    print()
    print("[3/3] 数据统计摘要\n")

    # 分类统计
    categories = {}
    scores = []
    for p in parsed_events:
        categories[p.category] = categories.get(p.category, 0) + 1
        if p.score is not None:
            scores.append(p.score)

    print("分类分布:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"  [{cat}] × {count}")

    if scores:
        avg = sum(scores) / len(scores)
        print(f"\n评分统计: 平均 {avg:.1f}/10 | 最高 {max(scores)}/10 | 最低 {min(scores)}/10")
        print(f"有评分事件: {len(scores)}/{len(parsed_events)}")

    print("\n" + "=" * 60)
    print("✅ 流程验证完成！可以开始构建 Dashboard 了。")


if __name__ == "__main__":
    main()
