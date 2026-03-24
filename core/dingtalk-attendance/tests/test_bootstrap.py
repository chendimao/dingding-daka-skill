from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
  sys.path.insert(0, str(SCRIPT_DIR))

import bootstrap as bootstrap_module  # type: ignore  # noqa: E402
from bootstrap import build_install_command, detect_local_ocr_backend, install_local_dependencies, resolve_runtime_mode  # type: ignore  # noqa: E402
from common import load_config, save_config, switch_to_model_fallback  # type: ignore  # noqa: E402


class BootstrapTests(unittest.TestCase):
  def test_remembers_model_fallback_after_install_failure(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      config = load_config(runtime_dir)

      def checker() -> bool:
        return False

      def installer() -> bool:
        return False

      mode = resolve_runtime_mode(
        runtime_dir,
        config,
        dependency_checker=checker,
        installer=installer,
        retry=False,
      )

      self.assertEqual(mode["mode"], "model_fallback")
      self.assertTrue(mode["local_install_failed"])

      persisted = load_config(runtime_dir)
      self.assertEqual(persisted["mode"], "model_fallback")
      self.assertTrue(persisted["local_install_failed"])

  def test_retry_can_restore_local_mode(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      save_config(
        runtime_dir,
        {
          "mode": "model_fallback",
          "last_device_serial": None,
          "local_install_failed": True,
          "local_failure_reason": "install failed",
        },
      )

      def checker() -> bool:
        return False

      def installer() -> bool:
        return True

      mode = resolve_runtime_mode(
        runtime_dir,
        load_config(runtime_dir),
        dependency_checker=checker,
        installer=installer,
        retry=True,
      )

      self.assertEqual(mode["mode"], "local")
      self.assertFalse(mode["local_install_failed"])

  def test_non_retry_rechecks_recovered_local_dependencies(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      save_config(
        runtime_dir,
        {
          "mode": "model_fallback",
          "last_device_serial": None,
          "local_install_failed": True,
          "local_failure_reason": "install failed",
        },
      )

      def checker() -> bool:
        return True

      def installer() -> bool:
        return False

      mode = resolve_runtime_mode(
        runtime_dir,
        load_config(runtime_dir),
        dependency_checker=checker,
        installer=installer,
        retry=False,
      )

      self.assertEqual(mode["mode"], "local")
      self.assertFalse(mode["local_install_failed"])

  def test_switch_to_model_fallback_persists_reason(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      config = switch_to_model_fallback(runtime_dir, "ocr failed")
      self.assertEqual(config["mode"], "model_fallback")
      self.assertEqual(config["local_failure_reason"], "ocr failed")
      persisted = load_config(runtime_dir)
      self.assertEqual(persisted["mode"], "model_fallback")
      self.assertEqual(persisted["local_failure_reason"], "ocr failed")

  def test_build_install_command_includes_paddle_on_linux(self) -> None:
    command = build_install_command(Path("/tmp/mock-runtime"), platform="linux")
    self.assertIn("paddlepaddle", command)

  def test_build_install_command_uses_rapidocr_on_darwin(self) -> None:
    command = build_install_command(Path("/tmp/mock-runtime"), platform="darwin")
    self.assertIn("rapidocr_onnxruntime", command)
    self.assertNotIn("paddlepaddle", command)

  def test_install_local_dependencies_attempts_install_on_darwin(self) -> None:
    with tempfile.TemporaryDirectory() as tmp:
      runtime_dir = Path(tmp)
      with (
        patch("bootstrap.sys.platform", "darwin"),
        patch("bootstrap.subprocess.run"),
        patch("bootstrap.dependencies_available", return_value=True),
      ):
        self.assertTrue(install_local_dependencies(runtime_dir))

  def test_detect_local_ocr_backend_prefers_paddle(self) -> None:
    with (
      patch.object(bootstrap_module.importlib, "import_module") as import_module,
      patch.object(bootstrap_module, "create_paddle_ocr_instance", return_value=object()),
    ):
      import_module.side_effect = [
        object(),
        object(),
        type("PaddleOCRModule", (), {"PaddleOCR": object})(),
      ]
      result = detect_local_ocr_backend(Path("/tmp/mock-runtime"))

    self.assertEqual(result["backend"], "paddleocr")
    self.assertTrue(result["available"])

  def test_detect_local_ocr_backend_falls_back_to_rapidocr(self) -> None:
    def fake_import_module(name: str) -> object:
      if name == "cv2":
        return object()
      if name == "paddle":
        raise ImportError("missing paddle")
      if name == "onnxruntime":
        return object()
      if name == "rapidocr_onnxruntime":
        return type("RapidOCRModule", (), {"RapidOCR": object})()
      raise ImportError(name)

    with (
      patch.object(bootstrap_module.importlib, "import_module", side_effect=fake_import_module),
      patch.object(bootstrap_module, "create_rapid_ocr_instance", return_value=object()),
    ):
      result = detect_local_ocr_backend(Path("/tmp/mock-runtime"))

    self.assertEqual(result["backend"], "rapidocr")
    self.assertTrue(result["available"])


if __name__ == "__main__":
  unittest.main()
