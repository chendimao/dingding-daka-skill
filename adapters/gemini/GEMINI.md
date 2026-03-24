# Gemini CLI 适配说明

本仓库对 Gemini CLI 的适配方式是“核心脚本共用，Gemini 只做协议消费与单步决策”。

## 触发条件

- 打开钉钉并进入考勤打卡页
- 上班打卡 / 打上班卡
- 下班打卡 / 打下班卡
- 关闭弹窗、暂不更新、返回到有底部 tabs 的页面

## 执行规则

- 在技能目录 `dingtalk-attendance` 内执行 `python3 scripts/run.py`
- 默认 `--json`
- 直接指令可以直接执行 `clock-in` / `clock-out`
- 非直接指令优先执行 `open`
- 默认保持 `dry_run`
- 只有用户明确要求真实执行时才追加 `--execute`

## 模型介入规则

- 若脚本返回 `needs_model_input`，Gemini 只做一步视觉判断
- 只允许从 `model_handoff.allowed_actions` 中选一个动作
- 动作后必须重新执行 `open-step`、`status`、`clock-in` 或 `clock-out`
- 协议字段含义以 `docs/protocol.md` 为准

## 安装方式

- 将 `core/dingtalk-attendance` 复制到 Gemini CLI 的技能目录
- 使用本文件作为 Gemini 侧入口说明
