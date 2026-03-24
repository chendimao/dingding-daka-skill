from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
  sys.path.insert(0, str(SCRIPT_DIR))


def find_repo_root() -> Path:
  current = Path(__file__).resolve()
  for parent in current.parents:
    if (parent / ".git").exists() or (parent / "README.md").exists():
      return parent
  raise RuntimeError("未找到仓库根目录")


class RepositoryLayoutTests(unittest.TestCase):
  def test_multi_cli_layout_exists(self) -> None:
    root = find_repo_root()
    expected_paths = [
      root / "core" / "dingtalk-attendance" / "scripts" / "run.py",
      root / "docs" / "protocol.md",
      root / "docs" / "publishing.md",
      root / "adapters" / "codex" / "SKILL.md",
      root / "adapters" / "opencode" / "SKILL.md",
      root / "adapters" / "claude" / "CLAUDE.md",
      root / "adapters" / "gemini" / "GEMINI.md",
      root / "adapters" / "openclaw" / "SKILL.md",
    ]
    missing = [str(path.relative_to(root)) for path in expected_paths if not path.exists()]
    self.assertEqual(missing, [])


if __name__ == "__main__":
  unittest.main()
