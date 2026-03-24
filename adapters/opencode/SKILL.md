---
name: dingtalk-attendance
description: 在 OpenCode 中，当用户要求进入钉钉考勤页、执行上班卡或下班卡，或处理钉钉页面异常导航时使用。
---

# DingTalk Attendance For OpenCode

这是 OpenCode 适配层。核心脚本仍然是 `python3 scripts/run.py`，协议定义统一来自 `docs/protocol.md`。

## 适配目标

- 让 OpenCode 把用户指令映射到核心命令
- 不在适配层复制核心状态机
- 当本地 OCR 或导航失败时，依赖统一的 `needs_model_input` 流程

## 指令映射

- “打开考勤页”“进入钉钉工作台并打开考勤打卡” -> `open`
- “上班打卡”“打上班卡” -> `clock-in`
- “下班打卡”“打下班卡” -> `clock-out`
- 仅在用户明确要求真实执行时追加 `--execute`

## 处理约束

- 默认 `dry_run`
- 若返回 `already_done`，直接反馈
- 若返回 `needs_confirmation`，先征求用户是否再次执行
- 若返回 `needs_model_input`，只允许从 `model_handoff.allowed_actions` 中选一个动作
- 单步动作后必须重新调用 `open-step`、`status`、`clock-in` 或 `clock-out`

## 命令入口

```bash
python3 scripts/run.py open --json
python3 scripts/run.py clock-in --json
python3 scripts/run.py clock-out --json
python3 scripts/run.py open-step --json
python3 scripts/run.py status --json
python3 scripts/run.py retry-local-install --json
```

## 安装提示

- 将 `core/dingtalk-attendance` 复制到 OpenCode 的技能目录
- 将本文件作为入口 `SKILL.md`
- `docs/protocol.md` 是统一协议源，不要在 OpenCode 适配层重复维护状态码语义
