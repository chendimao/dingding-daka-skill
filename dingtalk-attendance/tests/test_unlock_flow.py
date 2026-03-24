from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
  sys.path.insert(0, str(SCRIPT_DIR))

from common import ensure_device_unlocked, get_cached_unlock_password, load_config, save_config  # type: ignore  # noqa: E402


class UnlockFlowTests(unittest.TestCase):
  def test_requires_password_when_keyguard_and_no_password_available(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      with (
        patch(
          "common.current_activity",
          side_effect=[
            "mCurrentFocus=Window{1 u0 Keyguard}",
            "mCurrentFocus=Window{1 u0 Keyguard}",
            "mCurrentFocus=Window{1 u0 Keyguard}",
            "mCurrentFocus=Window{1 u0 Keyguard}",
            "mCurrentFocus=Window{1 u0 Keyguard}",
            "mCurrentFocus=Window{1 u0 Keyguard}",
          ],
        ),
        patch("common.capture_screenshot", return_value=runtime_dir / "lock.png"),
        patch("common.load_local_ocr_boxes", return_value=[{"text": "0", "bounds": [10, 10, 20, 20]}]),
        patch("common.wake_unlock_device"),
        patch("common.time.sleep"),
        patch.dict(os.environ, {}, clear=True),
      ):
        payload = ensure_device_unlocked("serial-1", runtime_dir)

    self.assertEqual(payload["status"], "needs_unlock_password")
    self.assertIn("锁屏密码", payload["message"])

  def test_caches_password_after_successful_unlock(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      with (
        patch("common.current_activity", side_effect=["mCurrentFocus=Window{1 u0 Keyguard}", "mCurrentFocus=Window{1 u0 com.alibaba.android.rimet/.Main}"]),
        patch("common.wake_unlock_device"),
        patch("common.set_secure_lock_password") as set_secure_lock_password_mock,
        patch.dict(os.environ, {"DINGTALK_ATTENDANCE_LOCK_PASSWORD": "000000"}, clear=False),
      ):
        payload = ensure_device_unlocked("serial-1", runtime_dir)

      config = load_config(runtime_dir)

    self.assertEqual(payload["status"], "unlocked")
    set_secure_lock_password_mock.assert_called_once_with("serial-1", "000000")
    self.assertIsNone(config["devices"]["serial-1"]["lock_password"])
    self.assertEqual(payload["password_source"], "env")
    self.assertFalse(payload["used_cache"])

  def test_unlock_waits_for_keyguard_to_dismiss_before_marking_success(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      with (
        patch(
          "common.current_activity",
          side_effect=[
            "mCurrentFocus=Window{1 u0 Keyguard}",
            "mCurrentFocus=Window{1 u0 Keyguard}",
            "mCurrentFocus=Window{1 u0 com.alibaba.android.rimet/.Main}",
          ],
        ),
        patch("common.wake_unlock_device"),
        patch("common.set_secure_lock_password") as set_secure_lock_password_mock,
        patch("common.time.sleep"),
        patch.dict(os.environ, {"DINGTALK_ATTENDANCE_LOCK_PASSWORD": "000000"}, clear=False),
      ):
        payload = ensure_device_unlocked("serial-1", runtime_dir)

      config = load_config(runtime_dir)

    self.assertEqual(payload["status"], "unlocked")
    set_secure_lock_password_mock.assert_called_once_with("serial-1", "000000")
    self.assertIsNone(config["devices"]["serial-1"]["lock_password"])

  def test_clears_cached_password_after_invalid_unlock(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      save_config(
        runtime_dir,
        {
          "last_device_serial": "serial-1",
        },
      )
      with (
        patch(
          "common.current_activity",
          side_effect=[
            "mCurrentFocus=Window{1 u0 Keyguard}",
            "mCurrentFocus=Window{1 u0 Keyguard}",
            "mCurrentFocus=Window{1 u0 Keyguard}",
            "mCurrentFocus=Window{1 u0 Keyguard}",
            "mCurrentFocus=Window{1 u0 Keyguard}",
            "mCurrentFocus=Window{1 u0 Keyguard}",
          ],
        ),
        patch("common.capture_screenshot", return_value=runtime_dir / "lock.png"),
        patch("common.load_local_ocr_boxes", return_value=[{"text": "0", "bounds": [10, 10, 20, 20]}]),
        patch("common.wake_unlock_device"),
        patch("common.get_secure_lock_password", return_value="111111"),
        patch("common.delete_secure_lock_password") as delete_secure_lock_password_mock,
        patch("common.time.sleep"),
        patch.dict(os.environ, {}, clear=True),
      ):
        payload = ensure_device_unlocked("serial-1", runtime_dir)

      config = load_config(runtime_dir)

    self.assertEqual(payload["status"], "unlock_password_invalid")
    delete_secure_lock_password_mock.assert_called_once_with("serial-1")
    self.assertIsNone(config["devices"]["serial-1"]["lock_password"])

  def test_does_not_reuse_other_device_cached_password(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      save_config(
        runtime_dir,
        {
          "last_device_serial": "serial-1",
        },
      )
      with (
        patch(
          "common.current_activity",
          side_effect=[
            "mCurrentFocus=Window{1 u0 Keyguard}",
            "mCurrentFocus=Window{1 u0 Keyguard}",
            "mCurrentFocus=Window{1 u0 Keyguard}",
            "mCurrentFocus=Window{1 u0 Keyguard}",
            "mCurrentFocus=Window{1 u0 Keyguard}",
            "mCurrentFocus=Window{1 u0 Keyguard}",
          ],
        ),
        patch("common.capture_screenshot", return_value=runtime_dir / "lock.png"),
        patch("common.load_local_ocr_boxes", return_value=[{"text": "0", "bounds": [10, 10, 20, 20]}]),
        patch("common.wake_unlock_device"),
        patch("common.get_secure_lock_password", return_value=None),
        patch("common.time.sleep"),
        patch.dict(os.environ, {}, clear=True),
      ):
        payload = ensure_device_unlocked("serial-2", runtime_dir)

    self.assertEqual(payload["status"], "needs_unlock_password")

  def test_migrates_legacy_lock_password_to_last_device(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      (runtime_dir / "config.json").write_text(
        '{"last_device_serial": "serial-legacy", "lock_password": "222222", "devices": {}}',
        encoding="utf-8",
      )

      with (
        patch("common.get_secure_lock_password", return_value=None),
        patch("common.set_secure_lock_password") as set_secure_lock_password_mock,
      ):
        cached = get_cached_unlock_password("serial-legacy", runtime_dir)
      config = load_config(runtime_dir)

    self.assertEqual(cached, "222222")
    set_secure_lock_password_mock.assert_called_once_with("serial-legacy", "222222")
    self.assertIsNone(config["devices"]["serial-legacy"]["lock_password"])

  def test_rejects_non_numeric_unlock_password(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      with (
        patch("common.current_activity", return_value="mCurrentFocus=Window{1 u0 Keyguard}"),
        patch("common.capture_screenshot", return_value=runtime_dir / "lock.png"),
        patch("common.load_local_ocr_boxes", return_value=[]),
        patch("common.wake_unlock_device") as wake_unlock_device_mock,
        patch.dict(os.environ, {"DINGTALK_ATTENDANCE_LOCK_PASSWORD": "abc123"}, clear=False),
      ):
        payload = ensure_device_unlocked("serial-1", runtime_dir)

    wake_unlock_device_mock.assert_not_called()
    self.assertEqual(payload["status"], "unsupported_lock_type")

  def test_returns_unsupported_when_lockscreen_is_not_numeric_pin(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      with (
        patch("common.current_activity", return_value="mCurrentFocus=Window{1 u0 Keyguard}"),
        patch("common.capture_screenshot", return_value=runtime_dir / "lock.png"),
        patch("common.load_local_ocr_boxes", return_value=[{"text": "绘制图案", "bounds": [10, 10, 40, 20]}]),
        patch("common.wake_unlock_device") as wake_unlock_device_mock,
        patch.dict(os.environ, {}, clear=True),
      ):
        payload = ensure_device_unlocked("serial-1", runtime_dir)

    wake_unlock_device_mock.assert_not_called()
    self.assertEqual(payload["status"], "unsupported_lock_type")


if __name__ == "__main__":
  unittest.main()
