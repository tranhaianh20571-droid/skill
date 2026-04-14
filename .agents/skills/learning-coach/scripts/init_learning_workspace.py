from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = SKILL_ROOT / "assets" / "templates"

DEFAULT_FILES = {
    "learner_profile.md": "learner_profile.md",
    "study_goal.md": "study_goal.md",
    "study_plan.md": "study_plan.md",
    "progress.md": "progress.md",
    "findings.md": "findings.md",
    "quiz_log.md": "quiz_log.md",
    "mistakes.md": "mistakes.md",
    "materials_index.md": "materials_index.md",
    "session_brief.md": "session_brief.md",
    "grounding_log.md": "grounding_log.md",
    "adjustment_log.md": "adjustment_log.md",
    "issue_log.md": "issue_log.md",
    "quiz_bank.md": "quiz_bank.md",
    "learning_protocol.md": "learning_protocol.md",
    "coverage_map.md": "coverage_map.md",
    "agent_team.md": "agent_team.md",
}


def render_template(template_name: str, topic: str) -> str:
    template_path = TEMPLATE_DIR / template_name
    text = template_path.read_text(encoding="utf-8")
    return (
        text.replace("{{TODAY}}", date.today().isoformat())
        .replace("{{TOPIC}}", topic)
    )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="初始化可复用的学习工作区。"
    )
    parser.add_argument("--root", required=True, help="项目或笔记根目录")
    parser.add_argument(
        "--planning-dir",
        default=".codex/planning",
        help="相对于根目录的规划文件目录",
    )
    parser.add_argument(
        "--topic",
        default="当前学习主题",
        help="模板中的初始主题名称",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="如果文件已存在则覆盖",
    )
    parser.add_argument(
        "--create-agents",
        action="store_true",
        help="同时在根目录创建项目级 AGENTS.md 模板",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    planning_dir = (root / args.planning_dir).resolve()
    planning_dir.mkdir(parents=True, exist_ok=True)

    created = 0
    skipped = 0

    for output_name, template_name in DEFAULT_FILES.items():
        output_path = planning_dir / output_name
        if output_path.exists() and not args.force:
            skipped += 1
            print(f"[跳过] {output_path}")
            continue

        output_path.write_text(
            render_template(template_name, args.topic),
            encoding="utf-8",
        )
        created += 1
        print(f"[写入] {output_path}")

    if args.create_agents:
        agents_path = root / "AGENTS.md"
        if agents_path.exists() and not args.force:
            skipped += 1
            print(f"[跳过] {agents_path}")
        else:
            agents_path.write_text(
                render_template("project_AGENTS.md", args.topic),
                encoding="utf-8",
            )
            created += 1
            print(f"[写入] {agents_path}")

    print()
    print(f"工作区已就绪：{planning_dir}")
    print(f"已创建：{created}")
    print(f"已跳过：{skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
