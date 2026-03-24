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


class AttendanceActionTests(unittest.TestCase):
  def test_clock_in_defaults_to_dry_run_without_clicking(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      screenshot_path = runtime_dir / "attendance.png"
      screenshot_path.write_text("", encoding="utf-8")
      xml_path = runtime_dir / "attendance.xml"
      xml_path.write_text("", encoding="utf-8")

      with (
        patch.object(
          run,
          "navigate_to_attendance",
          return_value={"ok": True, "status": "attendance_ready", "message": "已进入考勤打卡页面"},
        ),
        patch.object(run, "dump_ui_xml", return_value=xml_path),
        patch.object(run, "capture_screenshot", return_value=screenshot_path),
        patch.object(run, "merged_texts", return_value=(["上班打卡"], [])),
        patch.object(run, "decide_attendance_action", return_value={"status": "ready_to_click", "matched_text": "上班打卡"}),
        patch.object(run, "click_text_target") as click_text_target_mock,
      ):
        payload = run.handle_attendance_action("serial-1", runtime_dir, "local", "clock-in")

    click_text_target_mock.assert_not_called()
    self.assertEqual(payload["status"], "dry_run_ready")
    self.assertTrue(payload["dry_run"])

  def test_clock_out_executes_when_explicitly_disabled_dry_run(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      screenshot_path = runtime_dir / "attendance.png"
      screenshot_path.write_text("", encoding="utf-8")
      xml_path = runtime_dir / "attendance.xml"
      xml_path.write_text("", encoding="utf-8")
      verify_xml = runtime_dir / "verify.xml"
      verify_xml.write_text("", encoding="utf-8")
      verify_screen = runtime_dir / "verify.png"
      verify_screen.write_text("", encoding="utf-8")

      with (
        patch.object(
          run,
          "navigate_to_attendance",
          return_value={"ok": True, "status": "attendance_ready", "message": "已进入考勤打卡页面"},
        ),
        patch.object(run, "dump_ui_xml", side_effect=[xml_path, verify_xml]),
        patch.object(run, "capture_screenshot", side_effect=[screenshot_path, verify_screen]),
        patch.object(run, "merged_texts", side_effect=[(["下班打卡"], []), (["今日下班已打卡"], [])]),
        patch.object(run, "decide_attendance_action", side_effect=[{"status": "ready_to_click", "matched_text": "下班打卡"}, {"status": "needs_confirmation", "message": "已经打过下班卡，是否需要再次打下班卡"}]),
        patch.object(run, "click_text_target", return_value="下班打卡") as click_text_target_mock,
        patch.object(run.time, "sleep"),
      ):
        payload = run.handle_attendance_action("serial-1", runtime_dir, "local", "clock-out", dry_run=False)

    click_text_target_mock.assert_called_once()
    self.assertEqual(payload["status"], "completed")


if __name__ == "__main__":
  unittest.main()
