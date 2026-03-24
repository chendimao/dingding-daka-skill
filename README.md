# Codex DingTalk Attendance Skill

一个面向 Codex / Codex CLI 的钉钉考勤自动化 skill。

## 功能

- 打开钉钉并进入考勤打卡页
- 处理常见广告弹窗、更新弹窗、误入页面返回
- 支持本地 OCR，失败后回退到模型识别
- 锁屏仅支持：
  - 无锁屏
  - 数字 PIN
- 默认 `dry-run`
  - `clock-in` / `clock-out` 默认只识别、不真实点击
  - 只有显式加 `--execute` 才会真实执行
- 锁屏密码使用系统安全存储
  - macOS: Keychain
  - Windows: Credential Manager
  - Linux: Secret Service

## 前置要求

- 已安装 `adb`
- 手机已开启 USB 调试
- 手机已授权当前电脑的 `adb`
- 已安装 Python 3
- 本地 OCR 可选：
  - macOS: `RapidOCR + OpenCV`
  - Windows / Linux: `PaddleOCR + OpenCV`

## 安装

将仓库中的 `dingtalk-attendance` 目录复制到本地 Codex skills 目录，例如：

```bash
mkdir -p ~/.codex/skills
cp -R dingtalk-attendance ~/.codex/skills/
```

## 常用命令

```bash
python3 scripts/run.py open --json
python3 scripts/run.py clock-in --json
python3 scripts/run.py clock-out --json
python3 scripts/run.py clock-in --execute --json
python3 scripts/run.py clock-out --execute --json
python3 scripts/run.py show-config --json
python3 scripts/run.py set-lock-password --password 000000 --json
python3 scripts/run.py clear-lock-password --json
python3 scripts/run.py retry-local-install --json
```

## 支持边界

- 不支持图案锁
- 不支持字母数字密码
- 不支持厂商定制复杂锁屏
- 若本地 OCR 失败，会返回 `needs_model_input`

## 目录结构

```text
dingtalk-attendance/
  SKILL.md
  scripts/
  assets/
  references/
  tests/
```

## 测试

```bash
python3 -m unittest discover -s dingtalk-attendance/tests -p 'test_*.py'
```

## 风险说明

这是一个自动化操作 skill。请在理解脚本行为和公司制度的前提下自行使用。真实打卡前请确认当前模式是否为 `--execute`。

## 许可证

MIT
