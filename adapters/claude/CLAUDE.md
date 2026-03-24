# Claude Code 适配说明

本仓库的钉钉考勤能力由 `core/dingtalk-attendance` 提供，Claude Code 侧只负责把用户请求映射到核心命令。

## 何时调用

- 用户要求打开钉钉考勤页
- 用户要求上班打卡 / 打上班卡
- 用户要求下班打卡 / 打下班卡
- 用户要求处理钉钉中的更新弹窗、广告弹窗或误入页面返回

## 调用方式

- 在技能目录 `dingtalk-attendance` 内运行 `python3 scripts/run.py`
- 默认用 `--json`
- 直接指令可直接触发 `clock-in` 或 `clock-out`
- 默认不要加 `--execute`
- 只有用户明确要求真实打卡时，才加 `--execute`

## 处理协议

- 所有状态码与字段语义统一以 `docs/protocol.md` 为准
- 若返回 `needs_model_input`，只能根据 `model_handoff.allowed_actions` 执行一步
- 执行动作后必须重新读取页面状态
- 若返回 `needs_confirmation`，先征求用户确认

## 安装方式

- 将 `core/dingtalk-attendance` 复制到 Claude Code 的技能目录
- 将本说明合并到你的全局或仓库级 `CLAUDE.md`
- 不要在 `CLAUDE.md` 中复制整套状态机，只引用核心命令和统一协议
