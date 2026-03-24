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


class OpenStepHandlerTests(unittest.TestCase):
  def test_waits_for_ui_before_deciding_action(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      xml_paths = [runtime_dir / "a.xml", runtime_dir / "b.xml", runtime_dir / "c.xml"]
      png_paths = [runtime_dir / "a.png", runtime_dir / "b.png", runtime_dir / "c.png"]
      for path in [*xml_paths, *png_paths]:
        path.write_text("", encoding="utf-8")

      with (
        patch.object(run, "dump_ui_xml", side_effect=xml_paths),
        patch.object(run, "capture_screenshot", side_effect=png_paths),
        patch.object(run, "merged_texts", side_effect=[([], []), ([], []), (["工作台", "应用中心", "更多"], [])]),
        patch.object(run, "current_activity", return_value="mCurrentFocus=Window{123 u0 com.alibaba.android.rimet/com.alibaba.android.rimet.biz.LaunchHomeActivity}"),
        patch.object(run, "current_page_type", side_effect=["home", "home", "workbench"]),
        patch.object(run, "should_wait_for_ui", side_effect=[True, True, False]),
        patch.object(
          run,
          "suggest_open_action",
          return_value={"action": "tap-app-center", "message": "工作台首屏未识别到考勤文字，先打开应用中心或更多入口"},
        ),
        patch.object(run, "tap_workbench") as tap_workbench_mock,
        patch.object(run, "tap_app_center", return_value={"ok": True, "status": "tapped", "message": "已点击应用中心"}) as tap_app_center_mock,
        patch.object(run.time, "sleep"),
      ):
        payload = run.handle_open_step("serial-1", runtime_dir, "local")

    tap_workbench_mock.assert_not_called()
    tap_app_center_mock.assert_called_once()
    self.assertEqual(payload["action"], "tap-app-center")
    self.assertEqual(payload["status"], "step_executed")

  def test_rechecks_before_repeated_tap_workbench(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      xml_paths = [runtime_dir / "a.xml", runtime_dir / "b.xml", runtime_dir / "c.xml"]
      png_paths = [runtime_dir / "a.png", runtime_dir / "b.png", runtime_dir / "c.png"]
      for path in [*xml_paths, *png_paths]:
        path.write_text("", encoding="utf-8")

      with (
        patch.object(run, "dump_ui_xml", side_effect=xml_paths),
        patch.object(run, "capture_screenshot", side_effect=png_paths),
        patch.object(run, "merged_texts", side_effect=[([], []), ([], []), (["工作台", "应用中心", "更多"], [])]),
        patch.object(run, "current_activity", return_value="mCurrentFocus=Window{123 u0 com.alibaba.android.rimet/com.alibaba.android.rimet.biz.LaunchHomeActivity}"),
        patch.object(run, "current_page_type", side_effect=["home", "home", "workbench"]),
        patch.object(run, "should_wait_for_ui", return_value=False),
        patch.object(
          run,
          "suggest_open_action",
          side_effect=[
            {"action": "tap-workbench", "message": "当前不在工作台，先切到工作台"},
            {"action": "tap-workbench", "message": "当前不在工作台，先切到工作台"},
            {"action": "tap-app-center", "message": "工作台首屏未识别到考勤文字，先打开应用中心或更多入口"},
          ],
        ),
        patch.object(run, "tap_workbench") as tap_workbench_mock,
        patch.object(run, "tap_app_center", return_value={"ok": True, "status": "tapped", "message": "已点击应用中心"}) as tap_app_center_mock,
        patch.object(run.time, "sleep"),
      ):
        payload = run.handle_open_step("serial-1", runtime_dir, "local")

    tap_workbench_mock.assert_not_called()
    tap_app_center_mock.assert_called_once()
    self.assertEqual(payload["action"], "tap-app-center")
    self.assertEqual(payload["status"], "step_executed")


if __name__ == "__main__":
  unittest.main()
