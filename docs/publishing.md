# 多 CLI 发布说明

本文档说明如何把 `dingding-daka-skill` 作为“核心共用 + 适配层分发”的仓库发布给不同 AI CLI。

## 发布原则

- 核心自动化逻辑只维护一份，位于 `core/dingtalk-attendance`
- 协议只维护一份，位于 `docs/protocol.md`
- 不同 CLI 只提供轻量适配文档，不复制核心脚本
- 适配层负责：
  - 触发条件
  - 命令入口
  - 是否需要确认
  - 如何消费 `needs_model_input` 和 `model_handoff`

## 仓库分层

### 核心层

- 目录：`core/dingtalk-attendance`
- 内容：`scripts/`、`references/`、`tests/`、核心参考 `SKILL.md`
- 职责：ADB、页面识别、OCR、模型兜底交接、锁屏密码缓存、测试

### 协议层

- 目录：`docs/`
- 内容：`protocol.md`、`publishing.md`
- 职责：沉淀稳定字段与分发方式，避免适配层重复定义

### 适配层

- 目录：`adapters/`
- 内容：
  - `codex/SKILL.md`
  - `opencode/SKILL.md`
  - `claude/CLAUDE.md`
  - `gemini/GEMINI.md`
  - `openclaw/SKILL.md`
- 职责：把核心能力映射到具体 CLI 的技能机制

## 安装 / 复制策略

### Codex

- 复制 `core/dingtalk-attendance` 到本地技能目录，目录名保持 `dingtalk-attendance`
- 用 `adapters/codex/SKILL.md` 作为该技能目录中的入口文档

### OpenCode

- 复制 `core/dingtalk-attendance` 到 OpenCode 的本地技能目录
- 用 `adapters/opencode/SKILL.md` 作为入口文档

### Claude Code

- 复制 `core/dingtalk-attendance` 到 Claude Code 的个人技能目录
- 将 `adapters/claude/CLAUDE.md` 合并到目标环境的全局或仓库级 `CLAUDE.md`

### Gemini CLI

- 复制 `core/dingtalk-attendance` 到 Gemini 的技能目录
- 将 `adapters/gemini/GEMINI.md` 作为 Gemini 侧的调用入口

### OpenClaw

- 保留核心目录不变
- 用 `adapters/openclaw/SKILL.md` 告诉 OpenClaw 如何调用核心命令并消费统一 JSON 协议

## 发布检查清单

- 根 README 已明确说明这是多 CLI 仓库
- `docs/protocol.md` 中的状态码与当前脚本实现一致
- 所有适配层都引用 `docs/protocol.md`
- 默认仍然是 `dry_run`
- 文档明确锁屏只支持无锁屏和数字 PIN
- 文档明确本地 OCR 失败后直接走模型兜底
- 仓库中不包含 `.runtime`、设备序列号快照或明文密码
- 核心测试全部通过

## 版本发布建议

- 核心脚本行为有变更时，先更新 `core/` 和 `docs/protocol.md`
- 适配文案有变更时，只更新对应 `adapters/` 文档
- 发布标签建议覆盖整个仓库，而不是单独为某个 CLI 打包不同版本
- 如果将来出现 CLI 专属命令差异，再增加轻量适配脚本；在这之前，优先保持“文档适配、核心共用”
