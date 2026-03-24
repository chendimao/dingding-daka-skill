from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
  sys.path.insert(0, str(SCRIPT_DIR))

from common import parse_intent, parse_request  # type: ignore  # noqa: E402


class IntentParserTests(unittest.TestCase):
  def test_open_attendance_page(self) -> None:
    self.assertEqual(parse_intent("打开考勤打卡页面"), "open")

  def test_open_request_is_not_auto_execute(self) -> None:
    result = parse_request("打开考勤打卡页面")
    self.assertEqual(result["intent"], "open")
    self.assertFalse(result["auto_execute"])

  def test_clock_in(self) -> None:
    self.assertEqual(parse_intent("帮我打上班卡"), "clock-in")

  def test_clock_out(self) -> None:
    self.assertEqual(parse_intent("现在打下班卡"), "clock-out")

  def test_direct_clock_in_request_auto_executes(self) -> None:
    result = parse_request("上班打卡")
    self.assertEqual(result["intent"], "clock-in")
    self.assertTrue(result["auto_execute"])

  def test_direct_clock_out_request_auto_executes(self) -> None:
    result = parse_request("打下班卡")
    self.assertEqual(result["intent"], "clock-out")
    self.assertTrue(result["auto_execute"])

  def test_retry_local_install(self) -> None:
    self.assertEqual(parse_intent("重试本地安装"), "retry-local-install")


if __name__ == "__main__":
  unittest.main()
