from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
  sys.path.insert(0, str(SCRIPT_DIR))

from common import classify_page  # type: ignore  # noqa: E402


class PageClassificationTests(unittest.TestCase):
  def test_launch_home_with_message_markers_is_home(self) -> None:
    activity = (
      "mCurrentFocus=Window{123 u0 "
      "com.alibaba.android.rimet/com.alibaba.android.rimet.biz.LaunchHomeActivity}"
    )
    self.assertEqual(classify_page(activity, ["置顶", "未读", "工作台"]), "home")

  def test_launch_home_without_message_markers_is_workbench(self) -> None:
    activity = (
      "mCurrentFocus=Window{123 u0 "
      "com.alibaba.android.rimet/com.alibaba.android.rimet.biz.LaunchHomeActivity}"
    )
    self.assertEqual(classify_page(activity, ["工作台", "待办"]), "workbench")

  def test_launch_home_with_profile_card_is_workbench(self) -> None:
    activity = (
      "mCurrentFocus=Window{123 u0 "
      "com.alibaba.android.rimet/com.alibaba.android.rimet.biz.LaunchHomeActivity}"
    )
    self.assertEqual(classify_page(activity, ["我的信息", "工作台", "应用中心"]), "workbench")

  def test_launch_home_ignores_bottom_tab_message_label_on_workbench(self) -> None:
    activity = (
      "mCurrentFocus=Window{123 u0 "
      "com.alibaba.android.rimet/com.alibaba.android.rimet.biz.LaunchHomeActivity}"
    )
    texts = ["我的信息", "应用中心", "工作台", "消息", "通讯录", "我的"]
    self.assertEqual(classify_page(activity, texts), "workbench")

  def test_launch_home_profile_page_is_home(self) -> None:
    activity = (
      "mCurrentFocus=Window{123 u0 "
      "com.alibaba.android.rimet/com.alibaba.android.rimet.biz.LaunchHomeActivity}"
    )
    texts = ["设置与隐私", "应用市场", "客服与帮助", "工作台", "消息", "我的"]
    self.assertEqual(classify_page(activity, texts), "home")

  def test_enterprise_oa_is_notice_not_attendance(self) -> None:
    activity = (
      "mCurrentFocus=Window{123 u0 "
      "com.alibaba.android.rimet/com.alibaba.android.dingtalkim.activities.EnterpriseOAListActivity}"
    )
    texts = ["考勤打卡", "立即打卡", "打卡结果", "极速打卡·成功"]
    self.assertEqual(classify_page(activity, texts), "attendance-notice")

  def test_the_one_activity_is_attendance(self) -> None:
    activity = (
      "mCurrentFocus=Window{123 u0 "
      "com.alibaba.android.rimet/com.alibaba.lightapp.runtime.ariver.TheOneActivityMainTask}"
    )
    texts = ["考勤打卡", "上班打卡"]
    self.assertEqual(classify_page(activity, texts), "attendance")

  def test_the_one_main_task_with_tab_labels_is_attendance(self) -> None:
    activity = (
      "mCurrentFocus=Window{123 u0 "
      "com.alibaba.android.rimet/com.alibaba.lightapp.runtime.ariver.TheOneActivityMainTask}"
    )
    texts = ["返回", "打卡", "统计", "设置"]
    self.assertEqual(classify_page(activity, texts), "attendance")

  def test_the_one_activity_stats_page_is_attendance_subpage(self) -> None:
    activity = (
      "mCurrentFocus=Window{123 u0 "
      "com.alibaba.android.rimet/com.alibaba.lightapp.runtime.ariver.TheOneActivity5}"
    )
    texts = ["统计", "考勤助理", "回到今天"]
    self.assertEqual(classify_page(activity, texts), "attendance-subpage")


if __name__ == "__main__":
  unittest.main()
