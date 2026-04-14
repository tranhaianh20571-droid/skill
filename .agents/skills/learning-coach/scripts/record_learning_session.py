from __future__ import annotations

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_DIR = SKILL_ROOT / "assets" / "templates"


def ensure_file(path: Path, template_name: str) -> None:
    if path.exists():
        return
    text = (TEMPLATE_DIR / template_name).read_text(encoding="utf-8")
    text = text.replace("{{TODAY}}", date.today().isoformat())
    text = text.replace("{{TOPIC}}", "当前学习主题")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def append_text(path: Path, content: str) -> None:
    with path.open("a", encoding="utf-8") as handle:
        if not content.startswith("\n"):
            handle.write("\n")
        handle.write(content.rstrip() + "\n")


def table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(
        description="追加结构化的学习会话记录。"
    )
    parser.add_argument("--root", required=True, help="项目或笔记根目录")
    parser.add_argument(
        "--planning-dir",
        default=".codex/planning",
        help="相对于根目录的规划文件目录",
    )
    parser.add_argument("--unit", required=True, help="学习小单元名称")
    parser.add_argument("--summary", required=True, help="本次学到了什么")
    parser.add_argument("--scene", default="", help="当前学习场景")
    parser.add_argument(
        "--status",
        default="complete",
        choices=["complete", "partial", "blocked"],
        help="本次会话完成状态",
    )
    parser.add_argument("--next-step", default="", help="下一步学习动作")
    parser.add_argument("--granularity", default="", help="本次讲解颗粒度")
    parser.add_argument(
        "--focus",
        action="append",
        default=[],
        help="本次最重要的重点，可重复传入",
    )
    parser.add_argument(
        "--material-ref",
        action="append",
        default=[],
        help="本次讲解或出题依赖的材料依据，可重复传入",
    )
    parser.add_argument(
        "--necessary-support",
        action="append",
        default=[],
        help="必要补充及原因，建议格式：补充内容 | 必要性",
    )
    parser.add_argument("--quiz-topic", default="", help="测验主题")
    parser.add_argument(
        "--quiz-result",
        default="",
        choices=["", "pass", "partial", "fail"],
        help="如果做了测验，这里记录结果",
    )
    parser.add_argument(
        "--mistake",
        action="append",
        default=[],
        help="重复误区或错误点，可重复传入",
    )
    parser.add_argument(
        "--finding",
        action="append",
        default=[],
        help="值得沉淀的关键收获，可重复传入",
    )
    parser.add_argument(
        "--adjustment",
        action="append",
        default=[],
        help="根据用户反馈做出的调整，可重复传入",
    )
    parser.add_argument(
        "--issue",
        action="append",
        default=[],
        help="本轮暴露出的流程或讲解问题，可重复传入",
    )
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    planning_dir = (root / args.planning_dir).resolve()

    progress_path = planning_dir / "progress.md"
    findings_path = planning_dir / "findings.md"
    quiz_log_path = planning_dir / "quiz_log.md"
    mistakes_path = planning_dir / "mistakes.md"
    grounding_log_path = planning_dir / "grounding_log.md"
    adjustment_log_path = planning_dir / "adjustment_log.md"
    issue_log_path = planning_dir / "issue_log.md"

    ensure_file(progress_path, "progress.md")
    ensure_file(findings_path, "findings.md")
    ensure_file(quiz_log_path, "quiz_log.md")
    ensure_file(mistakes_path, "mistakes.md")
    ensure_file(grounding_log_path, "grounding_log.md")
    ensure_file(adjustment_log_path, "adjustment_log.md")
    ensure_file(issue_log_path, "issue_log.md")

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    status_map = {"complete": "完成", "partial": "部分完成", "blocked": "受阻"}
    quiz_result_map = {"pass": "通过", "partial": "部分通过", "fail": "未通过", "": "已记录"}
    progress_entry = [
        f"## {now} | {args.unit}",
        f"- 状态：{status_map[args.status]}",
        f"- 总结：{args.summary}",
    ]
    if args.scene:
        progress_entry.append(f"- 场景：{args.scene}")
    if args.granularity:
        progress_entry.append(f"- 颗粒度：{args.granularity}")
    if args.focus:
        progress_entry.append(f"- 重点：{'；'.join(args.focus)}")
    if args.material_ref:
        progress_entry.append(f"- 材料依据：{'；'.join(args.material_ref)}")
    if args.necessary_support:
        progress_entry.append(f"- 必要补充：{'；'.join(args.necessary_support)}")
    if args.quiz_topic:
        result = quiz_result_map[args.quiz_result]
        progress_entry.append(f"- 测验：{args.quiz_topic}（{result}）")
    if args.next_step:
        progress_entry.append(f"- 下一步：{args.next_step}")
    append_text(progress_path, "\n".join(progress_entry))
    print(f"[追加] {progress_path}")

    if args.finding:
        finding_lines = [f"## {now} | {args.unit}"]
        finding_lines.extend(f"- {item}" for item in args.finding)
        append_text(findings_path, "\n".join(finding_lines))
        print(f"[追加] {findings_path}")

    if args.quiz_topic:
        review_date = (date.today() + timedelta(days=1)).isoformat()
        quiz_line = (
            f"| {table_cell(date.today().isoformat())} | {table_cell(args.quiz_topic)} | 过程测验 | "
            f"{table_cell(quiz_result_map[args.quiz_result])} | {table_cell(args.summary)} | {table_cell(review_date)} |"
        )
        append_text(quiz_log_path, quiz_line)
        print(f"[追加] {quiz_log_path}")

    if args.mistake:
        review_date = (date.today() + timedelta(days=1)).isoformat()
        for item in args.mistake:
            row = (
                f"| {table_cell(date.today().isoformat())} | {table_cell(args.unit)} | {table_cell(item)} | "
                f"需要复习 | 针对性重练 | {table_cell(review_date)} | 待处理 |"
            )
            append_text(mistakes_path, row)
        print(f"[追加] {mistakes_path}")

    if args.material_ref or args.necessary_support or args.quiz_topic:
        grounding_row = (
            f"| {table_cell(date.today().isoformat())} | {table_cell(args.scene or '未指定')} | "
            f"{table_cell('学习单元/测验' if args.quiz_topic else '学习单元')} | {table_cell(args.unit)} | "
            f"{table_cell('；'.join(args.material_ref) or '待补充')} | "
            f"{table_cell('是' if args.necessary_support else '否')} | "
            f"{table_cell('；'.join(args.necessary_support) or '无')} | {table_cell(args.summary)} |"
        )
        append_text(grounding_log_path, grounding_row)
        print(f"[追加] {grounding_log_path}")

    if args.adjustment:
        for item in args.adjustment:
            row = (
                f"| {table_cell(date.today().isoformat())} | {table_cell(args.scene or '未指定')} | 用户反馈/运行观察 | "
                f"{table_cell(item)} | 待验证 | {table_cell(args.unit)} |"
            )
            append_text(adjustment_log_path, row)
        print(f"[追加] {adjustment_log_path}")

    if args.issue:
        for item in args.issue:
            row = (
                f"| {table_cell(date.today().isoformat())} | {table_cell(args.scene or '未指定')} | 学习流程 | "
                f"{table_cell(item)} | 待补充 | 待处理 | 待处理 |"
            )
            append_text(issue_log_path, row)
        print(f"[追加] {issue_log_path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
