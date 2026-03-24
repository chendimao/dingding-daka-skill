from __future__ import annotations

import unittest
from pathlib import Path


def find_repo_root() -> Path:
  current = Path(__file__).resolve()
  for parent in current.parents:
    if (parent / ".git").exists() or (parent / "README.md").exists():
      return parent
  raise RuntimeError("未找到仓库根目录")


class RepositoryDocsTests(unittest.TestCase):
  def test_readme_describes_multi_cli_layout(self) -> None:
    root = find_repo_root()
    content = (root / "README.md").read_text(encoding="utf-8")
    required_texts = [
      "多 CLI",
      "core/dingtalk-attendance",
      "docs/protocol.md",
      "adapters/codex/SKILL.md",
      "adapters/openclaw/SKILL.md",
      "adapters/claude/CLAUDE.md",
      "adapters/gemini/GEMINI.md",
      "adapters/opencode/SKILL.md",
    ]
    for text in required_texts:
      self.assertIn(text, content)

  def test_protocol_document_describes_stable_fields(self) -> None:
    root = find_repo_root()
    content = (root / "docs" / "protocol.md").read_text(encoding="utf-8")
    required_texts = [
      "status",
      "message",
      "fallback_reason",
      "dry_run",
      "serial",
      "mode",
      "model_handoff",
      "needs_model_input",
      "allowed_actions",
    ]
    for text in required_texts:
      self.assertIn(text, content)


if __name__ == "__main__":
  unittest.main()
