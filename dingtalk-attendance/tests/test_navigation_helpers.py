from __future__ import annotations

import contextlib
import io
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
  sys.path.insert(0, str(SCRIPT_DIR))

from common import get_relative_point, load_template_match  # type: ignore  # noqa: E402


class NavigationHelpersTests(unittest.TestCase):
  def test_relative_point_uses_screen_ratio(self) -> None:
    self.assertEqual(get_relative_point(1080, 1920, 0.42, 0.94), (453, 1804))

  def test_load_template_match_silences_cv2_import_output(self) -> None:
    original_import = __import__

    def fake_import(name: str, *args: object, **kwargs: object) -> object:
      if name == "cv2":
        print("OpenCV bindings requires numpy")
        raise ImportError("missing cv2")
      return original_import(name, *args, **kwargs)

    stdout = io.StringIO()
    stderr = io.StringIO()
    with (
      patch("builtins.__import__", side_effect=fake_import),
      contextlib.redirect_stdout(stdout),
      contextlib.redirect_stderr(stderr),
    ):
      result = load_template_match(Path("/tmp/source.png"), Path("/tmp/template.png"))

    self.assertIsNone(result)
    self.assertEqual(stdout.getvalue(), "")
    self.assertEqual(stderr.getvalue(), "")


if __name__ == "__main__":
  unittest.main()
