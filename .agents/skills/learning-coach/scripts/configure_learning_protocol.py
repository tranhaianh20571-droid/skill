from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = SKILL_ROOT / "assets" / "templates"


def render_template(template_name: str, topic: str) -> str:
    text = (TEMPLATE_DIR / template_name).read_text(encoding="utf-8")
    return text.replace("{{TODAY}}", date.today().isoformat()).replace("{{TOPIC}}", topic)


def protocol_questions(args: argparse.Namespace) -> list[str]:
    questions: list[str] = []
    if not args.chunk_definition:
        questions.append("对你来说，什么算一块内容？是一个概念、一个功能点、一段材料，还是固定时长？")
    if not args.chunk_size:
        questions.append("每一块希望讲到什么规模？例如 1 个核心概念、2 段材料、还是 10 分钟左右。")
    if not args.process_quiz_every:
        questions.append("你希望学几块之后做一次过程测验？每 1 块、每 2 块，还是不固定？")
    if args.process_quiz_count is None:
        questions.append("过程测验每次大概几题更合适？")
    if not args.checkpoint_rule:
        questions.append("阶段测试希望按什么触发？每阶段一次，还是每 3 到 5 块一次？")
    if args.checkpoint_quiz_count is None:
        questions.append("阶段测试每次大概几题更合适？")
    if not args.confirmation_rule:
        questions.append("你希望我什么时候停下来和你确认？每块后、只有转场时、还是只在你困惑时？")
    return questions


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="配置学习协议。")
    parser.add_argument("--root", required=True, help="项目或笔记根目录")
    parser.add_argument(
        "--planning-dir",
        default=".codex/planning",
        help="相对于根目录的规划文件目录",
    )
    parser.add_argument("--topic", default="当前学习主题", help="当前学习主题")
    parser.add_argument(
        "--proactive-guidance",
        default="on",
        choices=["on", "off", "mixed"],
        help="是否默认由系统主动带节奏",
    )
    parser.add_argument("--chunk-definition", default="", help="什么算一块内容")
    parser.add_argument("--chunk-size", default="", help="每块内容的默认规模")
    parser.add_argument("--process-quiz-every", default="", help="过程测验触发规则")
    parser.add_argument("--process-quiz-count", type=int, default=None, help="过程测验题量")
    parser.add_argument("--checkpoint-rule", default="", help="阶段测试触发规则")
    parser.add_argument("--checkpoint-quiz-count", type=int, default=None, help="阶段测试题量")
    parser.add_argument("--confirmation-rule", default="", help="什么时候停下来确认")
    parser.add_argument(
        "--quiz-extension-mode",
        default="focused",
        choices=["none", "focused", "light"],
        help="经典题/延伸题策略",
    )
    parser.add_argument(
        "--multi-teacher-default",
        default="auto",
        choices=["auto", "on", "off"],
        help="多老师模式默认策略",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    planning_dir = (root / args.planning_dir).resolve()
    planning_dir.mkdir(parents=True, exist_ok=True)

    protocol_md_path = planning_dir / "learning_protocol.md"
    protocol_json_path = planning_dir / "learning_protocol.json"

    missing = protocol_questions(args)

    protocol = {
        "topic": args.topic,
        "updated_at": date.today().isoformat(),
        "proactive_guidance": args.proactive_guidance,
        "chunk_definition": args.chunk_definition or "待确认",
        "chunk_size": args.chunk_size or "待确认",
        "process_quiz_every": args.process_quiz_every or "待确认",
        "process_quiz_count": args.process_quiz_count,
        "checkpoint_rule": args.checkpoint_rule or "待确认",
        "checkpoint_quiz_count": args.checkpoint_quiz_count,
        "confirmation_rule": args.confirmation_rule or "待确认",
        "quiz_extension_mode": args.quiz_extension_mode,
        "multi_teacher_default": args.multi_teacher_default,
        "missing_questions": missing,
    }

    md_text = f"""# 学习协议

主题：{args.topic}
更新日期：{date.today().isoformat()}

## 主动带学模式

- 设置：{args.proactive_guidance}
- 说明：开启后，系统默认主动推进下一步，而不是等用户每阶段重新下命令。

## 内容切块规则

- 什么算一块内容：{args.chunk_definition or "待确认"}
- 每块默认规模：{args.chunk_size or "待确认"}

## 测验规则

- 过程测验触发：{args.process_quiz_every or "待确认"}
- 过程测验题量：{args.process_quiz_count if args.process_quiz_count is not None else "待确认"}
- 阶段测试触发：{args.checkpoint_rule or "待确认"}
- 阶段测试题量：{args.checkpoint_quiz_count if args.checkpoint_quiz_count is not None else "待确认"}

## 交流节奏

- 何时停下来确认：{args.confirmation_rule or "待确认"}
- 多老师默认策略：{args.multi_teacher_default}

## 出题延伸策略

- 设置：{args.quiz_extension_mode}
- 说明：`focused` 表示经典题或延伸题只能围绕当前重点；`none` 表示只出材料题；`light` 表示可少量加入围绕重点的延伸题。

## 待确认问题

{chr(10).join(f"- {item}" for item in missing) if missing else "- 当前学习协议已完成基本配置。"}
"""

    protocol_md_path.write_text(md_text, encoding="utf-8")
    protocol_json_path.write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[写入] {protocol_md_path}")
    print(f"[写入] {protocol_json_path}")
    print()
    print("建议先和用户确认这些配置：")
    if missing:
        for index, item in enumerate(missing, start=1):
            print(f"{index}. {item}")
    else:
        print("1. 当前学习协议已完成基本配置，后续可以默认按协议主动带学。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
