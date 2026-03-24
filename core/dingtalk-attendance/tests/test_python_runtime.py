from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
  sys.path.insert(0, str(SCRIPT_DIR))

from run import choose_preferred_python_executable, should_reexec_python  # type: ignore  # noqa: E402


class PythonRuntimeTests(unittest.TestCase):
  def test_choose_preferred_python_picks_highest_mise_version(self) -> None:
    candidates = [
      Path("/Users/chendimao/.local/share/mise/installs/python/3.11.9/bin/python3"),
      Path("/Users/chendimao/.local/share/mise/installs/python/3.12.9/bin/python3"),
      Path("/Users/chendimao/.local/share/mise/installs/python/3.10.14/bin/python3"),
    ]
    selected = choose_preferred_python_executable(candidates)
    self.assertEqual(str(selected), "/Users/chendimao/.local/share/mise/installs/python/3.12.9/bin/python3")

  def test_should_reexec_when_current_python_is_not_preferred(self) -> None:
    current = "/usr/bin/python3"
    preferred = Path("/Users/chendimao/.local/share/mise/installs/python/3.12.9/bin/python3")
    self.assertTrue(should_reexec_python(current, preferred))

  def test_no_reexec_when_current_python_matches_preferred(self) -> None:
    current = "/Users/chendimao/.local/share/mise/installs/python/3.12.9/bin/python3"
    preferred = Path(current)
    self.assertFalse(should_reexec_python(current, preferred))


if __name__ == "__main__":
  unittest.main()
