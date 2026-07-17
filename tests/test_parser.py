"""
单元测试：验证事件标题解析器的各种格式。
不依赖 Google API，可直接运行。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.parser import parse_event_title


def test_parser():
    test_cases = [
        ("[工作] 调试蓝牙模块 7.5/10", "工作", "调试蓝牙模块", 7.5),
        ("[学习] 深度复盘 (8.5/10)", "学习", "深度复盘", 8.5),
        ("[健身] 跑步5km", "健身", "跑步5km", None),
        ("09:00-10:00 [工作] 写周报 6/10", "工作", "写周报", 6.0),
        ("[睡眠] 23:00-07:00", "睡眠", "23:00-07:00", None),
        ("随便写的没有分类", "未分类", "随便写的没有分类", None),
        ("[复盘] 本周回顾（9/10）", "复盘", "本周回顾", 9.0),
    ]

    print("解析器单元测试\n")
    passed = 0
    for title, exp_cat, exp_task, exp_score in test_cases:
        result = parse_event_title(title)
        ok = (
            result.category == exp_cat
            and result.task == exp_task
            and result.score == exp_score
        )
        status = "✅" if ok else "❌"
        print(f"  {status} {title}")
        if not ok:
            print(f"     期望: cat={exp_cat}, task={exp_task}, score={exp_score}")
            print(f"     实际: cat={result.category}, task={result.task}, score={result.score}")
        else:
            passed += 1

    print(f"\n结果: {passed}/{len(test_cases)} 通过")
    return passed == len(test_cases)


if __name__ == "__main__":
    success = test_parser()
    sys.exit(0 if success else 1)
