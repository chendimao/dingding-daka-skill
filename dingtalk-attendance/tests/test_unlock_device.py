from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import call, patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
  sys.path.insert(0, str(SCRIPT_DIR))

from common import get_unlock_password, wake_unlock_device  # type: ignore  # noqa: E402


class UnlockDeviceTests(unittest.TestCase):
  def test_reads_unlock_password_from_environment(self) -> None:
    with patch.dict(os.environ, {"DINGTALK_ATTENDANCE_LOCK_PASSWORD": "000000"}, clear=False):
      self.assertEqual(get_unlock_password(), "000000")

  def test_returns_none_when_unlock_password_missing(self) -> None:
    with patch.dict(os.environ, {}, clear=True):
      self.assertIsNone(get_unlock_password())

  def test_wake_unlock_device_taps_numeric_password_from_ocr(self) -> None:
    with (
      patch("common.adb_command") as adb_command_mock,
      patch("common.capture_screenshot", return_value=Path("/tmp/lock.png")),
      patch(
        "common.load_local_ocr_boxes",
        return_value=[
          {"text": "0", "bounds": [100, 200, 140, 240]},
        ],
      ),
      patch("common.tap_point") as tap_point_mock,
      patch("common.time.sleep"),
    ):
      wake_unlock_device("serial-1", password="000000")

    adb_command_mock.assert_has_calls(
      [
        call("serial-1", "shell", "input", "keyevent", "KEYCODE_WAKEUP", check=False),
        call("serial-1", "shell", "svc", "power", "stayon", "usb", check=False),
        call("serial-1", "shell", "input", "swipe", "540", "1600", "540", "400", "300", check=False),
      ]
    )
    self.assertEqual(tap_point_mock.call_count, 6)
    tap_point_mock.assert_has_calls([call("serial-1", 120, 220)] * 6)

  def test_wake_unlock_device_falls_back_to_keyevents_for_numeric_password(self) -> None:
    with (
      patch("common.adb_command") as adb_command_mock,
      patch("common.capture_screenshot", return_value=Path("/tmp/lock.png")),
      patch("common.load_local_ocr_boxes", return_value=[]),
      patch("common.time.sleep"),
    ):
      wake_unlock_device("serial-1", password="000000")

    adb_command_mock.assert_has_calls(
      [
        call("serial-1", "shell", "input", "keyevent", "KEYCODE_WAKEUP", check=False),
        call("serial-1", "shell", "svc", "power", "stayon", "usb", check=False),
        call("serial-1", "shell", "input", "swipe", "540", "1600", "540", "400", "300", check=False),
        call("serial-1", "shell", "input", "keyevent", "KEYCODE_0", check=False),
        call("serial-1", "shell", "input", "keyevent", "KEYCODE_0", check=False),
        call("serial-1", "shell", "input", "keyevent", "KEYCODE_0", check=False),
        call("serial-1", "shell", "input", "keyevent", "KEYCODE_0", check=False),
        call("serial-1", "shell", "input", "keyevent", "KEYCODE_0", check=False),
        call("serial-1", "shell", "input", "keyevent", "KEYCODE_0", check=False),
        call("serial-1", "shell", "input", "keyevent", "KEYCODE_ENTER", check=False),
      ]
    )


if __name__ == "__main__":
  unittest.main()
