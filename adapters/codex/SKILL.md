---
name: dingtalk-attendance
description: 在 Codex 中，当用户要求打开钉钉考勤页、打上班卡、打下班卡，或处理钉钉内弹窗与误入页面返回时使用。
---

# DingTalk Attendance For Codex

这是 Codex 适配层入口文档。核心实现位于 `core/dingtalk-attendance`，稳定协议见 `docs/protocol.md`。

## 触发场景

- 打开钉钉并进入考勤打卡页
- 上班打卡 / 打上班卡
- 下班打卡 / 打下班卡
- 关闭更新弹窗、广告弹窗
- 左上角返回直到回到底部 tabs，再继续导航

## 调用规则

- 在技能目录 `dingtalk-attendance` 内执行 `python3 scripts/run.py`
- 直接指令“上班打卡 / 打上班卡 / 下班打卡 / 打下班卡”可直接执行对应命令
- 默认保持 `dry_run`
- 只有用户明确要求真实打卡时，才追加 `--execute`
- 如果返回 `needs_model_input`，只执行一步动作，再重新读取状态

## 常用命令

```bash
python3 scripts/run.py open --json
python3 scripts/run.py clock-in --json
python3 scripts/run.py clock-out --json
python3 scripts/run.py clock-in --execute --json
python3 scripts/run.py clock-out --execute --json
python3 scripts/run.py open-step --json
python3 scripts/run.py status --json
```

## 结果处理

- `attendance_ready`：已进入考勤页
- `dry_run_ready`：识别到目标按钮，但没有真实点击
- `completed`：已完成真实点击
- `already_done`：当前卡已打过
- `needs_confirmation`：通常表示下班卡已打过，先问用户
- `needs_unlock_password`：缺少锁屏密码
- `unlock_password_invalid`：缓存密码错误，需要重新输入
- `unsupported_lock_type`：锁屏方式不支持
- `needs_model_input`：查看截图并按 `model_handoff.allowed_actions` 只执行一步

## 安装提示

- 将 `core/dingtalk-attendance` 复制到 Codex 的技能目录，并保留目录名 `dingtalk-attendance`
- 将本文件作为该目录的 `SKILL.md`
- 不要把协议定义写死在适配层，统一引用 `docs/protocol.md`
