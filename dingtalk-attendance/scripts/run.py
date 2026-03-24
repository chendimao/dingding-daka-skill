from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

from bootstrap import bootstrap_mode
from common import (
  APP_CENTER_TEXTS,
  ATTENDANCE_TEXTS,
  PACKAGE_NAME,
  POPUP_TEXTS,
  WORKBENCH_TEXTS,
  build_model_fallback_payload,
  cache_unlock_password,
  clear_cached_unlock_password,
  clear_plaintext_lock_password,
  capture_screenshot,
  choose_device,
  click_first_matching_text,
  click_popup_or_back_if_needed,
  collect_ui_texts,
  current_activity,
  current_page_type,
  decide_attendance_action,
  dump_ui_xml,
  ensure_device_unlocked,
  find_ocr_target,
  find_text_bounds,
  get_device_config,
  get_relative_point,
  get_runtime_dir,
  get_screen_size,
  get_secure_storage_status,
  has_stored_unlock_password,
  launch_dingtalk,
  load_config,
  load_local_ocr_boxes,
  ocr_texts,
  parse_intent,
  parse_request,
  press_back,
  save_config,
  should_wait_for_ui,
  swipe_point,
  suggest_open_action,
  switch_to_model_fallback,
  tap_point,
  wake_unlock_device,
)

ATTENDANCE_ENTRY_X_RATIO = 145 / 1080
ATTENDANCE_ENTRY_Y_RATIO = 930 / 1920


def choose_preferred_python_executable(candidates: list[Path]) -> Path | None:
  versioned: list[tuple[tuple[int, ...], Path]] = []
  for candidate in candidates:
    match = re.search(r"/python/(\d+(?:\.\d+)+)/bin/python3$", str(candidate))
    if not match:
      continue
    version = tuple(int(part) for part in match.group(1).split("."))
    versioned.append((version, candidate))
  if not versioned:
    return None
  versioned.sort()
  return versioned[-1][1]


def should_reexec_python(current_executable: str, preferred_executable: Path | None) -> bool:
  if preferred_executable is None:
    return False
  try:
    return Path(current_executable).resolve() != preferred_executable.resolve()
  except Exception:
    return str(current_executable) != str(preferred_executable)


def ensure_preferred_python() -> None:
  current = sys.executable
  if os.environ.get("DINGTALK_ATTENDANCE_SKIP_REEXEC") == "1":
    return
  mise_root = Path.home() / ".local" / "share" / "mise" / "installs" / "python"
  candidates = list(mise_root.glob("*/bin/python3"))
  preferred = choose_preferred_python_executable(candidates)
  if not should_reexec_python(current, preferred):
    return
  env = os.environ.copy()
  env["DINGTALK_ATTENDANCE_SKIP_REEXEC"] = "1"
  os.execve(str(preferred), [str(preferred), __file__, *sys.argv[1:]], env)


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="钉钉考勤 skill 运行入口")
  parser.add_argument(
    "command",
    choices=[
      "open",
      "open-step",
      "clock-in",
      "clock-out",
      "retry-local-install",
      "tap",
      "back",
      "tap-workbench",
      "scroll-workbench-top",
      "tap-app-center",
      "tap-attendance-entry",
      "tap-back-icon",
      "model-action",
      "status",
      "intent",
      "show-config",
      "set-lock-password",
      "clear-lock-password",
    ],
  )
  parser.add_argument("--serial")
  parser.add_argument("--json", action="store_true")
  parser.add_argument("--x", type=int)
  parser.add_argument("--y", type=int)
  parser.add_argument("--text")
  parser.add_argument("--action")
  parser.add_argument("--execute", action="store_true")
  parser.add_argument("--password")
  return parser.parse_args()


def emit(payload: dict[str, Any], as_json: bool) -> int:
  if as_json:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
  else:
    print(payload.get("message") or payload.get("status"))
    if payload.get("status") == "needs_model_input" and payload.get("screenshot_path"):
      print(payload["screenshot_path"])
  return 0 if payload.get("ok", True) else 1


def tap_workbench(serial: str) -> dict[str, Any]:
  width, height = get_screen_size(serial)
  x, y = get_relative_point(width, height, 0.42, 0.94)
  tap_point(serial, x, y)
  return {"ok": True, "status": "tapped", "message": f"已点击工作台 ({x}, {y})"}


def scroll_workbench_top(serial: str) -> dict[str, Any]:
  width, height = get_screen_size(serial)
  start_x, start_y = get_relative_point(width, height, 0.5, 0.38)
  end_x, end_y = get_relative_point(width, height, 0.5, 0.82)
  swipe_point(serial, start_x, start_y, end_x, end_y, 350)
  return {
    "ok": True,
    "status": "scrolled",
    "message": f"已将工作台滑动到顶部 ({start_x}, {start_y}) -> ({end_x}, {end_y})",
  }


def tap_app_center(
  serial: str,
  xml_path: Path | None = None,
  boxes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
  matched = None
  if xml_path is not None:
    matched = click_text_target(serial, xml_path, boxes or [], APP_CENTER_TEXTS)
  if matched:
    return {
      "ok": True,
      "status": "tapped",
      "message": f"已点击应用中心入口文本 {matched}",
      "tap_mode": "text",
    }
  width, height = get_screen_size(serial)
  x, y = get_relative_point(width, height, 0.92, 0.08)
  tap_point(serial, x, y)
  return {
    "ok": True,
    "status": "tapped",
    "message": f"已点击应用中心 ({x}, {y})",
    "tap_mode": "coordinate",
  }


def tap_back_icon(serial: str) -> dict[str, Any]:
  width, height = get_screen_size(serial)
  x, y = get_relative_point(width, height, 0.07, 0.06)
  tap_point(serial, x, y)
  return {"ok": True, "status": "tapped", "message": f"已点击返回图标 ({x}, {y})"}


def tap_attendance_entry(
  serial: str,
  xml_path: Path | None = None,
  boxes: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
  matched = None
  if xml_path is not None:
    matched = click_text_target(serial, xml_path, boxes or [], ATTENDANCE_TEXTS)
  if matched:
    return {
      "ok": True,
      "status": "tapped",
      "message": f"已点击考勤入口文本 {matched}",
      "tap_mode": "text",
    }
  width, height = get_screen_size(serial)
  x, y = get_relative_point(width, height, ATTENDANCE_ENTRY_X_RATIO, ATTENDANCE_ENTRY_Y_RATIO)
  tap_point(serial, x, y)
  return {
    "ok": True,
    "status": "tapped",
    "message": f"已点击考勤入口坐标 ({x}, {y})",
    "tap_mode": "coordinate",
  }


def collect_status_payload(serial: str, runtime_dir: Path, mode: str, dry_run: bool) -> dict[str, Any]:
  xml_path = dump_ui_xml(serial, runtime_dir)
  screenshot_path = capture_screenshot(serial, runtime_dir)
  texts, _ = merged_texts(runtime_dir, xml_path, screenshot_path, mode, use_ocr=False)
  return {
    "ok": True,
    "status": "status",
    "serial": serial,
    "mode": mode,
    "activity": current_activity(serial),
    "page_type": current_page_type(serial, texts),
    "texts": texts[:50],
    "screenshot_path": str(screenshot_path),
    "dry_run": dry_run,
  }


def resolve_config_serial(config: dict[str, Any], explicit_serial: str | None) -> str | None:
  if explicit_serial:
    return explicit_serial
  remembered_serial = str(config.get("last_device_serial") or "").strip()
  return remembered_serial or None


def mask_secret(value: str | None) -> str | None:
  if not value:
    return None
  return "*" * len(value)


def build_config_payload(config: dict[str, Any], runtime_dir: Path, serial: str | None = None) -> dict[str, Any]:
  current_serial = resolve_config_serial(config, serial)
  secure_storage = get_secure_storage_status()
  current_device = None
  if current_serial:
    device_config = get_device_config(config, current_serial)
    has_plaintext = bool(str(device_config.get("lock_password") or config.get("lock_password") or "").strip())
    has_password = has_stored_unlock_password(current_serial, runtime_dir)
    if has_password and has_plaintext:
      clear_plaintext_lock_password(current_serial, runtime_dir)
      config = load_config(runtime_dir)
    current_device = {
      "serial": current_serial,
      "has_lock_password": has_password,
      "lock_password_masked": "******" if has_password else None,
    }
  return {
    "ok": True,
    "status": "config",
    "mode": config.get("mode"),
    "dry_run": bool(config.get("dry_run", True)),
    "last_device_serial": config.get("last_device_serial"),
    "secure_storage": secure_storage,
    "current_device": current_device,
    "configured_devices": sorted(str(key) for key in (config.get("devices") or {}).keys()),
    "message": "已读取当前配置",
  }


def apply_model_action(
  serial: str,
  runtime_dir: Path,
  mode: str,
  action: str,
  *,
  x: int | None = None,
  y: int | None = None,
) -> dict[str, Any]:
  if action == "tap-workbench":
    result = tap_workbench(serial)
  elif action == "scroll-workbench-top":
    result = scroll_workbench_top(serial)
  elif action == "tap-app-center":
    xml_path = dump_ui_xml(serial, runtime_dir)
    screenshot_path = capture_screenshot(serial, runtime_dir)
    _, boxes = merged_texts(runtime_dir, xml_path, screenshot_path, mode)
    result = tap_app_center(serial, xml_path, boxes)
  elif action == "tap-attendance-entry":
    xml_path = dump_ui_xml(serial, runtime_dir)
    screenshot_path = capture_screenshot(serial, runtime_dir)
    _, boxes = merged_texts(runtime_dir, xml_path, screenshot_path, mode)
    result = tap_attendance_entry(serial, xml_path, boxes)
  elif action == "tap-back-icon":
    result = tap_back_icon(serial)
  elif action == "back":
    press_back(serial)
    result = {"ok": True, "status": "back", "message": "已执行返回"}
  elif action == "tap":
    if x is None or y is None:
      return {"ok": False, "status": "error", "message": "执行 tap 动作时 --x 和 --y 不能为空"}
    tap_point(serial, x, y)
    result = {"ok": True, "status": "tapped", "message": f"已点击 ({x}, {y})"}
  else:
    return {"ok": False, "status": "error", "message": f"不支持的模型动作: {action}"}

  post_status = collect_status_payload(serial, runtime_dir, mode, True)
  return {
    "ok": True,
    "status": "model_action_applied",
    "action": action,
    "message": result.get("message") or f"已执行模型动作 {action}",
    "result": result,
    "post_status": post_status,
  }


def merged_texts(
  runtime_dir: Path,
  xml_path: Path,
  screenshot_path: Path,
  mode: str,
  *,
  use_ocr: bool = True,
) -> tuple[list[str], list[dict[str, Any]]]:
  xml_texts = collect_ui_texts(xml_path)
  if mode != "local" or not use_ocr:
    return xml_texts, []
  boxes = load_local_ocr_boxes(runtime_dir, screenshot_path)
  texts = xml_texts + ocr_texts(boxes)
  return texts, boxes


def click_text_target(
  serial: str,
  xml_path: Path,
  boxes: list[dict[str, Any]],
  candidates: tuple[str, ...],
) -> str | None:
  matched = find_text_bounds(xml_path, candidates)
  if matched and matched[1] is not None:
    tap_point(serial, matched[1][0], matched[1][1])
    return matched[0]
  ocr_target = find_ocr_target(boxes, candidates)
  if ocr_target and ocr_target[1] is not None:
    tap_point(serial, ocr_target[1][0], ocr_target[1][1])
    return ocr_target[0]
  return None


def navigate_to_attendance(
  serial: str,
  runtime_dir: Path,
  mode: str,
  intent: str,
) -> dict[str, Any]:
  unlock_payload = ensure_device_unlocked(serial, runtime_dir)
  if unlock_payload["status"] in {"needs_unlock_password", "unlock_password_invalid", "unsupported_lock_type"}:
    return unlock_payload
  launch_dingtalk(serial)
  warmup_retries = 0
  relaunch_retries = 0

  for _ in range(8):
    xml_path = dump_ui_xml(serial, runtime_dir)
    screenshot_path = capture_screenshot(serial, runtime_dir)
    texts, boxes = merged_texts(runtime_dir, xml_path, screenshot_path, mode, use_ocr=False)
    page_type = current_page_type(serial, texts)
    activity = current_activity(serial)

    if should_wait_for_ui(activity, texts) and warmup_retries < 3:
      warmup_retries += 1
      time.sleep(2)
      continue

    if page_type == "lockscreen":
      unlock_payload = ensure_device_unlocked(serial, runtime_dir)
      if unlock_payload["status"] in {"needs_unlock_password", "unlock_password_invalid", "unsupported_lock_type"}:
        return unlock_payload
      continue

    if page_type == "external" and relaunch_retries < 2:
      relaunch_retries += 1
      launch_dingtalk(serial)
      time.sleep(2)
      continue

    if page_type == "attendance-notice":
      matched_back = click_text_target(serial, xml_path, boxes, ("返回",))
      if matched_back:
        time.sleep(2)
      else:
        width, height = get_screen_size(serial)
        back_x, back_y = get_relative_point(width, height, 0.07, 0.06)
        tap_point(serial, back_x, back_y)
        time.sleep(2)
      continue

    if page_type == "attendance-subpage":
      press_back(serial)
      time.sleep(2)
      continue

    popup_action = click_popup_or_back_if_needed(
      serial,
      xml_path,
      runtime_dir,
      screenshot_path,
    )
    if popup_action:
      continue

    if page_type == "attendance":
      return {
        "ok": True,
        "status": "attendance_ready",
        "message": "已进入考勤打卡页面",
        "activity": activity,
        "texts": texts,
        "screenshot_path": str(screenshot_path),
      }

    if page_type in {"home", "dingtalk-other"}:
      page_action = suggest_open_action(page_type, texts)["action"]
      if page_action == "tap-back":
        matched_back = click_text_target(serial, xml_path, boxes, ("返回",))
        if matched_back:
          time.sleep(2)
          continue
        press_back(serial)
        time.sleep(2)
        continue
      matched = click_text_target(serial, xml_path, boxes, WORKBENCH_TEXTS)
      if matched:
        time.sleep(2)
        continue
      width, height = get_screen_size(serial)
      fallback_x, fallback_y = get_relative_point(width, height, 0.42, 0.94)
      tap_point(serial, fallback_x, fallback_y)
      time.sleep(2)
      continue

    if page_type == "workbench":
      if mode == "local":
        texts, boxes = merged_texts(runtime_dir, xml_path, screenshot_path, mode, use_ocr=True)
      workbench_action = suggest_open_action(page_type, texts)["action"]
      if workbench_action == "tap-attendance-entry":
        matched_attendance = click_text_target(serial, xml_path, boxes, ATTENDANCE_TEXTS)
        if matched_attendance:
          time.sleep(2)
          continue
      if workbench_action == "scroll-workbench-top":
        scroll_workbench_top(serial)
        time.sleep(2)
        continue
      tap_app_center(serial, xml_path, boxes)
      time.sleep(2)
      continue

    matched_attendance = click_text_target(serial, xml_path, boxes, ATTENDANCE_TEXTS)
    if matched_attendance:
      time.sleep(2)
      continue

    if mode == "local":
      texts, boxes = merged_texts(runtime_dir, xml_path, screenshot_path, mode, use_ocr=True)
      if not boxes:
        switch_to_model_fallback(runtime_dir, "local OCR returned no text boxes")
        payload = build_model_fallback_payload(
          intent=intent,
          serial=serial,
          activity=activity,
          screenshot_path=screenshot_path,
          message="本地 OCR 未识别出可用文本，已切换到模型兜底模式，请使用当前模型查看截图并决定下一步操作",
          texts=texts,
          fallback_reason="local_ocr_returned_no_text_boxes",
        )
        payload["mode"] = "model_fallback"
        return payload
      page_type = current_page_type(serial, texts)
      if page_type in {"home", "dingtalk-other"}:
        page_action = suggest_open_action(page_type, texts)["action"]
        if page_action == "tap-back":
          matched_back = click_text_target(serial, xml_path, boxes, ("返回",))
          if matched_back:
            time.sleep(2)
            continue
          press_back(serial)
          time.sleep(2)
          continue
        matched = click_text_target(serial, xml_path, boxes, WORKBENCH_TEXTS)
        if matched:
          time.sleep(2)
          continue
        width, height = get_screen_size(serial)
        fallback_x, fallback_y = get_relative_point(width, height, 0.42, 0.94)
        tap_point(serial, fallback_x, fallback_y)
        time.sleep(2)
        continue
      if page_type == "workbench":
        workbench_action = suggest_open_action(page_type, texts)["action"]
        if workbench_action == "tap-attendance-entry":
          matched_attendance = click_text_target(serial, xml_path, boxes, ATTENDANCE_TEXTS)
          if matched_attendance:
            time.sleep(2)
            continue
        if workbench_action == "scroll-workbench-top":
          scroll_workbench_top(serial)
          time.sleep(2)
          continue
        tap_app_center(serial, xml_path, boxes)
        time.sleep(2)
        continue
      if page_type == "attendance-subpage":
        press_back(serial)
        time.sleep(2)
        continue
      matched_attendance = click_text_target(serial, xml_path, boxes, ATTENDANCE_TEXTS)
      if matched_attendance:
        time.sleep(2)
        continue

    if page_type in {"webview", "dingtalk-other"}:
      press_back(serial)
      continue

    return build_model_fallback_payload(
      intent=intent,
      serial=serial,
      activity=activity,
      screenshot_path=screenshot_path,
      message="本地识别无法定位工作台或考勤入口，请使用当前模型查看截图并决定下一步操作",
      texts=texts,
      fallback_reason="navigation_target_not_found_locally",
    )

  screenshot_path = capture_screenshot(serial, runtime_dir)
  return build_model_fallback_payload(
    intent=intent,
    serial=serial,
    activity=current_activity(serial),
    screenshot_path=screenshot_path,
    message="导航重试次数过多，请使用当前模型查看截图并决定是否点击返回、关闭弹窗或进入考勤",
    fallback_reason="navigation_retry_exhausted",
  )


def handle_attendance_action(
  serial: str,
  runtime_dir: Path,
  mode: str,
  intent: str,
  dry_run: bool = True,
) -> dict[str, Any]:
  navigation = navigate_to_attendance(serial, runtime_dir, mode, intent)
  if navigation.get("status") != "attendance_ready":
    return navigation

  if intent == "open":
    return navigation

  xml_path = dump_ui_xml(serial, runtime_dir)
  screenshot_path = capture_screenshot(serial, runtime_dir)
  texts, boxes = merged_texts(runtime_dir, xml_path, screenshot_path, mode)
  decision = decide_attendance_action(intent, texts)

  if decision["status"] == "already_done":
    return {
      "ok": True,
      "status": "already_done",
      "message": decision["message"],
      "screenshot_path": str(screenshot_path),
    }

  if decision["status"] == "needs_confirmation":
    return {
      "ok": True,
      "status": "needs_confirmation",
      "message": decision["message"],
      "screenshot_path": str(screenshot_path),
    }

  if decision["status"] == "ready_to_click":
    if dry_run:
      return {
        "ok": True,
        "status": "dry_run_ready",
        "message": f"当前为测试模式，已识别到 {decision['matched_text']}，未真实点击",
        "matched_text": decision["matched_text"],
        "dry_run": True,
        "screenshot_path": str(screenshot_path),
      }
    matched = click_text_target(serial, xml_path, boxes, (decision["matched_text"],))
    if matched:
      time.sleep(2)
      verify_xml = dump_ui_xml(serial, runtime_dir)
      verify_screen = capture_screenshot(serial, runtime_dir)
      verify_texts, _ = merged_texts(runtime_dir, verify_xml, verify_screen, mode)
      verify_decision = decide_attendance_action(intent, verify_texts)
      if verify_decision["status"] in {"already_done", "needs_confirmation"}:
        return {
          "ok": True,
          "status": "completed",
          "message": "已执行打卡操作",
          "post_check": verify_decision["status"],
          "dry_run": False,
          "screenshot_path": str(verify_screen),
        }
      return {
        "ok": True,
        "status": "clicked",
        "message": f"已点击 {matched}",
        "dry_run": False,
        "screenshot_path": str(verify_screen),
      }

  if mode == "local" and not boxes:
    switch_to_model_fallback(runtime_dir, "local OCR returned no text boxes on attendance page")
    payload = build_model_fallback_payload(
      intent=intent,
      serial=serial,
      activity=current_activity(serial),
      screenshot_path=screenshot_path,
      message="本地 OCR 未识别出可用文本，已切换到模型兜底模式，请使用当前模型查看截图",
      texts=texts,
      fallback_reason="attendance_page_local_ocr_returned_no_text_boxes",
    )
    payload["mode"] = "model_fallback"
    return payload

  return build_model_fallback_payload(
    intent=intent,
    serial=serial,
    activity=current_activity(serial),
    screenshot_path=screenshot_path,
    message="考勤页面已打开，但本地识别无法确认上班卡或下班卡按钮，请使用当前模型查看截图",
    texts=texts,
    fallback_reason="attendance_action_not_found_locally",
  )


def handle_open_step(serial: str, runtime_dir: Path, mode: str) -> dict[str, Any]:
  xml_path = dump_ui_xml(serial, runtime_dir)
  screenshot_path = capture_screenshot(serial, runtime_dir)
  texts, boxes = merged_texts(runtime_dir, xml_path, screenshot_path, mode)
  activity = current_activity(serial)
  page_type = current_page_type(serial, texts)
  for _ in range(3):
    if not should_wait_for_ui(activity, texts):
      break
    time.sleep(1)
    xml_path = dump_ui_xml(serial, runtime_dir)
    screenshot_path = capture_screenshot(serial, runtime_dir)
    texts, boxes = merged_texts(runtime_dir, xml_path, screenshot_path, mode)
    activity = current_activity(serial)
    page_type = current_page_type(serial, texts)

  suggestion = suggest_open_action(page_type, texts)
  action = suggestion["action"]

  if action == "tap-workbench" and "LaunchHomeActivity" in activity:
    for _ in range(3):
      time.sleep(1)
      retry_xml_path = dump_ui_xml(serial, runtime_dir)
      retry_screenshot_path = capture_screenshot(serial, runtime_dir)
      retry_texts, retry_boxes = merged_texts(runtime_dir, retry_xml_path, retry_screenshot_path, mode)
      retry_page_type = current_page_type(serial, retry_texts)
      retry_suggestion = suggest_open_action(retry_page_type, retry_texts)
      if retry_suggestion["action"] != "tap-workbench":
        xml_path = retry_xml_path
        screenshot_path = retry_screenshot_path
        texts = retry_texts
        boxes = retry_boxes
        page_type = retry_page_type
        suggestion = retry_suggestion
        action = suggestion["action"]
        break

  if action == "unlock-device":
    unlock_payload = ensure_device_unlocked(serial, runtime_dir)
    if unlock_payload["status"] in {"needs_unlock_password", "unlock_password_invalid", "unsupported_lock_type"}:
      return unlock_payload
    return {"ok": True, "status": "step_executed", "action": action, "message": suggestion["message"]}

  if action == "launch-dingtalk":
    launch_dingtalk(serial)
    return {"ok": True, "status": "step_executed", "action": action, "message": suggestion["message"]}

  if action == "tap-back":
    if page_type == "attendance-subpage":
      press_back(serial)
      payload = {"ok": True, "status": "step_executed", "action": action, "message": suggestion["message"]}
      return payload
    payload = tap_back_icon(serial)
    payload.update({"status": "step_executed", "action": action, "message": suggestion["message"]})
    return payload

  if action == "tap-workbench":
    payload = tap_workbench(serial)
    payload.update({"status": "step_executed", "action": action, "message": suggestion["message"]})
    return payload

  if action == "scroll-workbench-top":
    payload = scroll_workbench_top(serial)
    payload.update({"status": "step_executed", "action": action, "message": suggestion["message"]})
    return payload

  if action == "tap-app-center":
    payload = tap_app_center(serial, xml_path, boxes)
    payload.update({"status": "step_executed", "action": action, "message": suggestion["message"]})
    return payload

  if action == "tap-attendance-entry":
    payload = tap_attendance_entry(serial, xml_path, boxes)
    payload.update({"status": "step_executed", "action": action, "message": suggestion["message"]})
    return payload

  if action == "done":
    return {
      "ok": True,
      "status": "attendance_ready",
      "action": action,
      "message": suggestion["message"],
      "activity": activity,
      "texts": texts,
      "screenshot_path": str(screenshot_path),
      "mode": mode,
      "serial": serial,
    }

  payload = build_model_fallback_payload(
    intent="open",
    serial=serial,
    activity=activity,
    screenshot_path=screenshot_path,
    message=suggestion["message"],
    texts=texts,
    fallback_reason="open_step_requires_model_judgement",
  )
  payload["mode"] = mode
  return payload


def main() -> int:
  ensure_preferred_python()
  args = parse_args()
  runtime_dir = get_runtime_dir()
  config = load_config(runtime_dir)

  if args.command == "intent":
    if not args.text:
      return emit({"ok": False, "status": "error", "message": "--text 不能为空"}, args.json)
    try:
      parsed = parse_request(args.text)
    except ValueError as exc:
      return emit({"ok": False, "status": "error", "message": str(exc)}, args.json)
    return emit(
      {
        "ok": True,
        "status": "parsed",
        "intent": parsed["intent"],
        "auto_execute": parsed["auto_execute"],
        "message": str(parsed["intent"]),
      },
      args.json,
    )

  if args.command == "show-config":
    return emit(build_config_payload(config, runtime_dir, args.serial), args.json)

  if args.command == "set-lock-password":
    target_serial = resolve_config_serial(config, args.serial)
    if not target_serial:
      return emit({"ok": False, "status": "error", "message": "未找到目标设备，请先传入 --serial 或先连接设备运行一次"}, args.json)
    password = str(args.password or "").strip()
    if not password:
      return emit({"ok": False, "status": "error", "message": "--password 不能为空"}, args.json)
    if not password.isdigit():
      return emit({"ok": False, "status": "error", "message": "当前只支持数字 PIN 锁屏密码，请提供纯数字密码"}, args.json)
    if not cache_unlock_password(target_serial, runtime_dir, password):
      return emit({"ok": False, "status": "error", "message": "写入系统安全存储失败，请检查当前系统是否支持安全存储"}, args.json)
    updated_config = load_config(runtime_dir)
    return emit(
      {
        "ok": True,
        "status": "lock_password_updated",
        "serial": target_serial,
        "current_device": build_config_payload(updated_config, runtime_dir, target_serial)["current_device"],
        "message": f"已更新设备 {target_serial} 的锁屏密码缓存",
      },
      args.json,
    )

  if args.command == "clear-lock-password":
    target_serial = resolve_config_serial(config, args.serial)
    if not target_serial:
      return emit({"ok": False, "status": "error", "message": "未找到目标设备，请先传入 --serial 或先连接设备运行一次"}, args.json)
    clear_cached_unlock_password(target_serial, runtime_dir)
    updated_config = load_config(runtime_dir)
    return emit(
      {
        "ok": True,
        "status": "lock_password_cleared",
        "serial": target_serial,
        "current_device": build_config_payload(updated_config, runtime_dir, target_serial)["current_device"],
        "message": f"已清除设备 {target_serial} 的锁屏密码缓存",
      },
      args.json,
    )

  if args.command == "retry-local-install":
    updated_config = bootstrap_mode(runtime_dir, retry=True)
    return emit(
      {
        "ok": True,
        "status": "mode_updated",
        "message": f"当前模式: {updated_config['mode']}",
        "mode": updated_config["mode"],
      },
      args.json,
    )

  config = bootstrap_mode(runtime_dir, retry=False)
  serial = choose_device(args.serial)
  config["last_device_serial"] = serial
  save_config(runtime_dir, config)

  if args.command == "status":
    return emit(collect_status_payload(serial, runtime_dir, config["mode"], bool(config.get("dry_run", True))), args.json)

  if args.command == "tap":
    if args.x is None or args.y is None:
      return emit({"ok": False, "status": "error", "message": "--x 和 --y 不能为空"}, args.json)
    tap_point(serial, args.x, args.y)
    return emit({"ok": True, "status": "tapped", "message": f"已点击 ({args.x}, {args.y})"}, args.json)

  if args.command == "back":
    press_back(serial)
    return emit({"ok": True, "status": "back", "message": "已执行返回"}, args.json)

  if args.command == "tap-workbench":
    return emit(tap_workbench(serial), args.json)

  if args.command == "scroll-workbench-top":
    return emit(scroll_workbench_top(serial), args.json)

  if args.command == "tap-app-center":
    xml_path = dump_ui_xml(serial, runtime_dir)
    screenshot_path = capture_screenshot(serial, runtime_dir)
    _, boxes = merged_texts(runtime_dir, xml_path, screenshot_path, config["mode"])
    return emit(tap_app_center(serial, xml_path, boxes), args.json)

  if args.command == "tap-attendance-entry":
    xml_path = dump_ui_xml(serial, runtime_dir)
    screenshot_path = capture_screenshot(serial, runtime_dir)
    _, boxes = merged_texts(runtime_dir, xml_path, screenshot_path, config["mode"])
    return emit(tap_attendance_entry(serial, xml_path, boxes), args.json)

  if args.command == "tap-back-icon":
    return emit(tap_back_icon(serial), args.json)

  if args.command == "model-action":
    if not args.action:
      return emit({"ok": False, "status": "error", "message": "--action 不能为空"}, args.json)
    return emit(
      apply_model_action(
        serial,
        runtime_dir,
        config["mode"],
        args.action,
        x=args.x,
        y=args.y,
      ),
      args.json,
    )

  if args.command == "open-step":
    return emit(handle_open_step(serial, runtime_dir, config["mode"]), args.json)

  if args.command in {"open", "clock-in", "clock-out"}:
    dry_run = bool(config.get("dry_run", True))
    if args.execute:
      dry_run = False
    payload = handle_attendance_action(serial, runtime_dir, config["mode"], args.command, dry_run=dry_run)
    payload.setdefault("mode", config["mode"])
    payload.setdefault("serial", serial)
    payload.setdefault("dry_run", dry_run)
    return emit(payload, args.json)

  return emit({"ok": False, "status": "error", "message": f"未知命令: {args.command}"}, args.json)


if __name__ == "__main__":
  sys.exit(main())
