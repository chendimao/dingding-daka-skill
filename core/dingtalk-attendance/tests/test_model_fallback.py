from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
  sys.path.insert(0, str(SCRIPT_DIR))

from common import build_model_fallback_payload  # type: ignore  # noqa: E402


class ModelFallbackTests(unittest.TestCase):
  def test_payload_contains_model_handoff(self) -> None:
    payload = build_model_fallback_payload(
      intent="open",
      serial="serial-1",
      activity="mCurrentFocus=Window{123 u0 com.alibaba.android.rimet/com.foo.UnknownActivity}",
      screenshot_path=Path("/tmp/mock-screen.png"),
      message="需要模型查看截图后决定下一步",
      texts=["未知页面", "测试文案"],
      fallback_reason="local OCR returned no text boxes",
    )

    self.assertEqual(payload["status"], "needs_model_input")
    self.assertIn("model_handoff", payload)
    self.assertEqual(payload["model_handoff"]["image_path"], "/tmp/mock-screen.png")
    self.assertIn("只做一步", payload["model_handoff"]["prompt"])
    self.assertIn("tap-workbench", payload["model_handoff"]["allowed_actions"])
    self.assertIn("tap-app-center", payload["model_handoff"]["allowed_actions"])
    self.assertIn("tap-back-icon", payload["model_handoff"]["allowed_actions"])
    self.assertEqual(payload["fallback_reason"], "local OCR returned no text boxes")


if __name__ == "__main__":
  unittest.main()
