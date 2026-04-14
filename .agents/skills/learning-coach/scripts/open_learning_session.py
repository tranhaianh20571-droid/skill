from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = SKILL_ROOT / "assets" / "templates"


def ensure_file(path: Path, template_name: str, topic: str) -> None:
    if path.exists():
        return
    text = (TEMPLATE_DIR / template_name).read_text(encoding="utf-8")
    text = text.replace("{{TODAY}}", date.today().isoformat())
    text = text.replace("{{TOPIC}}", topic)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def format_list(items: list[str], empty_text: str = "待补充") -> str:
    if not items:
        return f"- {empty_text}"
    return "\n".join(f"- {item}" for item in items)


def load_protocol(planning_dir: Path) -> dict:
    protocol_path = planning_dir / "learning_protocol.json"
    if not protocol_path.exists():
        return {}
    try:
        return json.loads(protocol_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="打开并对齐当前学习会话。")
    parser.add_argument("--root", required=True, help="项目或笔记根目录")
    parser.add_argument(
        "--planning-dir",
        default=".codex/planning",
        help="相对于根目录的规划文件目录",
    )
    parser.add_argument("--topic", default="当前学习主题", help="当前学习主题")
    parser.add_argument("--scene", default="", help="当前学习场景")
    parser.add_argument("--goal", default="", help="当前轮次的学习目标")
    parser.add_argument(
        "--granularity",
        default="",
        help="讲解颗粒度，例如 粗粒度 / 中粒度 / 细粒度",
    )
    parser.add_argument(
        "--focus",
        action="append",
        default=[],
        help="当前最重要的重点，可重复传入",
    )
    parser.add_argument(
        "--material",
        action="append",
        default=[],
        help="本轮学习使用的材料，可重复传入",
    )
    parser.add_argument(
        "--non-goal",
        action="append",
        default=[],
        help="当前场景暂不展开的内容，可重复传入",
    )
    parser.add_argument(
        "--question",
        action="append",
        default=[],
        help="当前仍需和用户确认的问题，可重复传入",
    )
    parser.add_argument(
        "--multi-teacher",
        default="auto",
        choices=["auto", "on", "off"],
        help="多老师模式偏好：auto / on / off",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    planning_dir = (root / args.planning_dir).resolve()
    planning_dir.mkdir(parents=True, exist_ok=True)

    ensure_file(planning_dir / "learner_profile.md", "learner_profile.md", args.topic)
    ensure_file(planning_dir / "learning_protocol.md", "learning_protocol.md", args.topic)
    ensure_file(planning_dir / "session_brief.md", "session_brief.md", args.topic)
    ensure_file(planning_dir / "grounding_log.md", "grounding_log.md", args.topic)
    ensure_file(planning_dir / "adjustment_log.md", "adjustment_log.md", args.topic)
    ensure_file(planning_dir / "issue_log.md", "issue_log.md", args.topic)
    ensure_file(planning_dir / "coverage_map.md", "coverage_map.md", args.topic)
    ensure_file(planning_dir / "agent_team.md", "agent_team.md", args.topic)
    protocol = load_protocol(planning_dir)

    missing_questions: list[str] = []
    if not protocol:
        missing_questions.append("这套学习系统还没有完成初始协议配置。先确认：什么算一块内容、几块后测试、每次几题、什么时候停下来确认。")
    else:
        missing_questions.extend(protocol.get("missing_questions", []))
    if not args.scene:
        missing_questions.append("这轮学习当前处于什么场景？是搭框架、精读材料、面试表达，还是补薄弱点？")
    if not args.goal:
        missing_questions.append("这轮学习最想解决什么问题，学完后希望能做到什么？")
    if not args.material:
        missing_questions.append("这轮学习准备依托哪些材料？")
    if not args.granularity:
        missing_questions.append("你希望我讲多细？先抓框架、正常细讲，还是逐句逐点拆？")
    if not args.focus:
        missing_questions.append("这轮你最看重哪些重点？")

    remaining_questions = args.question + missing_questions

    session_brief = f"""# 当前学习会话

主题：{args.topic}
日期：{date.today().isoformat()}

## 当前场景

{args.scene or "待和用户确认"}

## 当前目标

{args.goal or "待和用户确认"}

## 当前资料

{format_list(args.material, "待补充资料")}

## 讲解颗粒度

{args.granularity or "待和用户确认"}

## 当前重点

{format_list(args.focus, "待和用户确认重点")}

## 当前非目标

{format_list(args.non_goal, "暂未定义")}

## 多老师模式

- 偏好：{args.multi_teacher}
- 说明：只有在任务复杂、材料多、或需要讲解/出题/复盘分工时才建议开启。

## 当前学习协议

- 主动带学：{protocol.get("proactive_guidance", "待确认")}
- 一块内容的定义：{protocol.get("chunk_definition", "待确认")}
- 每块默认规模：{protocol.get("chunk_size", "待确认")}
- 过程测验触发：{protocol.get("process_quiz_every", "待确认")}
- 过程测验题量：{protocol.get("process_quiz_count", "待确认")}
- 阶段测试触发：{protocol.get("checkpoint_rule", "待确认")}
- 阶段测试题量：{protocol.get("checkpoint_quiz_count", "待确认")}
- 停下来确认的时机：{protocol.get("confirmation_rule", "待确认")}

## 材料依据规则

- 优先基于本轮资料讲解和出题。
- 只有在“不补充就学不懂当前材料”时，才做必要补充。
- 如果做了补充，要记录补充内容和必要性。

## 待确认问题

{format_list(remaining_questions, "当前已完成基本对齐")}
"""

    session_brief_path = planning_dir / "session_brief.md"
    session_brief_path.write_text(session_brief, encoding="utf-8")
    print(f"[写入] {session_brief_path}")

    print()
    print("建议的开场对齐问题：")
    if remaining_questions:
        for index, question in enumerate(remaining_questions, start=1):
            print(f"{index}. {question}")
    else:
        print("1. 当前轮次已完成基本对齐，可以开始讲解。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
