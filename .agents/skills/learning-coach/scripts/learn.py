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

COVERAGE_LEVELS = [
    "核心必讲",
    "重点精讲",
    "支持理解",
    "背景点到为止",
    "本轮不展开",
]

LEVEL_DEFAULTS = {
    "核心必讲": {
        "reason": "直接服务当前学习目标，必须进入主线精讲。",
        "stage": "阶段2",
        "unit": "主线精讲",
        "quiz": "必须进入过程题和阶段题",
        "status": "待学习",
    },
    "重点精讲": {
        "reason": "重要但次于主线，需要完整理解和例子。",
        "stage": "阶段2",
        "unit": "重点展开",
        "quiz": "优先进过程题",
        "status": "待学习",
    },
    "支持理解": {
        "reason": "不是主角，但不补会影响理解主线。",
        "stage": "阶段2",
        "unit": "理解支撑",
        "quiz": "只在服务重点时进入题目",
        "status": "待学习",
    },
    "背景点到为止": {
        "reason": "只需要知道存在和作用，不展开成新主线。",
        "stage": "阶段1",
        "unit": "背景提示",
        "quiz": "默认不单独出题",
        "status": "点到为止",
    },
    "本轮不展开": {
        "reason": "资料里有，但当前轮次先不讲，避免打断主线。",
        "stage": "后续阶段",
        "unit": "暂缓处理",
        "quiz": "当前不出题",
        "status": "后移",
    },
}

ROLE_LIBRARY = {
    "主讲老师": {
        "duty": "建立主线、推进讲解、控制颗粒度和场景边界",
        "when": "始终需要",
        "output": "`study_plan.md`、`session_brief.md`、主线讲解",
    },
    "出题老师": {
        "duty": "负责过程题、阶段题、追问题",
        "when": "需要持续测验时",
        "output": "`quiz_log.md`、`quiz_bank.md`",
    },
    "复盘老师": {
        "duty": "负责错因分析、薄弱点归纳、下一步建议",
        "when": "错误较多或需要持续复盘时",
        "output": "`mistakes.md`、`progress.md`",
    },
    "资料梳理老师": {
        "duty": "负责资料覆盖分层、主次划分和漏点检查",
        "when": "资料多、来源杂时",
        "output": "`materials_index.md`、`coverage_map.md`",
    },
}


def configure_stdio() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")


def run_script(script_path: Path, arguments: list[str]) -> None:
    command = [sys.executable, str(script_path), *arguments]
    subprocess.run(command, check=True)


def clean_text(value: str) -> str:
    return value.encode("utf-8", "replace").decode("utf-8")


def ask_text(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}：").strip()
    return clean_text(value or default)


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


def table_cell(value: str) -> str:
    return clean_text(value).replace("|", "\\|").replace("\n", " ").strip()


def parse_first_number(text: str, default: int) -> int:
    match = re.search(r"(\d+)", text or "")
    if not match:
        return default
    return max(1, int(match.group(1)))


def read_markdown_sections(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return parse_markdown_sections(path.read_text(encoding="utf-8"))


def parse_material_point_entry(raw: str) -> tuple[str, str]:
    text = raw.strip()
    if not text:
        return "", ""
    if "=>" in text:
        material, point = text.split("=>", 1)
    elif "|" in text:
        material, point = text.split("|", 1)
    else:
        return "未指定材料", text
    return material.strip() or "未指定材料", point.strip()


def stringify_coverage_entries(rows: list[dict[str, str]], level: str) -> list[str]:
    result: list[str] = []
    for row in rows:
        if row.get("层级", "") != level:
            continue
        material = row.get("材料", "").strip() or "未指定材料"
        point = row.get("知识点 / 片段", "").strip()
        if point:
            result.append(f"{material}=>{point}")
    return result


def coverage_map_summary(root: Path) -> dict:
    path = planning_dir(root) / "coverage_map.md"
    rows = parse_markdown_table(path)
    counts = {level: 0 for level in COVERAGE_LEVELS}
    materials: list[str] = []
    for row in rows:
        level = row.get("层级", "")
        if level in counts:
            counts[level] += 1
        material = row.get("材料", "").strip()
        if material and material not in materials:
            materials.append(material)
    sections = read_markdown_sections(path)
    return {
        "path": path,
        "rows": rows,
        "counts": counts,
        "total": len(rows),
        "materials": materials,
        "gaps": extract_bullets(sections.get("当前覆盖缺口", "")),
        "next_priority": extract_bullets(sections.get("下一步处理", "")),
    }


def format_coverage_brief(summary: dict) -> str:
    if summary.get("total", 0) == 0:
        return "未建立资料覆盖矩阵"
    counts = summary["counts"]
    return (
        f"核心 {counts['核心必讲']} / 重点 {counts['重点精讲']} / "
        f"支持 {counts['支持理解']} / 背景 {counts['背景点到为止']} / "
        f"后移 {counts['本轮不展开']}"
    )


def study_plan_ready(root: Path) -> bool:
    path = planning_dir(root) / "study_plan.md"
    rows = parse_markdown_table(path)
    if not rows:
        return False

    default_goals = {"认识主题", "核心概念", "应用实践", "复盘测试"}
    default_whys = {
        "先建立整体地图和边界",
        "优先吃透主线和高频重点",
        "把重点放进例子、练习或项目场景",
        "回收薄弱点并验证整体掌握",
    }
    for row in rows:
        if row.get("资料", "").strip() or row.get("产出物", "").strip() or row.get("目标日期", "").strip():
            return True
        goal = row.get("目标", "").strip()
        why = row.get("为什么这样安排", "").strip()
        if goal and goal not in default_goals:
            return True
        if why and why not in default_whys:
            return True
    return False


def agent_team_snapshot(root: Path) -> dict[str, str]:
    sections = read_markdown_sections(planning_dir(root) / "agent_team.md")
    return {
        "recommendation": compact_markdown_value(sections.get("是否建议开启", "")),
        "current": compact_markdown_value(sections.get("当前建议", "")),
    }


def agent_team_configured(root: Path) -> bool:
    snapshot = agent_team_snapshot(root)
    recommendation = snapshot.get("recommendation", "")
    current = snapshot.get("current", "")
    return "待判断" not in recommendation and "待填写" not in current and recommendation != "待确认"


def infer_agent_team(root: Path) -> dict:
    session = read_session_sections(root)
    protocol = read_protocol(root)
    materials = extract_bullets(session.get("当前资料", ""))
    progress_entries = count_progress_entries(planning_dir(root) / "progress.md")
    due_quizzes, due_mistakes = due_review_summary(root)

    roles = ["主讲老师"]
    reasons: list[str] = []

    if len(materials) >= 3:
        roles.append("资料梳理老师")
        reasons.append("当前资料较多，适合单独做覆盖分层和漏点检查。")
    if protocol.get("process_quiz_count") or protocol.get("checkpoint_quiz_count"):
        roles.append("出题老师")
        reasons.append("当前流程包含持续测验，出题职责值得独立出来。")
    if progress_entries >= 2 or due_mistakes:
        roles.append("复盘老师")
        reasons.append("已经进入持续推进或暴露薄弱点，复盘职责开始重要。")

    deduped_roles: list[str] = []
    for role in roles:
        if role not in deduped_roles:
            deduped_roles.append(role)
    roles = deduped_roles

    preference = protocol.get("multi_teacher_default", "auto")
    if preference == "off":
        decision_key = "off"
        decision_label = "单老师即可"
    elif len(roles) >= 4 or (len(roles) >= 3 and len(materials) >= 2):
        decision_key = "on"
        decision_label = "建议开启"
    elif len(roles) >= 3:
        decision_key = "optional"
        decision_label = "可以考虑开启"
    else:
        decision_key = "off"
        decision_label = "单老师即可"

    combo_roles = roles if decision_key != "off" else ["主讲老师"]
    combo = " + ".join(combo_roles)
    fallback = "主讲老师兼顾主线、题目、复盘和资料分层。"
    summary = f"{decision_label}：{combo}"
    return {
        "decision_key": decision_key,
        "decision_label": decision_label,
        "reasons": reasons or ["当前任务复杂度还不高，单老师模式足够。"],
        "roles": roles,
        "combo": combo,
        "fallback": fallback,
        "summary": summary,
    }


def write_coverage_map(
    root: Path,
    topic: str,
    entries_by_level: dict[str, list[str]],
    gaps: list[str],
    next_priority: list[str],
    move_later: list[str],
    background_only: list[str],
) -> Path:
    path = planning_dir(root) / "coverage_map.md"
    lines = [
        "# 资料覆盖矩阵",
        "",
        f"主题：{topic}",
        f"更新日期：{date.today().isoformat()}",
        "",
        "## 分层标准",
        "",
        "- 核心必讲：当前学习目标离不开，必须精讲、必须能复述、通常要进题目。",
        "- 重点精讲：重要但次于主线，需要较完整理解，通常要有例子或追问。",
        "- 支持理解：不是主角，但不补就会影响理解主线，需要简讲。",
        "- 背景点到为止：知道它存在和大致作用即可，不展开成新主线。",
        "- 本轮不展开：资料里有，但当前轮次先不讲，避免打断主线。",
        "",
        "## 覆盖原则",
        "",
        "- 资料中的点默认都要有去处，但不要求平均篇幅。",
        "- 覆盖的目标是“有逻辑地处理全部资料”，不是“每个点都同样细讲”。",
        "- 核心和重点优先进入当前阶段计划。",
        "- 支持理解和背景点只在服务主线时进入讲解或题目。",
        "- 本轮不展开的点也要记录原因，避免之后遗忘。",
        "",
        "## 分层概览",
        "",
    ]

    for level in COVERAGE_LEVELS:
        values = entries_by_level.get(level, [])
        summary = "；".join(values) if values else "暂无"
        lines.append(f"- {level}：{summary}")

    lines.extend([
        "",
        "## 覆盖矩阵",
        "",
        "| 材料 | 知识点 / 片段 | 层级 | 为什么这样分层 | 所属阶段 | 所属单元 | 出题策略 | 当前状态 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ])

    for level in COVERAGE_LEVELS:
        meta = LEVEL_DEFAULTS[level]
        for raw in entries_by_level.get(level, []):
            material, point = parse_material_point_entry(raw)
            if not point:
                continue
            row = (
                f"| {table_cell(material)} | {table_cell(point)} | {table_cell(level)} | "
                f"{table_cell(meta['reason'])} | {table_cell(meta['stage'])} | {table_cell(meta['unit'])} | "
                f"{table_cell(meta['quiz'])} | {table_cell(meta['status'])} |"
            )
            lines.append(row)

    lines.extend([
        "",
        "## 当前覆盖缺口",
        "",
    ])
    if gaps:
        lines.extend(f"- {item}" for item in gaps)
    else:
        lines.append("- 暂无明显缺口。")

    lines.extend([
        "",
        "## 下一步处理",
        "",
        f"- 优先补齐哪些资料点：{'；'.join(next_priority) if next_priority else '待确认'}",
        f"- 哪些点可以后移：{'；'.join(move_later) if move_later else '待确认'}",
        f"- 哪些点只保留背景说明：{'；'.join(background_only) if background_only else '待确认'}",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[写入] {path}")
    return path


def render_role_rows(roles: list[str]) -> list[str]:
    rows: list[str] = []
    for role in roles:
        meta = ROLE_LIBRARY.get(role, {
            "duty": "待补充职责",
            "when": "待补充触发条件",
            "output": "待补充输出",
        })
        rows.append(
            f"| {table_cell(role)} | {table_cell(meta['duty'])} | "
            f"{table_cell(meta['when'])} | {table_cell(meta['output'])} |"
        )
    return rows


def write_agent_team(
    root: Path,
    topic: str,
    decision_label: str,
    reasons: list[str],
    roles: list[str],
    combo: str,
    fallback: str,
) -> Path:
    path = planning_dir(root) / "agent_team.md"
    lines = [
        "# 多老师分工建议",
        "",
        f"主题：{topic}",
        f"更新日期：{date.today().isoformat()}",
        "",
        "## 是否建议开启",
        "",
        f"- 建议：{decision_label}",
        f"- 原因：{'；'.join(reasons) if reasons else '待补充'}",
        "",
        "## 推荐逻辑",
        "",
        "- 只有在单老师明显难以兼顾质量时，才建议开启多老师模式。",
        "- 推荐多老师，不代表必须开启；用户始终可以选择单老师模式。",
        "- 如果资料少、目标单一、只想快速推进，默认不启用。",
        "",
        "## 推荐角色分工",
        "",
        "| 角色 | 主要职责 | 什么时候需要 | 主要输出 |",
        "| --- | --- | --- | --- |",
    ]
    lines.extend(render_role_rows(roles))
    lines.extend([
        "",
        "## 当前建议",
        "",
        f"- 当前最适合的模式：{decision_label}",
        f"- 如果开启多老师，建议最少角色组合：{combo}",
        f"- 如果不开启，多老师职责由谁合并承担：{fallback}",
        "",
        "## 不开启时的单老师补偿",
        "",
        "- 主讲时必须显式兼顾：主线、题目、复盘、资料分层。",
        "- 不能因为单老师模式，就忽略资料覆盖和问题收集。",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[写入] {path}")
    return path


def build_study_plan(root: Path, topic: str) -> Path:
    path = planning_dir(root) / "study_plan.md"
    session = read_session_sections(root)
    coverage = coverage_map_summary(root)
    materials = coverage["materials"] or extract_bullets(session.get("当前资料", ""))
    materials_text = "；".join(materials) if materials else "待补充"
    focus_text = "；".join(extract_bullets(session.get("当前重点", ""))) or "待确认重点"
    goal_text = compact_markdown_value(session.get("当前目标", ""))
    process_every = read_protocol(root).get("process_quiz_every", "待确认")

    rows = [
        ("1", "建立整体地图与资料边界", "先把主线、层级和非目标范围说清，避免一开始就扎进枝节。", materials_text, "覆盖矩阵初稿；主线框架", "", "进行中"),
        ("2", "吃透核心与重点", "围绕核心必讲和重点精讲内容展开，这是主线学习收益最高的阶段。", materials_text, f"重点笔记；围绕“{focus_text}”的过程题", "", "未开始"),
        ("3", "应用、表达与迁移", "把重点放进例子、练习、项目或表达场景，避免只停留在知道定义。", materials_text, "例子或练习；表达框架", "", "未开始"),
        ("4", "复盘、测验与收束", "回收薄弱点，验证整体掌握，再决定下一轮范围。", materials_text, f"阶段测验；复盘结论；下一轮建议", "", "未开始"),
    ]

    lines = [
        "# 学习计划",
        "",
        f"主题：{topic}",
        f"更新日期：{date.today().isoformat()}",
        "",
        "## 规划原则",
        "",
        "- 先建立整体地图，再细化阶段和当前学习块。",
        "- 资料中的点默认都要有去处，但不要求平均用力。",
        "- 优先使用 `coverage_map.md` 做资料点分层，再据此安排阶段。",
        "- 核心和重点内容进入主线精讲；支持理解和背景内容按需要简讲；明确非目标内容先不展开。",
        "",
        "## 资料覆盖策略",
        "",
        f"- 核心必讲：{coverage['counts']['核心必讲']} 项",
        f"- 重点精讲：{coverage['counts']['重点精讲']} 项",
        f"- 支持理解：{coverage['counts']['支持理解']} 项",
        f"- 背景点到为止：{coverage['counts']['背景点到为止']} 项",
        f"- 本轮不展开：{coverage['counts']['本轮不展开']} 项",
        "",
        "## 阶段安排",
        "",
        "| 阶段 | 目标 | 为什么这样安排 | 资料 | 产出物 | 目标日期 | 状态 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]

    for stage, goal, why, materials_value, outputs, target_date, status in rows:
        lines.append(
            f"| {stage} | {table_cell(goal)} | {table_cell(why)} | {table_cell(materials_value)} | "
            f"{table_cell(outputs)} | {table_cell(target_date)} | {table_cell(status)} |"
        )

    lines.extend([
        "",
        "## 阶段到资料层级映射",
        "",
        "| 阶段 | 主要覆盖层级 | 说明 |",
        "| --- | --- | --- |",
        "| 1 | 核心必讲 / 背景点到为止 / 本轮不展开 | 先搭主线并控边界，不深挖枝节 |",
        "| 2 | 核心必讲 / 重点精讲 / 支持理解 | 这是主线精讲阶段 |",
        "| 3 | 重点精讲 / 支持理解 / 背景点到为止 | 进入应用、表达和迁移 |",
        "| 4 | 核心必讲 / 重点精讲 | 用复盘和测试收束主线 |",
        "",
        "## 当前聚焦点",
        "",
        "- 当前阶段：阶段 1",
        f"- 当前单元：{goal_text if goal_text != '待确认' else '先完成资料分层和主线梳理'}",
        f"- 下一个检查点：按学习协议在 {process_every} 后检查是否进入过程测验",
        "",
    ])

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"[写入] {path}")
    return path


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

    materials = extract_bullets(session_sections.get("当前资料", ""))
    coverage = coverage_map_summary(root)
    if materials and coverage["total"] == 0:
        return {
            "key": "coverage",
            "message": "当前已有资料，但还没做覆盖分层。建议先把资料点分成核心、重点、支持和背景，再继续推进。",
        }

    if not study_plan_ready(root):
        return {
            "key": "plan",
            "message": "建议先根据当前资料和覆盖层级生成阶段学习计划，再进入具体学习块。",
        }

    inferred_team = infer_agent_team(root)
    if inferred_team["decision_key"] in {"on", "optional"} and not agent_team_configured(root):
        return {
            "key": "team",
            "message": f"当前任务复杂度已足够，{inferred_team['decision_label']}多老师分工，建议先确认角色安排。",
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
    coverage = coverage_map_summary(root)
    inferred_team = infer_agent_team(root)
    team_ready = agent_team_configured(root)
    plan_ready = study_plan_ready(root)

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
    print(f"- 资料覆盖：{format_coverage_brief(coverage)}")
    print(f"- 学习计划：{'已细化' if plan_ready else '待细化'}")
    print(f"- 多老师建议：{inferred_team['summary']}")
    print(f"- 分工方案：{'已记录' if team_ready else '待确认'}")
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


def run_coverage_wizard(root: Path, topic: str, args: argparse.Namespace | None = None) -> None:
    rows = coverage_map_summary(root)["rows"]
    args = args or argparse.Namespace()

    print("现在开始做资料覆盖分层。默认要求资料里的点都有去处，但不是每个点都同样细讲。")
    defaults = {level: stringify_coverage_entries(rows, level) for level in COVERAGE_LEVELS}
    entries_by_level = {
        "核心必讲": ask_list("核心必讲条目（格式：材料=>知识点）", getattr(args, "core", []) or defaults["核心必讲"]),
        "重点精讲": ask_list("重点精讲条目（格式：材料=>知识点）", getattr(args, "key", []) or defaults["重点精讲"]),
        "支持理解": ask_list("支持理解条目（格式：材料=>知识点）", getattr(args, "support", []) or defaults["支持理解"]),
        "背景点到为止": ask_list("背景点到为止条目（格式：材料=>知识点）", getattr(args, "background", []) or defaults["背景点到为止"]),
        "本轮不展开": ask_list("本轮不展开条目（格式：材料=>知识点）", getattr(args, "defer", []) or defaults["本轮不展开"]),
    }
    gaps = ask_list("当前覆盖缺口（可留空）", getattr(args, "gap", []) or [])
    next_priority = ask_list("优先补齐哪些资料点", getattr(args, "next_priority", []) or [])
    move_later = ask_list("哪些点可以后移", getattr(args, "move_later", []) or [])
    background_only = ask_list("哪些点只保留背景说明", getattr(args, "background_only", []) or [])

    write_coverage_map(root, topic, entries_by_level, gaps, next_priority, move_later, background_only)
    print()
    print(f"覆盖分层已完成：{format_coverage_brief(coverage_map_summary(root))}")


def run_team_wizard(root: Path, topic: str, args: argparse.Namespace | None = None) -> None:
    inferred = infer_agent_team(root)
    args = args or argparse.Namespace()

    print(f"系统初步判断：{inferred['summary']}")
    decision = ask_choice(
        "当前是否建议开启多老师模式",
        [("on", "建议开启"), ("optional", "可以考虑开启"), ("off", "单老师即可")],
        getattr(args, "decision", "") or inferred["decision_key"],
    )
    decision_label = {
        "on": "建议开启",
        "optional": "可以考虑开启",
        "off": "单老师即可",
    }[decision]
    reasons = ask_list("推荐原因", getattr(args, "reason", []) or inferred["reasons"])
    roles = ask_list("建议保留的角色", getattr(args, "role", []) or inferred["roles"])
    combo = ask_text("如果开启多老师，建议最少角色组合", getattr(args, "combo", "") or inferred["combo"])
    fallback = ask_text("如果不开启，多老师职责由谁合并承担", getattr(args, "fallback", "") or inferred["fallback"])

    write_agent_team(root, topic, decision_label, reasons, roles, combo, fallback)
    print()
    print(f"当前分工建议已更新：{decision_label}")


def build_current_block(root: Path, unit_hint: str = "") -> Path:
    pdir = planning_dir(root)
    protocol = read_protocol(root)
    session = read_session_sections(root)
    latest = read_latest_progress(pdir / "progress.md")
    block_path = pdir / "current_block.md"

    focus_items = extract_bullets(session.get("当前重点", ""))
    materials = extract_bullets(session.get("当前资料", ""))
    non_goals = extract_bullets(session.get("当前非目标", ""))
    coverage = coverage_map_summary(root)
    inferred_team = infer_agent_team(root)
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
- 资料覆盖：{format_coverage_brief(coverage)}
- 当前分工建议：{inferred_team["summary"]}

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
    output_format = ask_choice(
        "输出格式",
        [("markdown", "Markdown"), ("json", "JSON")],
        getattr(args, "output_format", "") or "markdown",
    )
    output_name = ask_text("输出文件名", getattr(args, "output_name", "") or "")

    quiz_args = [
        "--root", str(root),
        "--topic", topic,
        "--scene", scene,
        "--output-format", output_format,
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
                ("coverage", "做资料覆盖分层"),
                ("plan", "生成阶段学习计划"),
                ("team", "确认多老师分工建议"),
                ("block", "查看当前学习块建议"),
                ("record", "记录刚学完的一块"),
                ("quiz", "生成一轮测验"),
                ("review", "查看待复习项"),
                ("align", "重新对齐当前学习会话"),
                ("protocol", "调整学习协议"),
                ("status", "再看一次当前状态"),
                ("quit", "退出引导模式"),
            ],
            rec["key"] if rec["key"] in {"coverage", "plan", "team", "block", "record", "quiz", "review", "align", "protocol", "status"} else "status",
        )

        if action == "coverage":
            run_coverage_wizard(root, topic)
        elif action == "plan":
            build_study_plan(root, topic)
        elif action == "team":
            run_team_wizard(root, topic)
        elif action == "block":
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


def cmd_coverage(args: argparse.Namespace) -> int:
    root, topic = ensure_workspace(args.root, args.topic)
    run_coverage_wizard(root, topic, args)
    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    root, topic = ensure_workspace(args.root, args.topic)
    build_study_plan(root, topic)
    return 0


def cmd_team(args: argparse.Namespace) -> int:
    root, topic = ensure_workspace(args.root, args.topic)
    run_team_wizard(root, topic, args)
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

    coverage = subparsers.add_parser("coverage", help="整理资料覆盖分层")
    coverage.add_argument("--root", default="", help="项目或笔记根目录")
    coverage.add_argument("--topic", default="", help="当前学习主题")
    coverage.add_argument("--core", action="append", default=[], help="核心必讲条目，格式：材料=>知识点")
    coverage.add_argument("--key", action="append", default=[], help="重点精讲条目，格式：材料=>知识点")
    coverage.add_argument("--support", action="append", default=[], help="支持理解条目，格式：材料=>知识点")
    coverage.add_argument("--background", action="append", default=[], help="背景点到为止条目，格式：材料=>知识点")
    coverage.add_argument("--defer", action="append", default=[], help="本轮不展开条目，格式：材料=>知识点")
    coverage.add_argument("--gap", action="append", default=[], help="当前覆盖缺口")
    coverage.add_argument("--next-priority", action="append", default=[], help="优先补齐项")
    coverage.add_argument("--move-later", action="append", default=[], help="可后移项")
    coverage.add_argument("--background-only", action="append", default=[], help="只保留背景说明的项")
    coverage.set_defaults(func=cmd_coverage)

    plan = subparsers.add_parser("plan", help="生成阶段学习计划")
    plan.add_argument("--root", default="", help="项目或笔记根目录")
    plan.add_argument("--topic", default="", help="当前学习主题")
    plan.set_defaults(func=cmd_plan)

    team = subparsers.add_parser("team", help="确认多老师分工建议")
    team.add_argument("--root", default="", help="项目或笔记根目录")
    team.add_argument("--topic", default="", help="当前学习主题")
    team.add_argument("--decision", default="", help="on / optional / off")
    team.add_argument("--reason", action="append", default=[], help="推荐原因")
    team.add_argument("--role", action="append", default=[], help="建议保留的角色")
    team.add_argument("--combo", default="", help="建议最少角色组合")
    team.add_argument("--fallback", default="", help="不开启时的合并承担方式")
    team.set_defaults(func=cmd_team)

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
    quiz.add_argument("--output-format", default="", help="输出格式：markdown 或 json")
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
