---
name: dingtalk-attendance
description: 在用户要打开钉钉考勤页面、打上班卡、打下班卡，或在钉钉考勤自动化过程中处理弹窗、更新提示、误入页面返回时使用。
---

# DingTalk Attendance

这是核心参考版说明，主要描述共用脚本能力和状态机约束。面向具体 CLI 的发布入口见仓库 `adapters/` 目录。

使用这个 skill 时，优先让脚本处理 `adb`、页面判断和本地识别；只有当脚本明确返回 `needs_model_input` 时，才让当前模型查看截图并决定下一步点击。

## 何时使用

- 用户要进入钉钉考勤打卡页
- 用户要打上班卡
- 用户要打下班卡
- 钉钉里出现广告弹窗、更新弹窗、误触其他页面，需要自动恢复

## 安全规则

- 当用户提示词是 `上班打卡 / 打上班卡 / 下班打卡 / 打下班卡` 这类直接指令时，可直接执行对应打卡动作，不需要额外确认。
- `打下班卡` 时，如果脚本或页面状态显示已经打过下班卡，必须停止并询问用户是否继续，不能默认重复打卡。
- `打上班卡` 时，如果已经打过卡，直接反馈即可，不要重复点击。
- `clock-in` / `clock-out` 默认是测试模式，只识别按钮、不真实点击；只有显式加 `--execute` 才允许真实打卡。
- 如果当前是在测试、联调或验收流程，默认只导航到考勤页，不要真实点击打卡按钮，除非用户明确要求真实打卡并显式加 `--execute`。
- 当脚本返回 `needs_model_input` 时，只做单步判断和单步操作，不要在没有新校验的情况下连续盲点。

## 直接命令

从 skill 根目录调用：

```bash
python3 scripts/run.py open --json
python3 scripts/run.py open-step --json
python3 scripts/run.py clock-in --json
python3 scripts/run.py clock-out --json
python3 scripts/run.py clock-in --execute --json
python3 scripts/run.py clock-out --execute --json
python3 scripts/run.py retry-local-install --json
python3 scripts/run.py show-config --json
python3 scripts/run.py set-lock-password --password 000000 --json
python3 scripts/run.py clear-lock-password --json
```

辅助命令：

```bash
python3 scripts/run.py status --json
python3 scripts/run.py back --json
python3 scripts/run.py tap-workbench --json
python3 scripts/run.py scroll-workbench-top --json
python3 scripts/run.py tap-app-center --json
python3 scripts/run.py tap-attendance-entry --json
python3 scripts/run.py tap-back-icon --json
python3 scripts/run.py model-action --action tap-workbench --json
python3 scripts/run.py tap --x 100 --y 200 --json
```

配置管理：

```bash
python3 scripts/run.py show-config --json
python3 scripts/run.py set-lock-password --password 000000 --json
python3 scripts/run.py set-lock-password --serial <serial> --password 000000 --json
python3 scripts/run.py clear-lock-password --json
python3 scripts/run.py clear-lock-password --serial <serial> --json
```

## 默认流程

1. 运行目标命令：`open`、`clock-in` 或 `clock-out`
   - 如果原始用户提示词是直接指令，`clock-in` / `clock-out` 可以直接执行
   - 如果设备当前处于锁屏状态，脚本会先尝试解锁，再继续导航
2. 如果返回 `attendance_ready`、`completed`、`already_done` 或 `needs_confirmation`，直接按结果回复用户
   - 如果返回 `needs_unlock_password`，说明检测到锁屏且还没有可用密码，需要先补充锁屏密码再重试
   - 如果返回 `unlock_password_invalid`，说明当前密码校验失败，缓存已清空，需要重新提供正确密码
   - 如果返回 `unsupported_lock_type`，说明当前锁屏方式不是数字 PIN，脚本不会继续尝试
   - 如果返回 `dry_run_ready`，说明已经识别到可点击按钮，但当前仍在测试模式，没有真实点击
   - 如果返回 `config`，说明已经读取到当前运行配置和缓存状态
   - 如果返回 `lock_password_updated` / `lock_password_cleared`，说明当前设备缓存已经更新
3. 如果先要判断用户提示词是否属于直接执行，可先运行：

```bash
python3 scripts/run.py intent --text "打下班卡" --json
```

返回 `auto_execute: true` 时，可直接执行对应命令。
4. 如果返回 `needs_model_input`：
   - 查看返回的 `screenshot_path`
   - 优先读取返回的 `model_handoff.prompt`
   - 使用 `model_handoff.image_path` 让当前模型看图
   - 严格限制在 `model_handoff.allowed_actions` 中只选择一个动作
   - 优先使用 `python3 scripts/run.py model-action --action <动作名> --json` 执行并回传新的页面状态
   - 优先运行 `python3 scripts/run.py open-step --json`
   - 如果 `open-step` 仍然返回 `needs_model_input`，再根据截图判断应该关闭弹窗、点左上角返回、点工作台、点考勤打卡，还是点上班卡/下班卡
   - 只执行一个动作
   - 动作后重新运行原命令或 `status`
5. 如果当前页是工作台，但看起来停在可上下滑动的中间区域，优先先执行：

```bash
python3 scripts/run.py scroll-workbench-top --json
```

再继续运行 `open-step` 或 `open`

## 锁屏密码

- 脚本当前只支持两种情况：
  - 无锁屏
  - 数字 PIN 锁屏
- 图案锁、字母数字密码、厂商自定义复杂锁屏，都会返回 `unsupported_lock_type`，不会盲试。
- 脚本会先检查设备当前是否处于系统锁屏页；如果没有锁屏，直接继续后续流程。
- 如果检测到锁屏：
  - 先读取环境变量 `DINGTALK_ATTENDANCE_LOCK_PASSWORD`
  - 如果环境变量没有，再读取运行时配置里的当前设备缓存密码
  - 两者都没有时，返回 `needs_unlock_password`
- 第一次运行时，推荐这样提供锁屏密码：

```bash
DINGTALK_ATTENDANCE_LOCK_PASSWORD=000000 python3 scripts/run.py open --json
```

- 解锁成功后，密码会缓存到：

```bash
系统安全存储
```

- 后续再次运行时，如果设备仍然锁屏，脚本会优先复用当前设备的已缓存密码，不需要用户再次输入。
- 公开发布版不再把锁屏密码写入 `.runtime/config.json`。
- 密码缓存按设备 `serial` 隔离，不同手机不会共用一份锁屏密码。
- macOS 使用 Keychain，Windows 使用 Credential Manager，Linux 使用 Secret Service。
- 如果当前系统没有可用安全存储能力，`set-lock-password` 会直接报错，不会降级到明文文件缓存。
- 如果缓存密码错误，脚本会返回 `unlock_password_invalid`，并自动清空当前设备的安全存储记录，避免后续重复使用错误密码。
- 当用户明确更新了新的锁屏密码后，再次通过环境变量传入一次即可，成功后会自动刷新缓存。
- 如果要手动维护缓存，优先使用：

```bash
python3 scripts/run.py show-config --json
python3 scripts/run.py set-lock-password --password 000000 --json
python3 scripts/run.py clear-lock-password --json
```

## 本地识别与降级

- 脚本默认尝试本地模式
- Windows / Linux 优先使用 `PaddleOCR + OpenCV`
- macOS 优先使用 `RapidOCR + OpenCV`
- 本地 OCR 依赖安装失败后，会记住 `model_fallback` 模式
- 后续默认直接走模型兜底，除非用户明确要求“重试本地安装”
- 本地 OCR 本轮识别失败时，也会直接返回 `needs_model_input`，并带上 `fallback_reason`
- 当用户说“重试本地安装”或“恢复本地识别”时，运行：

```bash
python3 scripts/run.py retry-local-install --json
```

## 模型兜底处理

当脚本返回 `needs_model_input` 时：

1. 查看截图
2. 优先读取返回的 `model_handoff`：

```json
{
  "image_path": "...",
  "allowed_actions": ["tap-workbench", "tap-app-center", "tap-attendance-entry", "tap-back-icon", "back", "tap"],
  "prompt": "..."
}
```

3. 先尝试：

```bash
python3 scripts/run.py open-step --json
```

4. 如果 `open-step` 仍然无法推进，再优先判断这些目标：
   - 关闭广告弹窗
   - 暂不更新 / 以后再说
   - 左上角返回
   - 工作台
   - 考勤打卡
   - 上班打卡
   - 下班打卡
5. 模型选好动作后，优先使用：

```bash
python3 scripts/run.py model-action --action tap-workbench --json
python3 scripts/run.py model-action --action tap-app-center --json
python3 scripts/run.py model-action --action tap-attendance-entry --json
python3 scripts/run.py model-action --action tap-back-icon --json
python3 scripts/run.py model-action --action back --json
python3 scripts/run.py model-action --action tap --x 100 --y 200 --json
```

6. 推荐先使用这些安全命令，而不是手写坐标：

```bash
python3 scripts/run.py status --json
python3 scripts/run.py open-step --json
python3 scripts/run.py tap-workbench --json
python3 scripts/run.py scroll-workbench-top --json
python3 scripts/run.py tap-attendance-entry --json
python3 scripts/run.py tap-app-center --json
python3 scripts/run.py tap-back-icon --json
```

7. 必要时再使用 `tap` 或 `back` 只执行一步
8. 重新运行原命令确认状态

常见 `fallback_reason`：

- `local_ocr_returned_no_text_boxes`：本地 OCR 没识别到文本
- `navigation_target_not_found_locally`：本地识别没找到工作台或考勤入口
- `attendance_action_not_found_locally`：已到考勤页，但本地识别没确认上班/下班按钮
- `open_step_requires_model_judgement`：当前页面需要模型做一步判断
- `navigation_retry_exhausted`：自动导航重试次数用尽

## 发布说明

- 对外公开发布时，默认保持 `dry_run: true`
- `show-config` 只显示是否已缓存，不显示密码明文
- `set-lock-password` / `clear-lock-password` 用于维护系统安全存储
- 升级旧版本后，如果本地还残留明文密码，脚本会在首次读取时尝试迁移到系统安全存储，并清理文件中的旧值

如果截图显示“已打下班卡”，必须先问用户是否继续，不要直接执行第二次下班打卡。

## 状态机

详细规则见 [references/state-machine.md](references/state-machine.md)。
