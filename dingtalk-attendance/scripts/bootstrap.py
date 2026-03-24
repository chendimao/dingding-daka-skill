from __future__ import annotations

import importlib
import contextlib
import io
import os
import subprocess
import sys
import warnings
from pathlib import Path
from typing import Callable

from common import add_vendor_to_sys_path, create_paddle_ocr_instance, create_rapid_ocr_instance, load_config, save_config


DependencyChecker = Callable[[], bool]
Installer = Callable[[], bool]


def detect_local_ocr_backend(runtime_dir: Path | None = None) -> dict[str, str | bool | None]:
  os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
  warnings.filterwarnings("ignore")
  add_vendor_to_sys_path(runtime_dir)

  try:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
      importlib.import_module("cv2")
      importlib.import_module("paddle")
      paddleocr_module = importlib.import_module("paddleocr")
      create_paddle_ocr_instance(getattr(paddleocr_module, "PaddleOCR"))
    return {"available": True, "backend": "paddleocr", "reason": None}
  except Exception as exc:
    paddle_reason = str(exc)

  try:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
      importlib.import_module("cv2")
      importlib.import_module("onnxruntime")
      rapidocr_module = importlib.import_module("rapidocr_onnxruntime")
      create_rapid_ocr_instance(getattr(rapidocr_module, "RapidOCR"))
    return {"available": True, "backend": "rapidocr", "reason": None}
  except Exception as exc:
    return {"available": False, "backend": None, "reason": f"paddleocr={paddle_reason}; rapidocr={exc}"}


def build_install_command(runtime_dir: Path, platform: str | None = None) -> list[str]:
  platform = platform or sys.platform
  vendor_dir = runtime_dir / "vendor"
  vendor_dir.mkdir(parents=True, exist_ok=True)
  command = [
    sys.executable,
    "-m",
    "pip",
    "install",
    "--disable-pip-version-check",
    "--target",
    str(vendor_dir),
    "opencv-python",
  ]
  if platform == "darwin":
    command.append("rapidocr_onnxruntime")
    return command
  command.append("paddleocr")
  if platform.startswith("linux") or platform == "win32":
    command.append("paddlepaddle")
  return command


def dependencies_available(runtime_dir: Path | None = None) -> bool:
  return bool(detect_local_ocr_backend(runtime_dir)["available"])


def install_local_dependencies(runtime_dir: Path) -> bool:
  if not (sys.platform.startswith("linux") or sys.platform == "win32" or sys.platform == "darwin"):
    return False
  command = build_install_command(runtime_dir)
  try:
    subprocess.run(command, check=True, capture_output=True, text=True, timeout=900)
  except Exception:
    return False
  return dependencies_available(runtime_dir)


def resolve_runtime_mode(
  runtime_dir: Path,
  config: dict,
  *,
  dependency_checker: DependencyChecker | None = None,
  installer: Installer | None = None,
  retry: bool = False,
) -> dict:
  dependency_checker = dependency_checker or (lambda: dependencies_available(runtime_dir))
  installer = installer or (lambda: install_local_dependencies(runtime_dir))

  if dependency_checker():
    config["mode"] = "local"
    config["local_install_failed"] = False
    config["local_failure_reason"] = None
    return save_config(runtime_dir, config)

  install_succeeded = installer()
  if install_succeeded:
    config["mode"] = "local"
    config["local_install_failed"] = False
    config["local_failure_reason"] = None
    return save_config(runtime_dir, config)

  config["mode"] = "model_fallback"
  config["local_install_failed"] = True
  config["local_failure_reason"] = "local dependency install failed"
  return save_config(runtime_dir, config)


def bootstrap_mode(runtime_dir: Path, retry: bool = False) -> dict:
  config = load_config(runtime_dir)
  return resolve_runtime_mode(runtime_dir, config, retry=retry)
