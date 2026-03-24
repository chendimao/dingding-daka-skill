---
name: dingtalk-attendance
description: 在 OpenClaw 中，当用户要求通过 adb 自动打开钉钉考勤页、打卡或处理页面异常时使用。
---

# DingTalk Attendance For OpenClaw

OpenClaw 适配层的重点不是重写核心逻辑，而是正确消费核心脚本输出的统一 JSON 协议。

## 核心原则

- 所有实际动作都由 `python3 scripts/run.py` 执行
- OpenClaw 负责解释 `status`、`message`、`fallback_reason`、`model_handoff`
- 若返回 `needs_model_input`，OpenClaw 只做一步视觉判断
- 单步动作后必须重新调用核心命令，不能假设页面已到目标状态

## 常用入口

```bash
python3 scripts/run.py open --json
python3 scripts/run.py clock-in --json
python3 scripts/run.py clock-out --json
python3 scripts/run.py open-step --json
python3 scripts/run.py model-action --action tap-workbench --json
```

## 状态处理

- `attendance_ready`：告诉用户已到考勤页
- `dry_run_ready`：告诉用户已经识别到目标按钮，但当前未真实点击
- `completed`：告诉用户动作已完成
- `already_done`：告诉用户当前卡已打过
- `needs_confirmation`：要求用户确认是否再次打下班卡
- `needs_model_input`：查看截图，并按 `allowed_actions` 只执行一步

## 安装提示

- 将 `core/dingtalk-attendance` 复制到 OpenClaw 的技能目录
- 将本文件作为 OpenClaw 的 `SKILL.md`
- `docs/protocol.md` 是协议唯一来源，适配层不要复制或改写字段定义
