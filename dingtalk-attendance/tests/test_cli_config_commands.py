from __future__ import annotations

import argparse
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
  sys.path.insert(0, str(SCRIPT_DIR))

import run  # type: ignore  # noqa: E402
from common import load_config, save_config  # type: ignore  # noqa: E402


def build_args(command: str, **kwargs: object) -> argparse.Namespace:
  return argparse.Namespace(
    command=command,
    serial=kwargs.get("serial"),
    json=kwargs.get("json", True),
    x=kwargs.get("x"),
    y=kwargs.get("y"),
    text=kwargs.get("text"),
    action=kwargs.get("action"),
    execute=kwargs.get("execute", False),
    password=kwargs.get("password"),
  )


class CliConfigCommandTests(unittest.TestCase):
  def test_show_config_masks_cached_password(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      save_config(
        runtime_dir,
        {
          "mode": "local",
          "dry_run": True,
          "last_device_serial": "serial-1",
        },
      )
      with (
        patch.object(run, "get_runtime_dir", return_value=runtime_dir),
        patch.object(run, "parse_args", return_value=build_args("show-config")),
        patch.object(run, "ensure_preferred_python"),
        patch.object(run, "has_stored_unlock_password", return_value=True),
      ):
        payloads: list[dict[str, object]] = []

        def fake_emit(payload: dict[str, object], _: bool) -> int:
          payloads.append(payload)
          return 0

        with patch.object(run, "emit", side_effect=fake_emit):
          exit_code = run.main()

    self.assertEqual(exit_code, 0)
    self.assertEqual(payloads[0]["status"], "config")
    self.assertEqual(payloads[0]["current_device"]["lock_password_masked"], "******")
    self.assertTrue(payloads[0]["current_device"]["has_lock_password"])

  def test_show_config_clears_legacy_plaintext_after_secure_storage_hit(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      save_config(
        runtime_dir,
        {
          "mode": "local",
          "dry_run": True,
          "last_device_serial": "serial-1",
          "devices": {
            "serial-1": {
              "lock_password": "000000",
            },
          },
        },
      )
      config_path = runtime_dir / "config.json"
      config_path.write_text(
        '{"mode":"local","dry_run":true,"last_device_serial":"serial-1","devices":{"serial-1":{"lock_password":"000000"}}}',
        encoding="utf-8",
      )
      with (
        patch.object(run, "get_runtime_dir", return_value=runtime_dir),
        patch.object(run, "parse_args", return_value=build_args("show-config")),
        patch.object(run, "ensure_preferred_python"),
        patch.object(run, "has_stored_unlock_password", return_value=True),
      ):
        payloads: list[dict[str, object]] = []

        def fake_emit(payload: dict[str, object], _: bool) -> int:
          payloads.append(payload)
          return 0

        with patch.object(run, "emit", side_effect=fake_emit):
          exit_code = run.main()

      config = load_config(runtime_dir)

    self.assertEqual(exit_code, 0)
    self.assertEqual(payloads[0]["status"], "config")
    self.assertIsNone(config["devices"]["serial-1"]["lock_password"])

  def test_set_lock_password_updates_current_device_cache(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      save_config(runtime_dir, {"last_device_serial": "serial-1"})
      with (
        patch.object(run, "get_runtime_dir", return_value=runtime_dir),
        patch.object(run, "parse_args", return_value=build_args("set-lock-password", password="123456")),
        patch.object(run, "ensure_preferred_python"),
        patch.object(run, "cache_unlock_password", return_value=True) as cache_unlock_password_mock,
        patch.object(run, "has_stored_unlock_password", return_value=True),
      ):
        payloads: list[dict[str, object]] = []

        def fake_emit(payload: dict[str, object], _: bool) -> int:
          payloads.append(payload)
          return 0

        with patch.object(run, "emit", side_effect=fake_emit):
          exit_code = run.main()

      config = load_config(runtime_dir)

    self.assertEqual(exit_code, 0)
    self.assertEqual(payloads[0]["status"], "lock_password_updated")
    cache_unlock_password_mock.assert_called_once_with("serial-1", runtime_dir, "123456")
    self.assertIsNone(config["lock_password"])
    self.assertNotIn("serial-1", config["devices"])

  def test_clear_lock_password_clears_current_device_cache(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      save_config(
        runtime_dir,
        {
          "last_device_serial": "serial-1",
          "devices": {
            "serial-1": {
              "lock_password": "123456",
            },
          },
        },
      )
      with (
        patch.object(run, "get_runtime_dir", return_value=runtime_dir),
        patch.object(run, "parse_args", return_value=build_args("clear-lock-password")),
        patch.object(run, "ensure_preferred_python"),
        patch.object(run, "clear_cached_unlock_password") as clear_cached_unlock_password_mock,
        patch.object(run, "has_stored_unlock_password", return_value=False),
      ):
        payloads: list[dict[str, object]] = []

        def fake_emit(payload: dict[str, object], _: bool) -> int:
          payloads.append(payload)
          return 0

        with patch.object(run, "emit", side_effect=fake_emit):
          exit_code = run.main()

      config = load_config(runtime_dir)

    self.assertEqual(exit_code, 0)
    self.assertEqual(payloads[0]["status"], "lock_password_cleared")
    clear_cached_unlock_password_mock.assert_called_once_with("serial-1", runtime_dir)
    self.assertIsNone(config["devices"]["serial-1"]["lock_password"])

  def test_set_lock_password_requires_numeric_pin(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      save_config(runtime_dir, {"last_device_serial": "serial-1"})
      with (
        patch.object(run, "get_runtime_dir", return_value=runtime_dir),
        patch.object(run, "parse_args", return_value=build_args("set-lock-password", password="abc123")),
        patch.object(run, "ensure_preferred_python"),
      ):
        payloads: list[dict[str, object]] = []

        def fake_emit(payload: dict[str, object], _: bool) -> int:
          payloads.append(payload)
          return 1

        with patch.object(run, "emit", side_effect=fake_emit):
          exit_code = run.main()

    self.assertEqual(exit_code, 1)
    self.assertEqual(payloads[0]["status"], "error")
    self.assertIn("数字 PIN", str(payloads[0]["message"]))

  def test_set_lock_password_fails_when_secure_storage_write_fails(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      save_config(runtime_dir, {"last_device_serial": "serial-1"})
      with (
        patch.object(run, "get_runtime_dir", return_value=runtime_dir),
        patch.object(run, "parse_args", return_value=build_args("set-lock-password", password="123456")),
        patch.object(run, "ensure_preferred_python"),
        patch.object(run, "cache_unlock_password", return_value=False),
      ):
        payloads: list[dict[str, object]] = []

        def fake_emit(payload: dict[str, object], _: bool) -> int:
          payloads.append(payload)
          return 1

        with patch.object(run, "emit", side_effect=fake_emit):
          exit_code = run.main()

    self.assertEqual(exit_code, 1)
    self.assertEqual(payloads[0]["status"], "error")
    self.assertIn("安全存储", str(payloads[0]["message"]))


if __name__ == "__main__":
  unittest.main()
