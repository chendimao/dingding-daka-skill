from __future__ import annotations

import inspect
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
  sys.path.insert(0, str(SCRIPT_DIR))

import bootstrap as bootstrap_module  # type: ignore  # noqa: E402
from common import create_paddle_ocr_instance, load_local_ocr_boxes  # type: ignore  # noqa: E402


class LocalOcrCompatTests(unittest.TestCase):
  def test_dependencies_allow_rapidocr_fallback_when_paddle_missing(self) -> None:
    imported: list[str] = []

    def fake_import_module(name: str) -> object:
      imported.append(name)
      if name == "paddle":
        raise ImportError("missing paddle")
      if name == "paddleocr":
        return SimpleNamespace(PaddleOCR=object)
      if name == "rapidocr_onnxruntime":
        return SimpleNamespace(RapidOCR=object)
      return SimpleNamespace()

    with (
      patch.object(bootstrap_module.importlib, "import_module", side_effect=fake_import_module),
      patch.object(bootstrap_module, "create_rapid_ocr_instance", return_value=object()),
    ):
      available = bootstrap_module.dependencies_available(Path("/tmp/mock-runtime"))

    self.assertTrue(available)
    self.assertEqual(
      imported,
      ["cv2", "paddle", "cv2", "onnxruntime", "rapidocr_onnxruntime"],
    )

  def test_create_paddle_ocr_instance_uses_v3_arguments(self) -> None:
    captured: dict[str, object] = {}

    class FakePaddleOCR:
      def __init__(self, lang: str | None = None, use_textline_orientation: bool | None = None, **kwargs: object) -> None:
        captured["lang"] = lang
        captured["use_textline_orientation"] = use_textline_orientation
        captured["kwargs"] = kwargs

    create_paddle_ocr_instance(FakePaddleOCR)

    self.assertEqual(captured["lang"], "ch")
    self.assertEqual(captured["use_textline_orientation"], True)
    self.assertEqual(captured["kwargs"], {})

  def test_create_paddle_ocr_instance_uses_legacy_arguments(self) -> None:
    captured: dict[str, object] = {}

    class FakeLegacyPaddleOCR:
      def __init__(self, lang: str | None = None, use_angle_cls: bool | None = None, show_log: bool | None = None) -> None:
        captured["lang"] = lang
        captured["use_angle_cls"] = use_angle_cls
        captured["show_log"] = show_log

    create_paddle_ocr_instance(FakeLegacyPaddleOCR)

    self.assertEqual(captured["lang"], "ch")
    self.assertEqual(captured["use_angle_cls"], True)
    self.assertEqual(captured["show_log"], False)

  def test_load_local_ocr_boxes_falls_back_to_rapidocr(self) -> None:
    class FakeRapidOCR:
      def __call__(self, image_path: str) -> tuple[list[list[object]], None]:
        return (
          [
            [[[10, 20], [30, 20], [30, 40], [10, 40]], "下班打卡", 0.99],
          ],
          None,
        )

    with (
      patch("common._PADDLE_OCR_INSTANCE", None),
      patch("common._PADDLE_OCR_UNAVAILABLE", True),
      patch("common._RAPID_OCR_INSTANCE", FakeRapidOCR()),
      patch("common._RAPID_OCR_UNAVAILABLE", False),
    ):
      boxes = load_local_ocr_boxes(
        Path("/Users/chendimao/.codex/skills/dingtalk-attendance/.runtime"),
        Path("/tmp/mock-image.png"),
      )

    self.assertEqual(len(boxes), 1)
    self.assertEqual(boxes[0]["text"], "下班打卡")
    self.assertEqual(boxes[0]["bounds"], [10, 20, 30, 40])


if __name__ == "__main__":
  unittest.main()
