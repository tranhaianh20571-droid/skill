# 学习教练 Skill

这是一个给 Codex 终端环境使用的可复用学习工作流 skill。

它适合这样的场景：

- 你提供学习目标、资料、时间约束
- Codex 不只是回答一次问题
- 而是像一位循循善诱的中国老师一样，先帮你搭框架，再分阶段推进、定期测验、持续记录和调整

这个 skill 不只适用于代码学习，也适用于项目理解、面试准备、读论文、读书、概念入门等陌生内容学习。

## 功能

- 开场先做学习配置，而不是直接长篇讲解
- 对齐学习目标、资料、颗粒度、重点、当前场景和非目标范围
- 先建立大框架，再细化当前阶段和当前学习块
- 自动记录学习协议、学习计划、进度、题目、错题、调整和问题
- 讲解和出题优先基于材料，减少幻觉和无关展开
- 只有在“不补充就学不懂”时才补必要背景
- 支持建议是否启用多老师模式
- 终端里可持续引导，不需要每一步都自己想命令
- 题目会同时输出 Markdown 和 JSON，方便后续接 UI

## 仓库结构

```text
.agents/skills/learning-coach/
├── SKILL.md
├── agents/openai.yaml
├── assets/templates/
├── references/
└── scripts/

tools/
├── install-learning-coach.ps1
└── install-learning-coach.sh
```

## 安装

### Windows PowerShell

在仓库根目录执行：

```powershell
.\tools\install-learning-coach.ps1
```

如果本机已经装过旧版本，想覆盖安装：

```powershell
.\tools\install-learning-coach.ps1 -Force
```

### macOS / Linux

在仓库根目录执行：

```bash
chmod +x ./tools/install-learning-coach.sh
./tools/install-learning-coach.sh
```

如果本机已经装过旧版本，想覆盖安装：

```bash
./tools/install-learning-coach.sh --force
```

安装完成后，skill 会被放到：

```text
~/.codex/skills/learning-coach
```

Windows 默认对应：

```text
C:\Users\<你的用户名>\.codex\skills\learning-coach
```

## 最推荐的使用方式

安装后，直接在 Codex 里用自然语言触发：

```text
使用 $learning-coach，帮我基于这些资料建立一个完整学习流程
```

或者：

```text
使用 $learning-coach。我想学习 XXX，这是我的资料和目标。你先像老师一样帮我完成第一次配置。
```

第一次使用时，它会先和你确认：

- 学习目标
- 当前基础
- 学习资料
- 时间节奏
- 讲解颗粒度
- 当前重点
- 当前场景
- 非目标内容
- 什么算一块内容
- 几块后测试
- 每次几题
- 什么时候停下来确认

## 命令行入口

如果你想显式用脚本，也可以直接运行：

```bash
python ~/.codex/skills/learning-coach/scripts/learn.py
```

Windows 下也可以写成：

```powershell
python "$HOME\.codex\skills\learning-coach\scripts\learn.py"
```

无子命令时，会直接进入持续引导模式。

常用子命令：

```bash
python ~/.codex/skills/learning-coach/scripts/learn.py start
python ~/.codex/skills/learning-coach/scripts/learn.py status --root "<学习目录>"
python ~/.codex/skills/learning-coach/scripts/learn.py next --root "<学习目录>"
python ~/.codex/skills/learning-coach/scripts/learn.py review --root "<学习目录>"
python ~/.codex/skills/learning-coach/scripts/learn.py block --root "<学习目录>"
python ~/.codex/skills/learning-coach/scripts/learn.py quiz --root "<学习目录>"
```

说明：

- `start`、`protocol`、`align`、`quiz`、`record` 更偏向向导式入口
- `status`、`next`、`review`、`block` 更偏向直接输出当前状态和建议
- 如果你不想自己判断用哪个命令，直接运行 `learn.py` 即可

## 初始化后会生成什么

学习目录里会生成一套 planning 文件，默认在：

```text
.codex/planning/
```

核心文件包括：

- `study_plan.md`
- `progress.md`
- `findings.md`
- `mistakes.md`
- `quiz_log.md`
- `quiz_bank.md`
- `materials_index.md`
- `learning_protocol.md`
- `session_brief.md`
- `grounding_log.md`
- `adjustment_log.md`
- `issue_log.md`

## 适合的学习任务

- 学代码和项目
- 面试准备
- 读课程资料
- 读书和论文
- 进入完全陌生的新主题
- 需要长期记录和复盘的学习任务

## 发布说明

这是一个以 skill 形式交付的完整学习系统。

它不是独立 app，也不是单纯提示词模板，而是：

- skill
- 脚本
- 模板
- 持久化学习文件

组合起来的一套终端学习工作流。
