from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
INIT_SCRIPT = SCRIPT_DIR / "init_learning_workspace.py"
PROTOCOL_SCRIPT = SCRIPT_DIR / "configure_learning_protocol.py"
SESSION_SCRIPT = SCRIPT_DIR / "open_learning_session.py"
QUIZ_SCRIPT = SCRIPT_DIR / "generate_quiz.py"
RECORD_SCRIPT = SCRIPT_DIR / "record_learning_session.py"


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def run_script(script_path: Path, arguments: list[str]) -> None:
    command = [sys.executable, str(script_path), *arguments]
    subprocess.run(command, check=True)


def ask_text(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}：").strip()
    return value or default


def ask_int(prompt: str, default: int) -> int:
    while True:
        raw = ask_text(prompt, str(default))
        try:
            return int(raw)
        except ValueError:
            print("请输入整数。")


def ask_choice(prompt: str, options: list[tuple[str, str]], default: str) -> str:
    print(prompt)
    for index, (value, label) in enumerate(options, start=1):
        flag = " (默认)" if value == default else ""
        print(f"{index}. {label}{flag}")
    while True:
        raw = input("请输入编号或值：").strip()
        if not raw:
            return default
        if raw.isdigit():
            choice_index = int(raw) - 1
            if 0 <= choice_index < len(options):
                return options[choice_index][0]
        for value, _label in options:
            if raw == value:
                return value
        print("输入无效，请重新选择。")


def ask_bool(prompt: str, default: bool = True) -> bool:
    default_text = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{prompt} [{default_text}]：").strip().lower()
        if not raw:
            return default
        if raw in {"y", "yes"}:
            return True
        if raw in {"n", "no"}:
            return False
        print("请输入 y 或 n。")


def ask_list(prompt: str, default: list[str] | None = None) -> list[str]:
    default_text = "；".join(default or [])
    raw = ask_text(prompt + "（多个请用；分隔）", default_text)
    return [item.strip() for item in re.split(r"[；;]", raw) if item.strip()]


def load_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def planning_dir(root: Path) -> Path:
    return root / ".codex" / "planning"


def workspace_ready(root: Path) -> bool:
    return planning_dir(root).exists()


def parse_markdown_sections(text: str) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    current = ""
    for line in text.splitlines():
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current:
            sections[current].append(line)
    return {key: "\n".join(value).strip() for key, value in sections.items()}


def compact_markdown_value(value: str) -> str:
    if not value:
        return "待确认"
    lines = [line.strip() for line in value.splitlines() if line.strip()]
    bullets = [line[2:].strip() for line in lines if line.startswith("- ")]
    if bullets:
        return "；".join(bullets)
    return " ".join(lines)


def extract_bullets(value: str) -> list[str]:
    if not value:
        return []
    result: list[str] = []
    for line in value.splitlines():
        stripped = line.strip()
        if stripped.startswith("- "):
            result.append(stripped[2:].strip())
    return result


def read_session_sections(root: Path) -> dict[str, str]:
    path = planning_dir(root) / "session_brief.md"
    if not path.exists():
        return {}
    return parse_markdown_sections(path.read_text(encoding="utf-8"))


def read_protocol(root: Path) -> dict:
    return load_json(planning_dir(root) / "learning_protocol.json")


def read_latest_progress(progress_path: Path) -> dict[str, str]:
    if not progress_path.exists():
        return {}
    text = progress_path.read_text(encoding="utf-8")
    pattern = re.compile(r"(?ms)^## (\d{4}-\d{2}-\d{2} .*?)(?=^## |\Z)")
    entries = [match.group(1).strip() for match in pattern.finditer(text)]
    if not entries:
        return {}
    latest = entries[-1]
    lines = latest.splitlines()
    result = {"title": lines[0].strip() if lines else ""}
    for line in lines[1:]:
        if line.startswith("- "):
            body = line[2:]
            if "：" in body:
                key, value = body.split("：", 1)
                result[key.strip()] = value.strip()
    return result


def count_progress_entries(path: Path) -> int:
    if not path.exists():
        return 0
    pattern = re.compile(r"(?m)^## \d{4}-\d{2}-\d{2} ")
    return len(pattern.findall(path.read_text(encoding="utf-8")))


def parse_markdown_table(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    lines = [line.rstrip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    table_lines = [line for line in lines if line.lstrip().startswith("|")]
    if len(table_lines) < 3:
        return []

    def split_row(line: str) -> list[str]:
        cells: list[str] = []
        current: list[str] = []
        escaped = False
        started = False
        for char in line:
            if char == "|" and not escaped:
                if started:
                    cells.append("".join(current).strip())
                    current = []
                else:
                    started = True
                continue
            if char == "\\" and not escaped:
                escaped = True
                current.append(char)
                continue
            escaped = False
            current.append(char)
        if current:
            cells.append("".join(current).strip())
        if cells and cells[-1] == "":
            cells = cells[:-1]
        return [cell.replace("\\|", "|") for cell in cells]

    headers = split_row(table_lines[0])
    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:
        cells = split_row(line)
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows


def count_table_rows(path: Path) -> int:
    return len(parse_markdown_table(path))


def parse_first_number(text: str, default: int) -> int:
    match = re.search(r"(\d+)", text or "")
    if not match:
        return default
    return max(1, int(match.group(1)))


def due_review_summary(root: Path) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    today = date.today().isoformat()
    quiz_rows = parse_markdown_table(planning_dir(root) / "quiz_log.md")
    mistake_rows = parse_markdown_table(planning_dir(root) / "mistakes.md")
    due_quizzes = [row for row in quiz_rows if row.get("下次复习", "") and row.get("下次复习", "") <= today]
    due_mistakes = [
        row
        for row in mistake_rows
        if row.get("复习日期", "") and row.get("复习日期", "") <= today and row.get("状态", "") not in {"已解决", "closed"}
    ]
    return due_quizzes, due_mistakes


def recommendation(root: Path) -> dict[str, str]:
    pdir = planning_dir(root)
    protocol = read_protocol(root)
    if not protocol:
        return {
            "key": "protocol",
            "message": "先完成第一次学习协议配置，把切块、测验频率、题量和确认时机定下来。",
        }

    if protocol.get("missing_questions"):
        return {
            "key": "protocol",
            "message": "学习协议还有未确认项，建议先补齐再继续。",
        }

    session_sections = read_session_sections(root)
    if not session_sections:
        return {
            "key": "align",
            "message": "先对齐当前学习会话，确认当前场景、目标、重点和资料。",
        }

    unresolved = session_sections.get("待确认问题", "")
    if unresolved and "当前已完成基本对齐" not in unresolved:
        return {
            "key": "align",
            "message": "当前会话还有待确认问题，先补齐再进入学习。",
        }

    due_quizzes, due_mistakes = due_review_summary(root)
    if due_quizzes or due_mistakes:
        return {
            "key": "review",
            "message": f"当前有 {len(due_quizzes)} 条待复习测验、{len(due_mistakes)} 条待复习薄弱点，建议先复习。",
        }

    progress_path = pdir / "progress.md"
    latest_progress = read_latest_progress(progress_path)
    progress_entries = count_progress_entries(progress_path)
    quiz_entries = count_table_rows(pdir / "quiz_log.md")
    process_every = parse_first_number(str(protocol.get("process_quiz_every", "")), 1)

    if progress_entries == 0:
        focus_items = extract_bullets(session_sections.get("当前重点", ""))
        if focus_items:
            return {
                "key": "block",
                "message": f"还没有开始第一块内容，建议先围绕“{focus_items[0]}”进入当前小单元。",
            }
        return {
            "key": "block",
            "message": "还没有开始第一块内容，建议先生成当前学习块建议。",
        }

    expected_quizzes = progress_entries // process_every
    if quiz_entries < expected_quizzes:
        return {
            "key": "quiz",
            "message": "按当前学习协议，已经到了过程测验时机，建议先做一轮测验。",
        }

    next_step = latest_progress.get("下一步")
    if next_step:
        return {
            "key": "block",
            "message": f"建议下一步：{next_step}",
        }

    return {
        "key": "block",
        "message": "协议和会话都已对齐，可以继续推进下一块内容。",
    }


def show_status(root: Path) -> None:
    pdir = planning_dir(root)
    protocol = read_protocol(root)
    session_sections = read_session_sections(root)
    latest_progress = read_latest_progress(pdir / "progress.md")
    rec = recommendation(root)
    due_quizzes, due_mistakes = due_review_summary(root)

    print("当前学习状态")
    print(f"- 根目录：{root}")
    print(f"- 当前主题：{protocol.get('topic') or '待确认'}")
    print(f"- 主动带学：{protocol.get('proactive_guidance', '待确认')}")
    print(f"- 一块内容：{protocol.get('chunk_definition', '待确认')}")
    print(f"- 每块规模：{protocol.get('chunk_size', '待确认')}")
    print(f"- 过程测验：{protocol.get('process_quiz_every', '待确认')} / {protocol.get('process_quiz_count', '待确认')} 题")
    print(f"- 阶段测试：{protocol.get('checkpoint_rule', '待确认')} / {protocol.get('checkpoint_quiz_count', '待确认')} 题")
    print(f"- 当前场景：{compact_markdown_value(session_sections.get('当前场景', ''))}")
    print(f"- 当前目标：{compact_markdown_value(session_sections.get('当前目标', ''))}")
    print(f"- 当前重点：{compact_markdown_value(session_sections.get('当前重点', ''))}")
    if latest_progress:
        print(f"- 最近一块：{latest_progress.get('title', '无')}")
        print(f"- 最近总结：{latest_progress.get('总结', '无')}")
        print(f"- 最近下一步：{latest_progress.get('下一步', '无')}")
    else:
        print("- 最近一块：暂无")
    print(f"- 已记录学习块数：{count_progress_entries(pdir / 'progress.md')}")
    print(f"- 已记录测验数：{count_table_rows(pdir / 'quiz_log.md')}")
    print(f"- 待复习测验：{len(due_quizzes)}")
    print(f"- 待复习薄弱点：{len(due_mistakes)}")
    print(f"- 下一步建议：{rec['message']}")


def ensure_workspace(root_hint: str = "", topic_hint: str = "") -> tuple[Path, str]:
    if root_hint:
        root = Path(root_hint).expanduser().resolve()
    else:
        root = Path(ask_text("项目或笔记根目录", str(Path.cwd()))).expanduser().resolve()
    topic = topic_hint or read_protocol(root).get("topic")
    if not topic:
        topic = ask_text("当前学习主题", "当前学习主题")
    if workspace_ready(root):
        return root, topic
    print("检测到这是第一次使用，自动进入初始化向导。")
    create_agents = ask_bool("是否顺便创建项目级 AGENTS.md", True)
    init_args = ["--root", str(root), "--topic", topic]
    if create_agents:
        init_args.append("--create-agents")
    run_script(INIT_SCRIPT, init_args)
    return root, topic


def run_protocol_wizard(root: Path, topic: str, existing: dict | None = None) -> None:
    existing = existing or read_protocol(root)
    print("现在开始配置学习协议。")
    proactive = ask_choice(
        "默认要不要由系统主动带节奏？",
        [("on", "开启主动带学"), ("mixed", "半主动，重要节点再确认"), ("off", "仅在你要求时推进")],
        existing.get("proactive_guidance", "on"),
    )
    chunk_definition = ask_text(
        "什么算一块内容",
        existing.get("chunk_definition", "以一个核心概念、功能点或典型问题为一块"),
    )
    chunk_size = ask_text(
        "每块内容默认多大",
        existing.get("chunk_size", "每块 1 个核心点，必要时配 1 个例子"),
    )
    process_quiz_every = ask_text(
        "几块后做一次过程测验",
        existing.get("process_quiz_every", "每 1 块后做一次过程测验"),
    )
    process_quiz_count = ask_int("过程测验每次几题", int(existing.get("process_quiz_count") or 3))
    checkpoint_rule = ask_text(
        "阶段测试怎么触发",
        existing.get("checkpoint_rule", "每 3 块后做一次阶段测试"),
    )
    checkpoint_quiz_count = ask_int("阶段测试每次几题", int(existing.get("checkpoint_quiz_count") or 6))
    confirmation_rule = ask_text(
        "什么时候停下来确认",
        existing.get("confirmation_rule", "每块后都先停下来确认是否继续"),
    )
    quiz_extension_mode = ask_choice(
        "经典题或延伸题默认怎么处理？",
        [("focused", "少量加入，但只能围绕当前重点"), ("light", "可稍微多一点延伸，但仍围绕重点"), ("none", "只出材料题")],
        existing.get("quiz_extension_mode", "focused"),
    )
    multi_teacher_default = ask_choice(
        "多老师模式默认策略",
        [("auto", "由系统判断是否值得建议"), ("on", "默认建议开启"), ("off", "默认单老师")],
        existing.get("multi_teacher_default", "auto"),
    )

    protocol_args = [
        "--root", str(root),
        "--topic", topic,
        "--proactive-guidance", proactive,
        "--chunk-definition", chunk_definition,
        "--chunk-size", chunk_size,
        "--process-quiz-every", process_quiz_every,
        "--process-quiz-count", str(process_quiz_count),
        "--checkpoint-rule", checkpoint_rule,
        "--checkpoint-quiz-count", str(checkpoint_quiz_count),
        "--confirmation-rule", confirmation_rule,
        "--quiz-extension-mode", quiz_extension_mode,
        "--multi-teacher-default", multi_teacher_default,
    ]
    run_script(PROTOCOL_SCRIPT, protocol_args)


def run_align_wizard(root: Path, topic: str, args: argparse.Namespace | None = None) -> None:
    protocol = read_protocol(root)
    session = read_session_sections(root)
    args = args or argparse.Namespace()
    scene = ask_choice(
        "当前学习场景",
        [
            ("先搭框架", "先建立整体地图"),
            ("精读材料", "围绕一份材料深入理解"),
            ("面试表达", "偏向如何组织回答"),
            ("项目映射", "偏向映射到项目或实践"),
            ("补薄弱点", "针对某个问题专项补强"),
        ],
        getattr(args, "scene", "") or compact_markdown_value(session.get("当前场景", "")) or "先搭框架",
    )
    goal = ask_text("这一轮最想解决什么问题", getattr(args, "goal", "") or compact_markdown_value(session.get("当前目标", "")) or "先建立整体框架，再决定从哪块先学")
    granularity = ask_choice(
        "这轮讲解颗粒度",
        [("粗粒度", "先抓框架和主线"), ("中粒度", "正常细讲"), ("细粒度", "逐点深挖")],
        getattr(args, "granularity", "") or compact_markdown_value(session.get("讲解颗粒度", "")) or "中粒度",
    )
    materials = ask_list("这轮使用哪些材料", getattr(args, "material", []) or extract_bullets(session.get("当前资料", "")))
    focuses = ask_list("这轮最重要的重点", getattr(args, "focus", []) or extract_bullets(session.get("当前重点", "")))
    non_goals = ask_list("这轮先不展开哪些内容", getattr(args, "non_goal", []) or extract_bullets(session.get("当前非目标", "")))
    multi_teacher = ask_choice(
        "这轮多老师模式偏好",
        [("auto", "让系统判断"), ("on", "建议开启"), ("off", "单老师即可")],
        getattr(args, "multi_teacher", "") or protocol.get("multi_teacher_default", "auto"),
    )

    session_args = [
        "--root", str(root),
        "--topic", topic,
        "--scene", scene,
        "--goal", goal,
        "--granularity", granularity,
        "--multi-teacher", multi_teacher,
    ]
    for item in materials:
        session_args.extend(["--material", item])
    for item in focuses:
        session_args.extend(["--focus", item])
    for item in non_goals:
        session_args.extend(["--non-goal", item])
    run_script(SESSION_SCRIPT, session_args)


def build_current_block(root: Path, unit_hint: str = "") -> Path:
    pdir = planning_dir(root)
    protocol = read_protocol(root)
    session = read_session_sections(root)
    latest = read_latest_progress(pdir / "progress.md")
    block_path = pdir / "current_block.md"

    focus_items = extract_bullets(session.get("当前重点", ""))
    materials = extract_bullets(session.get("当前资料", ""))
    non_goals = extract_bullets(session.get("当前非目标", ""))
    recommended_unit = unit_hint or latest.get("下一步") or (focus_items[0] if focus_items else "当前学习块")
    process_every = protocol.get("process_quiz_every", "待确认")
    process_quiz_count = protocol.get("process_quiz_count", "待确认")
    progress_entries = count_progress_entries(pdir / "progress.md")
    next_block_index = progress_entries + 1
    quiz_due = next_block_index % parse_first_number(str(process_every), 1) == 0

    text = f"""# 当前学习块建议

日期：{date.today().isoformat()}

## 推荐块名

{recommended_unit}

## 当前场景

{compact_markdown_value(session.get("当前场景", ""))}

## 当前目标

{compact_markdown_value(session.get("当前目标", ""))}

## 推荐推进方式

- 当前学习协议把“一块内容”定义为：{protocol.get("chunk_definition", "待确认")}
- 当前块默认规模：{protocol.get("chunk_size", "待确认")}
- 当前讲解颗粒度：{compact_markdown_value(session.get("讲解颗粒度", ""))}
- 当前重点：{("；".join(focus_items) if focus_items else "待确认")}
- 当前资料：{("；".join(materials) if materials else "待确认")}
- 当前非目标：{("；".join(non_goals) if non_goals else "无")}

## 节奏提醒

- 这将是第 {next_block_index} 块内容
- 过程测验规则：{process_every}
- 过程测验题量：{process_quiz_count}
- 这一块结束后{"建议立即做过程测验" if quiz_due else "暂时不需要立即测验"}
- 停下来确认的时机：{protocol.get("confirmation_rule", "待确认")}
"""

    block_path.write_text(text, encoding="utf-8")
    print(f"[写入] {block_path}")
    print()
    print(text)
    return block_path


def run_quiz_wizard(root: Path, topic: str, args: argparse.Namespace | None = None) -> None:
    session = read_session_sections(root)
    args = args or argparse.Namespace()
    scene = ask_text("当前学习场景", getattr(args, "scene", "") or compact_markdown_value(session.get("当前场景", "")))
    focuses = ask_list("当前重点", getattr(args, "focus", []) or extract_bullets(session.get("当前重点", "")))
    material_points = ask_list("材料中的关键点", getattr(args, "material_point", []) or [])
    material_refs = ask_list("材料依据标签", getattr(args, "material_ref", []) or extract_bullets(session.get("当前资料", "")))
    non_goals = ask_list("当前非目标", getattr(args, "non_goal", []) or extract_bullets(session.get("当前非目标", "")))
    classic_notes = ask_list("经典题或经典结论（可留空）", getattr(args, "classic_note", []) or [])
    web_notes = ask_list("网络延伸要点（可留空）", getattr(args, "web_note", []) or [])
    output_name = ask_text("输出文件名", getattr(args, "output_name", "") or "")

    quiz_args = [
        "--root", str(root),
        "--topic", topic,
        "--scene", scene,
        "--output-name", output_name,
    ]
    if getattr(args, "question_count", None) is not None:
        quiz_args.extend(["--question-count", str(args.question_count)])
    if getattr(args, "extension_mode", ""):
        quiz_args.extend(["--extension-mode", args.extension_mode])
    for item in focuses:
        quiz_args.extend(["--focus", item])
    for item in material_points:
        quiz_args.extend(["--material-point", item])
    for item in material_refs:
        quiz_args.extend(["--material-ref", item])
    for item in classic_notes:
        quiz_args.extend(["--classic-note", item])
    for item in web_notes:
        quiz_args.extend(["--web-note", item])
    for item in non_goals:
        quiz_args.extend(["--non-goal", item])
    run_script(QUIZ_SCRIPT, quiz_args)


def run_record_wizard(root: Path, topic: str, args: argparse.Namespace | None = None) -> None:
    session = read_session_sections(root)
    args = args or argparse.Namespace()
    unit = ask_text("本次学习小单元", getattr(args, "unit", "") or "")
    summary = ask_text("本次学到了什么", getattr(args, "summary", "") or "")
    scene = ask_text("当前学习场景", getattr(args, "scene", "") or compact_markdown_value(session.get("当前场景", "")))
    granularity = ask_text("本次讲解颗粒度", getattr(args, "granularity", "") or compact_markdown_value(session.get("讲解颗粒度", "")))
    focuses = ask_list("本次最重要的重点", getattr(args, "focus", []) or extract_bullets(session.get("当前重点", "")))
    material_refs = ask_list("本次材料依据", getattr(args, "material_ref", []) or extract_bullets(session.get("当前资料", "")))
    supports = ask_list("本次必要补充（可留空）", getattr(args, "necessary_support", []) or [])
    next_step = ask_text("下一步学习动作", getattr(args, "next_step", "") or "")

    did_quiz = ask_bool("这块结束后是否已经做了测验", False)
    quiz_topic = ""
    quiz_result = ""
    if did_quiz:
        quiz_topic = ask_text("测验主题", "当前块过程测验")
        quiz_result = ask_choice(
            "测验结果",
            [("pass", "通过"), ("partial", "部分通过"), ("fail", "未通过")],
            "pass",
        )

    findings = ask_list("值得沉淀的收获（可留空）", getattr(args, "finding", []) or [])
    mistakes = ask_list("暴露出的错误或薄弱点（可留空）", getattr(args, "mistake", []) or [])
    adjustments = ask_list("需要记录的调整（可留空）", getattr(args, "adjustment", []) or [])
    issues = ask_list("需要记录的问题（可留空）", getattr(args, "issue", []) or [])

    record_args = [
        "--root", str(root),
        "--unit", unit,
        "--summary", summary,
        "--scene", scene,
        "--granularity", granularity,
    ]
    if next_step:
        record_args.extend(["--next-step", next_step])
    for item in focuses:
        record_args.extend(["--focus", item])
    for item in material_refs:
        record_args.extend(["--material-ref", item])
    for item in supports:
        record_args.extend(["--necessary-support", item])
    if did_quiz:
        record_args.extend(["--quiz-topic", quiz_topic, "--quiz-result", quiz_result])
    for item in findings:
        record_args.extend(["--finding", item])
    for item in mistakes:
        record_args.extend(["--mistake", item])
    for item in adjustments:
        record_args.extend(["--adjustment", item])
    for item in issues:
        record_args.extend(["--issue", item])
    run_script(RECORD_SCRIPT, record_args)


def show_review(root: Path) -> None:
    due_quizzes, due_mistakes = due_review_summary(root)
    print("当前复习面板")
    print(f"- 待复习测验：{len(due_quizzes)}")
    for row in due_quizzes[:5]:
        print(f"  - [{row.get('日期', '')}] {row.get('主题', '')} -> 下次复习：{row.get('下次复习', '')}")
    print(f"- 待复习薄弱点：{len(due_mistakes)}")
    for row in due_mistakes[:5]:
        print(f"  - [{row.get('日期', '')}] {row.get('错误点', '')} -> 复习日期：{row.get('复习日期', '')}")
    if not due_quizzes and not due_mistakes:
        print("- 当前没有到期的复习项。")


def run_guide(root_hint: str = "", topic_hint: str = "") -> int:
    root, topic = ensure_workspace(root_hint, topic_hint)
    protocol = read_protocol(root)
    if not protocol or protocol.get("missing_questions"):
        run_protocol_wizard(root, topic, protocol)
    if not read_session_sections(root):
        run_align_wizard(root, topic)

    while True:
        print()
        show_status(root)
        rec = recommendation(root)
        print()
        print(f"系统建议：{rec['message']}")
        action = ask_choice(
            "下一步想怎么做？",
            [
                ("block", "查看当前学习块建议"),
                ("record", "记录刚学完的一块"),
                ("quiz", "生成一轮测验"),
                ("review", "查看待复习项"),
                ("align", "重新对齐当前学习会话"),
                ("protocol", "调整学习协议"),
                ("status", "再看一次当前状态"),
                ("quit", "退出引导模式"),
            ],
            rec["key"] if rec["key"] in {"block", "record", "quiz", "review", "align", "protocol", "status"} else "status",
        )

        if action == "block":
            build_current_block(root)
        elif action == "record":
            run_record_wizard(root, topic)
        elif action == "quiz":
            run_quiz_wizard(root, topic)
        elif action == "review":
            show_review(root)
        elif action == "align":
            run_align_wizard(root, topic)
        elif action == "protocol":
            run_protocol_wizard(root, topic)
        elif action == "status":
            show_status(root)
        elif action == "quit":
            print("已退出引导模式。")
            return 0


def cmd_start(args: argparse.Namespace) -> int:
    root, topic = ensure_workspace(args.root, args.topic)
    run_protocol_wizard(root, topic)
    if ask_bool("是否现在顺便完成第一轮学习会话对齐", True):
        run_align_wizard(root, topic)
    print()
    show_status(root)
    return 0


def cmd_protocol(args: argparse.Namespace) -> int:
    root, topic = ensure_workspace(args.root, args.topic)
    run_protocol_wizard(root, topic)
    return 0


def cmd_align(args: argparse.Namespace) -> int:
    root, topic = ensure_workspace(args.root, args.topic)
    run_align_wizard(root, topic, args)
    return 0


def cmd_block(args: argparse.Namespace) -> int:
    root, _topic = ensure_workspace(args.root, args.topic)
    build_current_block(root, args.unit)
    return 0


def cmd_quiz(args: argparse.Namespace) -> int:
    root, topic = ensure_workspace(args.root, args.topic)
    run_quiz_wizard(root, topic, args)
    return 0


def cmd_record(args: argparse.Namespace) -> int:
    root, topic = ensure_workspace(args.root, args.topic)
    run_record_wizard(root, topic, args)
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    root, _topic = ensure_workspace(args.root, args.topic)
    show_review(root)
    return 0


def cmd_status(args: argparse.Namespace) -> int:
    root, _topic = ensure_workspace(args.root, args.topic)
    show_status(root)
    return 0


def cmd_next(args: argparse.Namespace) -> int:
    root, _topic = ensure_workspace(args.root, args.topic)
    print(recommendation(root)["message"])
    return 0


def cmd_guide(args: argparse.Namespace) -> int:
    return run_guide(args.root, args.topic)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="学习教练统一终端入口。")
    subparsers = parser.add_subparsers(dest="command")

    start = subparsers.add_parser("start", help="第一次使用时的初始化向导")
    start.add_argument("--root", default="", help="项目或笔记根目录")
    start.add_argument("--topic", default="", help="当前学习主题")
    start.set_defaults(func=cmd_start)

    protocol = subparsers.add_parser("protocol", help="调整学习协议")
    protocol.add_argument("--root", default="", help="项目或笔记根目录")
    protocol.add_argument("--topic", default="", help="当前学习主题")
    protocol.set_defaults(func=cmd_protocol)

    align = subparsers.add_parser("align", help="对齐当前学习会话")
    align.add_argument("--root", default="", help="项目或笔记根目录")
    align.add_argument("--topic", default="", help="当前学习主题")
    align.add_argument("--scene", default="", help="当前学习场景")
    align.add_argument("--goal", default="", help="当前轮目标")
    align.add_argument("--granularity", default="", help="讲解颗粒度")
    align.add_argument("--multi-teacher", default="", help="多老师模式偏好")
    align.add_argument("--material", action="append", default=[], help="本轮材料")
    align.add_argument("--focus", action="append", default=[], help="本轮重点")
    align.add_argument("--non-goal", action="append", default=[], help="本轮非目标")
    align.set_defaults(func=cmd_align)

    block = subparsers.add_parser("block", help="生成当前学习块建议")
    block.add_argument("--root", default="", help="项目或笔记根目录")
    block.add_argument("--topic", default="", help="当前学习主题")
    block.add_argument("--unit", default="", help="手动指定块名")
    block.set_defaults(func=cmd_block)

    quiz = subparsers.add_parser("quiz", help="生成一轮测验")
    quiz.add_argument("--root", default="", help="项目或笔记根目录")
    quiz.add_argument("--topic", default="", help="当前学习主题")
    quiz.add_argument("--scene", default="", help="当前学习场景")
    quiz.add_argument("--focus", action="append", default=[], help="当前重点")
    quiz.add_argument("--material-point", action="append", default=[], help="材料关键点")
    quiz.add_argument("--material-ref", action="append", default=[], help="材料依据")
    quiz.add_argument("--non-goal", action="append", default=[], help="当前非目标")
    quiz.add_argument("--classic-note", action="append", default=[], help="经典题延伸")
    quiz.add_argument("--web-note", action="append", default=[], help="网络延伸")
    quiz.add_argument("--question-count", type=int, default=None, help="题量")
    quiz.add_argument("--extension-mode", default="", help="延伸模式")
    quiz.add_argument("--output-name", default="", help="输出文件名")
    quiz.set_defaults(func=cmd_quiz)

    record = subparsers.add_parser("record", help="快速记录本轮学习")
    record.add_argument("--root", default="", help="项目或笔记根目录")
    record.add_argument("--topic", default="", help="当前学习主题")
    record.add_argument("--unit", default="", help="本轮学习小单元")
    record.add_argument("--summary", default="", help="本轮学习总结")
    record.add_argument("--scene", default="", help="当前学习场景")
    record.add_argument("--granularity", default="", help="讲解颗粒度")
    record.add_argument("--focus", action="append", default=[], help="本轮重点")
    record.add_argument("--material-ref", action="append", default=[], help="材料依据")
    record.add_argument("--necessary-support", action="append", default=[], help="必要补充")
    record.add_argument("--finding", action="append", default=[], help="学习收获")
    record.add_argument("--mistake", action="append", default=[], help="薄弱点")
    record.add_argument("--adjustment", action="append", default=[], help="调整")
    record.add_argument("--issue", action="append", default=[], help="问题")
    record.add_argument("--next-step", default="", help="下一步")
    record.set_defaults(func=cmd_record)

    review = subparsers.add_parser("review", help="查看待复习项")
    review.add_argument("--root", default="", help="项目或笔记根目录")
    review.add_argument("--topic", default="", help="当前学习主题")
    review.set_defaults(func=cmd_review)

    status = subparsers.add_parser("status", help="查看当前学习状态")
    status.add_argument("--root", default="", help="项目或笔记根目录")
    status.add_argument("--topic", default="", help="当前学习主题")
    status.set_defaults(func=cmd_status)

    next_cmd = subparsers.add_parser("next", help="给出下一步建议")
    next_cmd.add_argument("--root", default="", help="项目或笔记根目录")
    next_cmd.add_argument("--topic", default="", help="当前学习主题")
    next_cmd.set_defaults(func=cmd_next)

    guide = subparsers.add_parser("guide", help="进入持续引导模式")
    guide.add_argument("--root", default="", help="项目或笔记根目录")
    guide.add_argument("--topic", default="", help="当前学习主题")
    guide.set_defaults(func=cmd_guide)

    return parser


def main() -> int:
    configure_stdio()
    parser = build_parser()
    if len(sys.argv) == 1:
        return run_guide()
    args = parser.parse_args()
    if not hasattr(args, "func"):
        return run_guide()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
