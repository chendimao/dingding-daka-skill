# 钉钉考勤统一协议

本文档定义 `core/dingtalk-attendance/scripts/run.py` 的稳定 JSON 输出协议。`codex`、`opencode`、`claude`、`gemini`、`openclaw` 等适配层都应优先依赖这里定义的字段和状态，而不是各自重复发明状态机。

## 基本约定

- 所有命令都应尽量输出 JSON 对象
- 适配层优先读取 `status`
- 用户可见说明优先读取 `message`
- 当存在截图分析或模型兜底时，优先读取 `fallback_reason` 与 `model_handoff`
- 当命令处于测试模式时，应保留 `dry_run: true`
- 当涉及设备缓存、锁屏密码或设备选择时，应带出 `serial`
- 当前运行模式由 `mode` 表示，例如 `local` 或 `model_fallback`

## 稳定字段

| 字段 | 含义 |
| --- | --- |
| `status` | 当前步骤的机器可读状态码 |
| `message` | 给上层或用户展示的中文说明 |
| `dry_run` | 是否为只识别不真实点击的测试模式 |
| `serial` | 当前命中的设备序列号 |
| `mode` | 当前运行模式，例如本地识别或模型兜底 |
| `fallback_reason` | 本地识别失败或无法继续自动化时的原因 |
| `model_handoff` | 需要模型参与判断时的单步交接信息 |

## 常见状态码

| `status` | 说明 |
| --- | --- |
| `attendance_ready` | 已进入考勤打卡页面 |
| `dry_run_ready` | 已识别到目标按钮，但当前为测试模式，没有真实点击 |
| `completed` | 已执行真实点击，并通过页面复检 |
| `already_done` | 页面已显示当前动作完成，例如已打上班卡 |
| `needs_confirmation` | 通常表示下班卡已打过，必须先询问用户是否继续 |
| `needs_unlock_password` | 检测到锁屏，但当前没有可用数字 PIN |
| `unlock_password_invalid` | 当前缓存或传入的密码错误，已自动清空缓存 |
| `unsupported_lock_type` | 当前锁屏方式不是无锁屏或数字 PIN |
| `needs_model_input` | 本地流程无法继续，需要模型查看截图并做一步判断 |
| `config` | 当前返回的是运行配置或缓存状态 |
| `lock_password_updated` | 锁屏密码缓存更新成功 |
| `lock_password_cleared` | 锁屏密码缓存清除成功 |

## `fallback_reason` 语义

| `fallback_reason` | 说明 |
| --- | --- |
| `local_ocr_returned_no_text_boxes` | 本地 OCR 没识别到可用文本 |
| `navigation_target_not_found_locally` | 本地识别没找到工作台或考勤入口 |
| `attendance_action_not_found_locally` | 已进入考勤页，但没识别到上班 / 下班动作 |
| `open_step_requires_model_judgement` | 当前页面需要模型做一步判断 |
| `navigation_retry_exhausted` | 自动导航重试次数耗尽 |

## `model_handoff` 约定

当 `status = needs_model_input` 时，返回值中应包含 `model_handoff`。适配层必须把它视为“只允许一步动作”的明确约束。

```json
{
  "status": "needs_model_input",
  "message": "当前页面需要模型辅助判断",
  "fallback_reason": "open_step_requires_model_judgement",
  "dry_run": true,
  "serial": "emulator-5554",
  "mode": "model_fallback",
  "model_handoff": {
    "image_path": "/tmp/dingtalk-attendance.png",
    "allowed_actions": [
      "tap-workbench",
      "tap-app-center",
      "tap-attendance-entry",
      "tap-back-icon",
      "back",
      "tap"
    ],
    "prompt": "只允许从 allowed_actions 中选一个动作，执行后重新读取页面状态。"
  }
}
```

## 单步动作规则

- `needs_model_input` 不是“让模型直接完成整条链路”，而是只交出一步动作决策
- 适配层必须优先遵守 `model_handoff.allowed_actions`
- 每次只允许执行一个动作
- 动作执行后必须重新运行 `open-step`、`status`、`clock-in` 或 `clock-out`
- 如果页面已经显示“已打上班卡”，应返回 `already_done`
- 如果页面已经显示“已打下班卡”，应返回 `needs_confirmation`，由上层先询问用户

## 上层适配建议

- 直接指令如“上班打卡 / 打上班卡 / 下班打卡 / 打下班卡”，可以直接映射到 `clock-in` 或 `clock-out`
- 若用户只是要求进入考勤页或查看状态，应先运行 `open`
- 默认保持 `dry_run`
- 只有当用户明确要求真实执行时，才追加 `--execute`
