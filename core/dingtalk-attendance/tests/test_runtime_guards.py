from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
  sys.path.insert(0, str(SCRIPT_DIR))

from common import should_wait_for_ui  # type: ignore  # noqa: E402


class RuntimeGuardTests(unittest.TestCase):
  def test_waits_for_launch_splash_with_no_texts(self) -> None:
    self.assertTrue(
      should_wait_for_ui(
        "mCurrentFocus=Window{123 u0 com.alibaba.android.rimet/com.alibaba.android.rimet.biz.LaunchHomeActivity}",
        [],
      )
    )

  def test_no_wait_when_useful_text_exists(self) -> None:
    self.assertFalse(
      should_wait_for_ui(
        "mCurrentFocus=Window{123 u0 com.alibaba.android.rimet/com.alibaba.android.rimet.biz.LaunchHomeActivity}",
        ["工作台", "消息"],
      )
    )


if __name__ == "__main__":
  unittest.main()
