from __future__ import annotations

import argparse
import json
import math
import random
import re
import sys
from datetime import date, datetime
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


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", value)
    value = re.sub(r"-+", "-", value).strip("-")
    return value or "quiz"


def table_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ").strip()


def load_protocol(planning_dir: Path) -> dict:
    protocol_path = planning_dir / "learning_protocol.json"
    if not protocol_path.exists():
        return {}
    try:
        return json.loads(protocol_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def parse_mapped_notes(entries: list[str], allowed_focuses: list[str], source_kind: str) -> list[dict[str, str]]:
    parsed: list[dict[str, str]] = []
    allowed = set(allowed_focuses)
    for raw in entries:
        text = raw.strip()
        if not text:
            continue

        if "=>" in text:
            focus, content = text.split("=>", 1)
        elif "|" in text:
            focus, content = text.split("|", 1)
        else:
            focus, content = "*", text

        focus = focus.strip()
        content = content.strip()
        if not content:
            continue
        if focus != "*" and allowed and focus not in allowed:
            continue
        parsed.append(
            {
                "focus": focus,
                "content": content,
                "source_kind": source_kind,
            }
        )
    return parsed


def pick_distractors(pool: list[str], correct: str, count: int) -> list[str]:
    distractors: list[str] = []
    seen = {correct}
    for item in pool:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        distractors.append(normalized)
        seen.add(normalized)
        if len(distractors) == count:
            break
    return distractors


def make_options(correct: str, candidates: list[str], non_goals: list[str], fallback_focus: str) -> tuple[list[str], str]:
    pool = candidates + non_goals + [
        f"先扩展所有和“{fallback_focus}”间接相关的背景知识",
        f"暂时跳过当前重点，改讲一个相关但不在本轮目标里的分支",
    ]
    distractors = pick_distractors(pool, correct, 3)
    if len(distractors) < 3:
        pool.extend(
            [
                "这轮无需区分当前重点和非目标",
                "只要相关就应该全面展开，不需要场景边界",
                "题目可以主要围绕补充背景，不必围绕材料重点",
            ]
        )
        distractors = pick_distractors(pool, correct, 3)
    options = [correct] + distractors[:3]
    rng = random.Random(correct)
    rng.shuffle(options)
    answer = "ABCD"[options.index(correct)]
    return options, answer


def render_markdown(bundle: dict) -> str:
    lines = [
        "# 当前测验",
        "",
        f"- 主题：{bundle['topic']}",
        f"- 场景：{bundle['scene'] or '未指定'}",
        f"- 难度：{bundle['difficulty']}",
        f"- 题目数量：{len(bundle['questions'])}",
        f"- 当前重点：{'；'.join(bundle['focuses']) or '未指定'}",
        f"- 出题来源策略：{bundle['source_strategy']}",
        "",
        "## 题目",
        "",
    ]

    for index, question in enumerate(bundle["questions"], start=1):
        lines.append(
            f"### 第 {index} 题 [{question['source_kind_label']}] [{question['focus']}]"
        )
        lines.append(question["stem"])
        lines.append("")
        for option_id, option_text in zip(["A", "B", "C", "D"], question["options"]):
            lines.append(f"- {option_id}. {option_text}")
        lines.append("")

    lines.extend(["## 参考答案", ""])
    for index, question in enumerate(bundle["questions"], start=1):
        lines.append(f"### 第 {index} 题")
        lines.append(f"- 答案：{question['answer']}")
        lines.append(f"- 解析：{question['rationale']}")
        lines.append(f"- 依据：{question['source_basis']}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    parser = argparse.ArgumentParser(description="基于重点与材料生成测验。")
    parser.add_argument("--root", required=True, help="项目或笔记根目录")
    parser.add_argument(
        "--planning-dir",
        default=".codex/planning",
        help="相对于根目录的规划文件目录",
    )
    parser.add_argument("--topic", default="当前学习主题", help="当前学习主题")
    parser.add_argument("--scene", default="", help="当前学习场景")
    parser.add_argument(
        "--focus",
        action="append",
        default=[],
        help="当前重点，可重复传入",
    )
    parser.add_argument(
        "--material-point",
        action="append",
        default=[],
        help="材料中的关键点，可重复传入",
    )
    parser.add_argument(
        "--material-ref",
        action="append",
        default=[],
        help="材料依据标签，可重复传入",
    )
    parser.add_argument(
        "--classic-note",
        action="append",
        default=[],
        help="经典题或经典结论，建议格式：重点=>内容，可重复传入",
    )
    parser.add_argument(
        "--web-note",
        action="append",
        default=[],
        help="网络检索得到的延伸要点，建议格式：重点=>内容，可重复传入",
    )
    parser.add_argument(
        "--non-goal",
        action="append",
        default=[],
        help="当前场景的非目标，可重复传入",
    )
    parser.add_argument("--question-count", type=int, default=None, help="题目数量")
    parser.add_argument(
        "--difficulty",
        default="基础",
        choices=["基础", "进阶", "混合"],
        help="测验难度",
    )
    parser.add_argument(
        "--extension-mode",
        default="",
        choices=["", "none", "classic", "web", "both"],
        help="是否允许加入经典题或网络延伸",
    )
    parser.add_argument(
        "--output-name",
        default="",
        help="输出文件名，不带扩展名时会自动处理",
    )
    args = parser.parse_args()

    if not args.material_point:
        raise SystemExit("至少需要一个 --material-point 才能生成测验。")

    root = Path(args.root).expanduser().resolve()
    planning_dir = (root / args.planning_dir).resolve()
    outputs_dir = planning_dir / "quiz_outputs"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    protocol = load_protocol(planning_dir)

    quiz_bank_path = planning_dir / "quiz_bank.md"
    ensure_file(quiz_bank_path, "quiz_bank.md", args.topic)

    focuses = [item.strip() for item in args.focus if item.strip()]
    if not focuses:
        focuses = ["当前材料重点"]

    protocol_extension_mode = protocol.get("quiz_extension_mode", "focused")
    extension_mode = args.extension_mode
    if not extension_mode:
        if protocol_extension_mode in {"focused", "light"} and (args.classic_note or args.web_note):
            extension_mode = "both"
        else:
            extension_mode = "none"
    else:
        extension_mode = extension_mode

    extension_notes: list[dict[str, str]] = []
    if extension_mode in {"classic", "both"}:
        extension_notes.extend(parse_mapped_notes(args.classic_note, focuses, "classic"))
    if extension_mode in {"web", "both"}:
        extension_notes.extend(parse_mapped_notes(args.web_note, focuses, "web"))

    question_count = args.question_count
    if question_count is None:
        question_count = protocol.get("process_quiz_count") or 6

    material_target = question_count
    extension_target = 0
    if extension_notes and extension_mode != "none":
        ratio = 0.2 if protocol_extension_mode == "focused" else 0.3
        extension_target = min(len(extension_notes), max(1, math.floor(question_count * ratio)))
        material_target = max(1, question_count - extension_target)

    questions: list[dict[str, object]] = []
    material_candidates = [item.strip() for item in args.material_point if item.strip()]

    for index in range(material_target):
        correct = material_candidates[index % len(material_candidates)]
        focus = focuses[index % len(focuses)]
        options, answer = make_options(correct, material_candidates, args.non_goal, focus)
        questions.append(
            {
                "id": f"material-{index + 1}",
                "type": "multiple_choice",
                "source_kind": "material",
                "source_kind_label": "材料重点题",
                "focus": focus,
                "stem": f"在当前场景“{args.scene or '未指定'}”下，围绕重点“{focus}”，下列哪一项最符合本轮材料中的核心表述？",
                "options": options,
                "answer": answer,
                "source_basis": "；".join(args.material_ref) or "当前材料要点",
                "rationale": "正确项直接来自当前材料重点，其余项要么是其他材料点，要么属于当前非目标或错误展开方向。",
            }
        )

    for index in range(extension_target):
        note = extension_notes[index]
        correct = note["content"]
        focus = note["focus"] if note["focus"] != "*" else focuses[index % len(focuses)]
        note_pool = [item["content"] for item in extension_notes]
        options, answer = make_options(correct, material_candidates + note_pool, args.non_goal, focus)
        label = "经典延伸题" if note["source_kind"] == "classic" else "网络延伸题"
        source_basis = "；".join(args.material_ref) or "当前材料重点"
        source_basis += f"；{label}:{correct}"
        questions.append(
            {
                "id": f"{note['source_kind']}-{index + 1}",
                "type": "multiple_choice",
                "source_kind": note["source_kind"],
                "source_kind_label": label,
                "focus": focus,
                "stem": f"围绕当前重点“{focus}”，下面哪一项最适合作为本轮学习的延伸理解？",
                "options": options,
                "answer": answer,
                "source_basis": source_basis,
                "rationale": "正确项是围绕当前重点挑出的延伸线索，其他项不是当前重点的最佳延伸方向，或属于本轮非目标。",
            }
        )

    source_strategy = "仅材料重点"
    if extension_target > 0:
        source_strategy = f"材料重点 {material_target} 题 + 延伸 {extension_target} 题"

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base_name = slugify(args.output_name or f"{args.topic}-{timestamp}")
    markdown_path = outputs_dir / f"{base_name}.md"
    json_path = outputs_dir / f"{base_name}.json"

    bundle = {
        "topic": args.topic,
        "scene": args.scene,
        "difficulty": args.difficulty,
        "focuses": focuses,
        "source_strategy": source_strategy,
        "protocol_defaults": {
            "process_quiz_count": protocol.get("process_quiz_count"),
            "quiz_extension_mode": protocol_extension_mode,
        },
        "material_refs": args.material_ref,
        "questions": questions,
    }

    markdown_path.write_text(render_markdown(bundle), encoding="utf-8")
    json_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")

    bank_row = (
        f"| {table_cell(date.today().isoformat())} | {table_cell(args.topic)} | {table_cell(args.scene or '未指定')} | "
        f"{table_cell('；'.join(focuses))} | {len(questions)} | {table_cell(source_strategy)} | "
        f"{table_cell(str(markdown_path))} | {table_cell(str(json_path))} |"
    )
    with quiz_bank_path.open("a", encoding="utf-8") as handle:
        handle.write("\n" + bank_row + "\n")

    print(f"[写入] {markdown_path}")
    print(f"[写入] {json_path}")
    print(f"[追加] {quiz_bank_path}")
    print()
    print(f"题目数量：{len(questions)}")
    print(f"出题策略：{source_strategy}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
