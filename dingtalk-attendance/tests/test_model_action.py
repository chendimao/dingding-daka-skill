from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
  sys.path.insert(0, str(SCRIPT_DIR))

import run  # type: ignore  # noqa: E402


class ModelActionTests(unittest.TestCase):
  def test_tap_attendance_entry_returns_post_status(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      with (
        patch.object(run, "tap_attendance_entry", return_value={"ok": True, "status": "tapped", "message": "已点击考勤入口"}),
        patch.object(
          run,
          "collect_status_payload",
          return_value={
            "ok": True,
            "status": "status",
            "serial": "serial-1",
            "mode": "model_fallback",
            "activity": "activity-1",
            "page_type": "attendance",
            "texts": ["打卡"],
            "screenshot_path": "/tmp/after.png",
          },
        ),
      ):
        payload = run.apply_model_action("serial-1", runtime_dir, "model_fallback", "tap-attendance-entry")

    self.assertTrue(payload["ok"])
    self.assertEqual(payload["status"], "model_action_applied")
    self.assertEqual(payload["action"], "tap-attendance-entry")
    self.assertEqual(payload["post_status"]["page_type"], "attendance")

  def test_tap_app_center_returns_post_status(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      with (
        patch.object(run, "tap_app_center", return_value={"ok": True, "status": "tapped", "message": "已点击应用中心"}),
        patch.object(
          run,
          "collect_status_payload",
          return_value={
            "ok": True,
            "status": "status",
            "serial": "serial-1",
            "mode": "model_fallback",
            "activity": "activity-1",
            "page_type": "workbench",
            "texts": ["应用中心"],
            "screenshot_path": "/tmp/after.png",
          },
        ),
      ):
        payload = run.apply_model_action("serial-1", runtime_dir, "model_fallback", "tap-app-center")

    self.assertTrue(payload["ok"])
    self.assertEqual(payload["status"], "model_action_applied")
    self.assertEqual(payload["action"], "tap-app-center")
    self.assertEqual(payload["post_status"]["page_type"], "workbench")

  def test_tap_requires_coordinates(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      payload = run.apply_model_action("serial-1", runtime_dir, "model_fallback", "tap")
    self.assertFalse(payload["ok"])
    self.assertEqual(payload["status"], "error")

  def test_unknown_action_is_rejected(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      payload = run.apply_model_action("serial-1", runtime_dir, "model_fallback", "do-something-else")
    self.assertFalse(payload["ok"])
    self.assertEqual(payload["status"], "error")


if __name__ == "__main__":
  unittest.main()
