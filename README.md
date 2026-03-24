# dingding-daka-skill

`dingding-daka-skill` 是一个面向多 CLI 的钉钉考勤自动化仓库，采用“核心共用 + 适配层分发”的结构，首批支持 `codex`、`opencode`、`claude`、`gemini`、`openclaw`。

## 仓库定位

- `core/dingtalk-attendance`：与具体大模型 CLI 无关的核心脚本、测试和参考说明
- `docs/protocol.md`：稳定 JSON 协议，供各 CLI 适配层统一消费
- `docs/publishing.md`：多 CLI 发布与安装策略
- `adapters/codex/SKILL.md`：Codex 适配层入口
- `adapters/opencode/SKILL.md`：OpenCode 适配层入口
- `adapters/claude/CLAUDE.md`：Claude Code 适配层入口
- `adapters/gemini/GEMINI.md`：Gemini CLI 适配层入口
- `adapters/openclaw/SKILL.md`：OpenClaw 适配层入口

## 功能

- 打开钉钉并导航到考勤打卡页
- 处理常见广告弹窗、更新弹窗、误入页面返回
- 根据提示词判断上班卡 / 下班卡动作
- 默认 `dry-run`，只有显式 `--execute` 才真实点击
- 锁屏仅支持无锁屏或数字 PIN
- 优先本地 OCR，本地失败后返回统一模型兜底协议
- 锁屏密码使用系统安全存储
  - macOS：Keychain
  - Windows：Credential Manager
  - Linux：Secret Service

## 前置要求

- 已安装 `adb`
- 手机已开启 USB 调试
- 手机已授权当前电脑的 `adb`
- 已安装 Python 3
- 本地 OCR 可选：
  - macOS：`RapidOCR + OpenCV`
  - Windows / Linux：`PaddleOCR + OpenCV`

## 目录结构

```text
dingding-daka-skill/
  README.md
  LICENSE
  发布说明.md
  docs/
    protocol.md
    publishing.md
  core/
    dingtalk-attendance/
      SKILL.md
      scripts/
      references/
      tests/
  adapters/
    codex/
      SKILL.md
    opencode/
      SKILL.md
    claude/
      CLAUDE.md
    gemini/
      GEMINI.md
    openclaw/
      SKILL.md
```

## 安装思路

### 1. 安装核心目录

把 `core/dingtalk-attendance` 复制到目标 CLI 的技能目录，并保持目录名为 `dingtalk-attendance`。

### 2. 套用适配层入口文档

不同 CLI 使用不同入口文档：

- Codex：使用 `adapters/codex/SKILL.md`
- OpenCode：使用 `adapters/opencode/SKILL.md`
- Claude Code：使用 `adapters/claude/CLAUDE.md`
- Gemini CLI：使用 `adapters/gemini/GEMINI.md`
- OpenClaw：使用 `adapters/openclaw/SKILL.md`

适配层只定义触发方式、调用约束和如何消费协议；核心脚本始终共用同一套 `python3 scripts/run.py` 命令。

## 常用命令

以下命令均在 `core/dingtalk-attendance` 目录内执行：

```bash
python3 scripts/run.py open --json
python3 scripts/run.py open-step --json
python3 scripts/run.py clock-in --json
python3 scripts/run.py clock-out --json
python3 scripts/run.py clock-in --execute --json
python3 scripts/run.py clock-out --execute --json
python3 scripts/run.py status --json
python3 scripts/run.py show-config --json
python3 scripts/run.py set-lock-password --password 000000 --json
python3 scripts/run.py clear-lock-password --json
python3 scripts/run.py retry-local-install --json
```

## 统一协议

所有 CLI 适配层都应把脚本输出当作稳定 JSON 协议处理，重点关注：

- `status`
- `message`
- `fallback_reason`
- `dry_run`
- `serial`
- `mode`
- `model_handoff`

详见 `docs/protocol.md`。

## 支持边界

- 不支持图案锁
- 不支持字母数字密码
- 不支持厂商定制复杂锁屏
- 本地 OCR 安装失败后默认记住模型兜底模式，除非用户明确要求重试安装
- 当返回 `needs_model_input` 时，只允许执行一步动作，再重新读取页面状态

## 测试

```bash
python3 -m unittest discover -s core/dingtalk-attendance/tests -p 'test_*.py'
```

## 发布

- 多 CLI 发布说明见 `docs/publishing.md`
- 当前仓库对外发布说明见 `发布说明.md`

## 风险说明

这是一个自动化操作仓库。真实打卡前请确认当前命令是否显式带了 `--execute`，并确认该行为符合你的使用场景和公司制度。

## 许可证

MIT
