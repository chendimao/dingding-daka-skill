from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
  sys.path.insert(0, str(SCRIPT_DIR))

from common import decide_attendance_action  # type: ignore  # noqa: E402


class StateMachineTests(unittest.TestCase):
  def test_clock_in_clicks_when_button_visible(self) -> None:
    result = decide_attendance_action(
      "clock-in",
      ["定位中", "上班打卡", "更新打卡"],
    )
    self.assertEqual(result["status"], "ready_to_click")
    self.assertIn("上班打卡", result["matched_text"])

  def test_clock_in_reports_already_done(self) -> None:
    result = decide_attendance_action(
      "clock-in",
      ["今日上班已打卡", "考勤打卡"],
    )
    self.assertEqual(result["status"], "already_done")

  def test_clock_in_reports_already_done_from_success_card(self) -> None:
    result = decide_attendance_action(
      "clock-in",
      ["09:00上班打卡提醒", "打卡结果", "08:53极速打卡·成功"],
    )
    self.assertEqual(result["status"], "already_done")

  def test_clock_out_clicks_when_button_visible(self) -> None:
    result = decide_attendance_action(
      "clock-out",
      ["下班打卡", "考勤打卡"],
    )
    self.assertEqual(result["status"], "ready_to_click")
    self.assertIn("下班打卡", result["matched_text"])

  def test_clock_out_requires_confirmation_when_already_done(self) -> None:
    result = decide_attendance_action(
      "clock-out",
      ["今日下班已打卡", "已完成打卡"],
    )
    self.assertEqual(result["status"], "needs_confirmation")
    self.assertIn("已经打过下班卡", result["message"])


if __name__ == "__main__":
  unittest.main()
