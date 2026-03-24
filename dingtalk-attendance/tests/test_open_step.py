from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
  sys.path.insert(0, str(SCRIPT_DIR))

from common import suggest_open_action  # type: ignore  # noqa: E402


class OpenStepTests(unittest.TestCase):
  def test_external_page_relaunches_dingtalk(self) -> None:
    result = suggest_open_action("external", [])
    self.assertEqual(result["action"], "launch-dingtalk")

  def test_notice_page_uses_back(self) -> None:
    result = suggest_open_action("attendance-notice", ["返回", "打卡结果"])
    self.assertEqual(result["action"], "tap-back")

  def test_home_page_goes_to_workbench(self) -> None:
    result = suggest_open_action("home", ["消息", "工作台"])
    self.assertEqual(result["action"], "tap-workbench")

  def test_about_page_goes_back_first(self) -> None:
    result = suggest_open_action("dingtalk-other", ["返回", "关于钉钉", "检查版本更新"])
    self.assertEqual(result["action"], "tap-back")

  def test_return_page_without_tabs_goes_back_first(self) -> None:
    result = suggest_open_action("dingtalk-other", ["返回", "服务协议", "隐私政策"])
    self.assertEqual(result["action"], "tap-back")

  def test_return_page_with_non_dingtalk_tabs_goes_back_first(self) -> None:
    result = suggest_open_action("webview", ["返回", "探索", "应用", "我的"])
    self.assertEqual(result["action"], "tap-back")

  def test_non_dingtalk_tabs_go_back_even_without_return_text(self) -> None:
    result = suggest_open_action("webview", ["探索", "应用", "模板", "我的"])
    self.assertEqual(result["action"], "tap-back")

  def test_return_page_with_dingtalk_tabs_does_not_go_back_first(self) -> None:
    result = suggest_open_action("dingtalk-other", ["返回", "消息", "工作台", "通讯录", "我的"])
    self.assertEqual(result["action"], "tap-workbench")

  def test_workbench_with_entry_opens_attendance(self) -> None:
    result = suggest_open_action("workbench", ["考勤打卡", "工作台"])
    self.assertEqual(result["action"], "tap-attendance-entry")

  def test_workbench_without_entry_scrolls_top_first(self) -> None:
    result = suggest_open_action("workbench", ["工作台", "待办", "更多"])
    self.assertEqual(result["action"], "scroll-workbench-top")

  def test_workbench_at_top_without_entry_opens_app_center_first(self) -> None:
    result = suggest_open_action("workbench", ["工作台", "应用中心", "更多"])
    self.assertEqual(result["action"], "tap-app-center")

  def test_attendance_subpage_goes_back_first(self) -> None:
    result = suggest_open_action("attendance-subpage", ["统计", "考勤助理"])
    self.assertEqual(result["action"], "tap-back")


if __name__ == "__main__":
  unittest.main()
