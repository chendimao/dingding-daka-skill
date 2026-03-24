from __future__ import annotations

import contextlib
import ctypes
import io
import inspect
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any


SKILL_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR_ENV = "DINGTALK_ATTENDANCE_RUNTIME_DIR"
LOCK_PASSWORD_ENV = "DINGTALK_ATTENDANCE_LOCK_PASSWORD"
SECURE_STORE_SERVICE = "codex.dingtalk-attendance"
PACKAGE_NAME = "com.alibaba.android.rimet"
HOME_ACTIVITY_HINTS = (
  "LaunchHomeActivity",
  "biz.LaunchHomeActivity",
)
WORKBENCH_TEXTS = ("工作台",)
APP_CENTER_TEXTS = ("应用中心", "更多")
ATTENDANCE_TEXTS = ("考勤打卡", "考勤", "打卡")
WORKBENCH_TOP_MARKERS = (
  "应用中心",
  "常用应用",
  "智能填表",
  "考勤打卡",
  "补卡申请",
  "请假",
  "加班",
  "考勤统计",
  "设置",
)
INTERNAL_BACK_PAGE_MARKERS = (
  "关于钉钉",
  "检查版本更新",
  "新功能黑板报",
  "历史版本介绍",
  "服务协议",
  "隐私政策",
)
DINGTALK_BOTTOM_TABS = ("消息", "工作台", "通讯录", "我的")
APP_MARKET_BOTTOM_TABS = ("探索", "应用", "硬件", "模板", "AI助理", "我的")
ATTENDANCE_BOTTOM_TABS = ("打卡", "统计", "设置")
MESSAGE_PAGE_MARKERS = (
  "置顶",
  "未读",
  "工作通知",
  "钉钉小秘书",
  "待回复",
)
WORKBENCH_PAGE_MARKERS = (
  "待办",
  "常用应用",
  "应用中心",
  "智能填表",
  "工作台",
)
PROFILE_PAGE_MARKERS = (
  "设置与隐私",
  "应用市场",
  "客服与帮助",
  "钱包",
  "收藏",
  "会议",
  "邮箱",
)
POPUP_TEXTS = (
  "暂不更新",
  "以后再说",
  "稍后",
  "关闭",
  "取消",
  "知道了",
  "我知道了",
  "跳过",
  "暂不",
)
ATTENDANCE_NOTICE_MARKERS = ("打卡结果", "立即打卡", "上班打卡提醒")
DIRECT_CLOCK_IN_TEXTS = ("上班打卡", "打上班卡")
DIRECT_CLOCK_OUT_TEXTS = ("下班打卡", "打下班卡")
MODEL_ALLOWED_ACTIONS = (
  "tap-workbench",
  "tap-app-center",
  "tap-attendance-entry",
  "tap-back-icon",
  "back",
  "tap",
)
DEFAULT_CONFIG = {
  "mode": "local",
  "last_device_serial": None,
  "local_install_failed": False,
  "local_failure_reason": None,
  "lock_password": None,
  "devices": {},
  "dry_run": True,
}
_PADDLE_OCR_INSTANCE: Any | None = None
_PADDLE_OCR_UNAVAILABLE = False
_RAPID_OCR_INSTANCE: Any | None = None
_RAPID_OCR_UNAVAILABLE = False


def build_default_config() -> dict[str, Any]:
  payload = dict(DEFAULT_CONFIG)
  payload["devices"] = {}
  return payload


def get_runtime_dir(explicit: Path | None = None) -> Path:
  if explicit is not None:
    explicit.mkdir(parents=True, exist_ok=True)
    return explicit
  override = os.environ.get(RUNTIME_DIR_ENV)
  if override:
    path = Path(override).expanduser()
  else:
    path = SKILL_ROOT / ".runtime"
  path.mkdir(parents=True, exist_ok=True)
  return path


def get_unlock_password() -> str | None:
  password = os.environ.get(LOCK_PASSWORD_ENV, "").strip()
  return password or None


def get_device_config(config: dict[str, Any], serial: str) -> dict[str, Any]:
  devices = config.get("devices")
  if not isinstance(devices, dict):
    devices = {}
    config["devices"] = devices
  device_config = devices.get(serial)
  if not isinstance(device_config, dict):
    device_config = {}
    devices[serial] = device_config
  device_config.setdefault("lock_password", None)
  return device_config


def migrate_legacy_config(config: dict[str, Any]) -> dict[str, Any]:
  config.setdefault("lock_password", None)
  devices = config.get("devices")
  if not isinstance(devices, dict):
    config["devices"] = {}
  return config


def build_secure_store_account(serial: str) -> str:
  return f"{PACKAGE_NAME}:{serial}:lock-password"


def get_secure_storage_backend() -> str | None:
  if sys.platform == "darwin":
    return "keychain"
  if sys.platform == "win32":
    return "wincred"
  if sys.platform.startswith("linux"):
    return "secret-service"
  return None


def get_secure_storage_status() -> dict[str, Any]:
  backend = get_secure_storage_backend()
  if backend == "keychain":
    return {
      "available": shutil.which("security") is not None,
      "backend": backend,
    }
  if backend == "secret-service":
    return {
      "available": shutil.which("secret-tool") is not None,
      "backend": backend,
    }
  if backend == "wincred":
    return {
      "available": True,
      "backend": backend,
    }
  return {
    "available": False,
    "backend": None,
  }


def ensure_secure_storage_available() -> str:
  status = get_secure_storage_status()
  if not status["available"] or not status["backend"]:
    raise RuntimeError("当前系统没有可用的安全存储能力，公开发布版不支持明文缓存锁屏密码")
  return str(status["backend"])


def _macos_set_secure_password(account: str, password: str) -> None:
  ensure_command("security")
  run_command(
    [
      "security",
      "add-generic-password",
      "-a",
      account,
      "-s",
      SECURE_STORE_SERVICE,
      "-w",
      password,
      "-U",
    ],
  )


def _macos_get_secure_password(account: str) -> str | None:
  ensure_command("security")
  result = run_command(
    [
      "security",
      "find-generic-password",
      "-a",
      account,
      "-s",
      SECURE_STORE_SERVICE,
      "-w",
    ],
    check=False,
  )
  if result.returncode != 0:
    return None
  return (result.stdout or "").strip() or None


def _macos_delete_secure_password(account: str) -> None:
  ensure_command("security")
  run_command(
    [
      "security",
      "delete-generic-password",
      "-a",
      account,
      "-s",
      SECURE_STORE_SERVICE,
    ],
    check=False,
  )


def _linux_set_secure_password(account: str, password: str) -> None:
  ensure_command("secret-tool")
  subprocess.run(
    [
      "secret-tool",
      "store",
      "--label",
      f"{SECURE_STORE_SERVICE}:{account}",
      "service",
      SECURE_STORE_SERVICE,
      "account",
      account,
    ],
    input=f"{password}\n",
    text=True,
    capture_output=True,
    check=True,
    timeout=30,
  )


def _linux_get_secure_password(account: str) -> str | None:
  ensure_command("secret-tool")
  result = run_command(
    [
      "secret-tool",
      "lookup",
      "service",
      SECURE_STORE_SERVICE,
      "account",
      account,
    ],
    check=False,
  )
  if result.returncode != 0:
    return None
  return (result.stdout or "").strip() or None


def _linux_delete_secure_password(account: str) -> None:
  ensure_command("secret-tool")
  run_command(
    [
      "secret-tool",
      "clear",
      "service",
      SECURE_STORE_SERVICE,
      "account",
      account,
    ],
    check=False,
  )


def _windows_set_secure_password(account: str, password: str) -> None:
  class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]

  class CREDENTIALW(ctypes.Structure):
    _fields_ = [
      ("Flags", ctypes.c_uint32),
      ("Type", ctypes.c_uint32),
      ("TargetName", ctypes.c_wchar_p),
      ("Comment", ctypes.c_wchar_p),
      ("LastWritten", FILETIME),
      ("CredentialBlobSize", ctypes.c_uint32),
      ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
      ("Persist", ctypes.c_uint32),
      ("AttributeCount", ctypes.c_uint32),
      ("Attributes", ctypes.c_void_p),
      ("TargetAlias", ctypes.c_wchar_p),
      ("UserName", ctypes.c_wchar_p),
    ]

  blob = password.encode("utf-16-le")
  buffer = ctypes.create_string_buffer(blob)
  pointer = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte))
  credential = CREDENTIALW()
  credential.Type = 1
  credential.TargetName = f"{SECURE_STORE_SERVICE}:{account}"
  credential.CredentialBlobSize = len(blob)
  credential.CredentialBlob = pointer
  credential.Persist = 2
  credential.UserName = account
  advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
  if not advapi32.CredWriteW(ctypes.byref(credential), 0):
    raise RuntimeError("写入 Windows Credential Manager 失败")


def _windows_get_secure_password(account: str) -> str | None:
  class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_uint32), ("dwHighDateTime", ctypes.c_uint32)]

  class CREDENTIALW(ctypes.Structure):
    _fields_ = [
      ("Flags", ctypes.c_uint32),
      ("Type", ctypes.c_uint32),
      ("TargetName", ctypes.c_wchar_p),
      ("Comment", ctypes.c_wchar_p),
      ("LastWritten", FILETIME),
      ("CredentialBlobSize", ctypes.c_uint32),
      ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
      ("Persist", ctypes.c_uint32),
      ("AttributeCount", ctypes.c_uint32),
      ("Attributes", ctypes.c_void_p),
      ("TargetAlias", ctypes.c_wchar_p),
      ("UserName", ctypes.c_wchar_p),
    ]

  advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
  credential_ptr = ctypes.POINTER(CREDENTIALW)()
  if not advapi32.CredReadW(f"{SECURE_STORE_SERVICE}:{account}", 1, 0, ctypes.byref(credential_ptr)):
    return None
  try:
    credential = credential_ptr.contents
    blob = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
    return blob.decode("utf-16-le") or None
  finally:
    advapi32.CredFree(credential_ptr)


def _windows_delete_secure_password(account: str) -> None:
  advapi32 = ctypes.WinDLL("Advapi32.dll", use_last_error=True)
  advapi32.CredDeleteW(f"{SECURE_STORE_SERVICE}:{account}", 1, 0)


def set_secure_lock_password(serial: str, password: str) -> None:
  backend = ensure_secure_storage_available()
  account = build_secure_store_account(serial)
  if backend == "keychain":
    _macos_set_secure_password(account, password)
    return
  if backend == "secret-service":
    _linux_set_secure_password(account, password)
    return
  if backend == "wincred":
    _windows_set_secure_password(account, password)
    return
  raise RuntimeError("当前系统没有可用的安全存储能力")


def get_secure_lock_password(serial: str) -> str | None:
  status = get_secure_storage_status()
  backend = status["backend"]
  if not status["available"] or not backend:
    return None
  account = build_secure_store_account(serial)
  if backend == "keychain":
    return _macos_get_secure_password(account)
  if backend == "secret-service":
    return _linux_get_secure_password(account)
  if backend == "wincred":
    return _windows_get_secure_password(account)
  return None


def delete_secure_lock_password(serial: str) -> None:
  backend = ensure_secure_storage_available()
  account = build_secure_store_account(serial)
  if backend == "keychain":
    _macos_delete_secure_password(account)
    return
  if backend == "secret-service":
    _linux_delete_secure_password(account)
    return
  if backend == "wincred":
    _windows_delete_secure_password(account)
    return


def clear_plaintext_lock_password(serial: str, runtime_dir: Path | None) -> None:
  config = load_config(runtime_dir)
  config["lock_password"] = None
  device_config = get_device_config(config, serial)
  device_config["lock_password"] = None
  save_config(runtime_dir, config)


def get_cached_unlock_password(serial: str, runtime_dir: Path | None = None) -> str | None:
  password = get_secure_lock_password(serial)
  if password:
    clear_plaintext_lock_password(serial, runtime_dir)
    return password
  config = load_config(runtime_dir)
  device_config = get_device_config(config, serial)
  legacy_password = str(device_config.get("lock_password") or config.get("lock_password") or "").strip()
  if not legacy_password:
    return None
  try:
    set_secure_lock_password(serial, legacy_password)
  except Exception:
    return None
  clear_plaintext_lock_password(serial, runtime_dir)
  return legacy_password


def has_stored_unlock_password(serial: str, runtime_dir: Path | None = None) -> bool:
  if get_secure_lock_password(serial):
    return True
  config = load_config(runtime_dir)
  device_config = get_device_config(config, serial)
  return bool(str(device_config.get("lock_password") or config.get("lock_password") or "").strip())


def cache_unlock_password(serial: str, runtime_dir: Path | None, password: str) -> bool:
  try:
    set_secure_lock_password(serial, password)
    return True
  except Exception:
    return False
  finally:
    clear_plaintext_lock_password(serial, runtime_dir)


def clear_cached_unlock_password(serial: str, runtime_dir: Path | None) -> None:
  try:
    delete_secure_lock_password(serial)
  except Exception:
    pass
  clear_plaintext_lock_password(serial, runtime_dir)


def resolve_unlock_password(serial: str, runtime_dir: Path | None = None) -> tuple[str | None, str | None]:
  password = get_unlock_password()
  if password:
    return password, "env"
  cached = get_cached_unlock_password(serial, runtime_dir)
  if cached:
    return cached, "cache"
  return None, None


def detect_lock_type(
  serial: str,
  runtime_dir: Path | None = None,
  *,
  password: str | None = None,
) -> dict[str, Any]:
  if password and not password.isdigit():
    return {
      "lock_type": "unsupported",
      "reason": "provided_password_not_numeric",
    }
  screenshot_path = capture_screenshot(serial, runtime_dir)
  boxes = load_local_ocr_boxes(runtime_dir, screenshot_path)
  normalized_texts = [normalize_text(str(item.get("text", ""))) for item in boxes if normalize_text(str(item.get("text", "")))]
  digit_texts = {text for text in normalized_texts if text.isdigit() and len(text) == 1}
  if digit_texts:
    return {
      "lock_type": "numeric_pin",
      "reason": "ocr_digits_detected",
      "screenshot_path": str(screenshot_path),
    }
  if password and password.isdigit():
    return {
      "lock_type": "numeric_pin",
      "reason": "numeric_password_provided",
      "screenshot_path": str(screenshot_path),
    }
  if boxes:
    return {
      "lock_type": "unsupported",
      "reason": "ocr_boxes_without_numeric_pin",
      "screenshot_path": str(screenshot_path),
    }
  return {
    "lock_type": "unknown",
    "reason": "ocr_unavailable_or_empty",
    "screenshot_path": str(screenshot_path),
  }


def get_ocr_text_center(boxes: list[dict[str, Any]], text: str) -> tuple[int, int] | None:
  for item in boxes:
    if normalize_text(str(item.get("text", ""))) != normalize_text(text):
      continue
    bounds = item.get("bounds")
    if isinstance(bounds, list) and len(bounds) == 4:
      x1, y1, x2, y2 = [int(value) for value in bounds]
      return ((x1 + x2) // 2, (y1 + y2) // 2)
  return None


def tap_unlock_password_by_ocr(serial: str, password: str, runtime_dir: Path | None = None) -> bool:
  screenshot_path = capture_screenshot(serial, runtime_dir)
  boxes = load_local_ocr_boxes(runtime_dir, screenshot_path)
  centers: list[tuple[int, int]] = []
  for char in password:
    center = get_ocr_text_center(boxes, char)
    if center is None:
      return False
    centers.append(center)
  for center in centers:
    tap_point(serial, center[0], center[1])
  return True


def ensure_device_unlocked(serial: str, runtime_dir: Path | None = None) -> dict[str, Any]:
  before_activity = current_activity(serial)
  if "Keyguard" not in before_activity:
    return {
      "ok": True,
      "status": "already_unlocked",
      "message": "设备已解锁",
      "lock_type": "none",
      "password_source": None,
      "used_cache": False,
      "unlock_attempts": 0,
    }

  password, source = resolve_unlock_password(serial, runtime_dir)
  lock_info = detect_lock_type(serial, runtime_dir, password=password)
  used_cache = source == "cache"
  if lock_info["lock_type"] == "unsupported":
    if used_cache:
      clear_cached_unlock_password(serial, runtime_dir)
    return {
      "ok": False,
      "status": "unsupported_lock_type",
      "message": "当前仅支持无锁屏或数字 PIN 锁屏，请改用数字 PIN 后重试",
      "lock_type": lock_info["lock_type"],
      "password_source": source,
      "used_cache": used_cache,
      "unlock_attempts": 0,
      "fallback_reason": lock_info["reason"],
      "screenshot_path": lock_info.get("screenshot_path"),
    }
  if not password:
    if lock_info["lock_type"] == "unsupported":
      return {
        "ok": False,
        "status": "unsupported_lock_type",
        "message": "当前仅支持无锁屏或数字 PIN 锁屏，请改用数字 PIN 后重试",
        "lock_type": lock_info["lock_type"],
        "password_source": None,
        "used_cache": False,
        "unlock_attempts": 0,
        "fallback_reason": lock_info["reason"],
        "screenshot_path": lock_info.get("screenshot_path"),
      }
    if lock_info["lock_type"] == "unknown":
      return {
        "ok": False,
        "status": "needs_unlock_password",
        "message": "检测到设备需要数字 PIN 锁屏密码，请先提供锁屏密码后重试",
        "password_env": LOCK_PASSWORD_ENV,
        "lock_type": lock_info["lock_type"],
        "password_source": None,
        "used_cache": False,
        "unlock_attempts": 0,
        "fallback_reason": lock_info["reason"],
        "screenshot_path": lock_info.get("screenshot_path"),
      }
    return {
      "ok": False,
      "status": "needs_unlock_password",
      "message": "检测到设备需要数字 PIN 锁屏密码，请先提供锁屏密码后重试",
      "password_env": LOCK_PASSWORD_ENV,
      "lock_type": lock_info["lock_type"],
      "password_source": None,
      "used_cache": False,
      "unlock_attempts": 0,
      "fallback_reason": lock_info["reason"],
      "screenshot_path": lock_info.get("screenshot_path"),
    }
  wake_unlock_device(serial, runtime_dir, password=password)
  for attempt in range(5):
    after_activity = current_activity(serial)
    if "Keyguard" not in after_activity:
      if password:
        cache_unlock_password(serial, runtime_dir, password)
      return {
        "ok": True,
        "status": "unlocked",
        "message": "设备已解锁",
        "lock_type": lock_info["lock_type"],
        "password_source": source,
        "used_cache": used_cache,
        "unlock_attempts": attempt + 1,
      }
    time.sleep(1)

  if password:
    clear_cached_unlock_password(serial, runtime_dir)
    return {
      "ok": False,
      "status": "unlock_password_invalid",
      "message": "锁屏密码错误，请重新提供锁屏密码",
      "lock_type": lock_info["lock_type"],
      "password_source": source,
      "used_cache": used_cache,
      "unlock_attempts": 5,
    }

  return {
    "ok": False,
    "status": "needs_unlock_password",
    "message": "检测到设备需要数字 PIN 锁屏密码，请先提供锁屏密码后重试",
    "password_env": LOCK_PASSWORD_ENV,
    "lock_type": lock_info["lock_type"],
    "password_source": None,
    "used_cache": False,
    "unlock_attempts": 0,
    "fallback_reason": lock_info["reason"],
    "screenshot_path": lock_info.get("screenshot_path"),
  }


def get_vendor_dir(runtime_dir: Path | None = None) -> Path:
  return get_runtime_dir(runtime_dir) / "vendor"


def add_vendor_to_sys_path(runtime_dir: Path | None = None) -> None:
  vendor_dir = get_vendor_dir(runtime_dir)
  if vendor_dir.exists() and str(vendor_dir) not in sys.path:
    sys.path.insert(0, str(vendor_dir))


def get_config_path(runtime_dir: Path | None = None) -> Path:
  return get_runtime_dir(runtime_dir) / "config.json"


def load_config(runtime_dir: Path | None = None) -> dict[str, Any]:
  path = get_config_path(runtime_dir)
  if not path.exists():
    return migrate_legacy_config(build_default_config())
  try:
    raw = json.loads(path.read_text(encoding="utf-8"))
  except json.JSONDecodeError:
    return migrate_legacy_config(build_default_config())
  config = build_default_config()
  config.update(raw)
  return migrate_legacy_config(config)


def save_config(runtime_dir: Path | None, config: dict[str, Any]) -> dict[str, Any]:
  payload = build_default_config()
  payload.update(config)
  payload = migrate_legacy_config(payload)
  payload["lock_password"] = None
  devices = payload.get("devices")
  if isinstance(devices, dict):
    for device_config in devices.values():
      if isinstance(device_config, dict):
        device_config["lock_password"] = None
  path = get_config_path(runtime_dir)
  path.write_text(
    json.dumps(payload, ensure_ascii=False, indent=2),
    encoding="utf-8",
  )
  return payload


def switch_to_model_fallback(runtime_dir: Path | None, reason: str) -> dict[str, Any]:
  config = load_config(runtime_dir)
  config["mode"] = "model_fallback"
  config["local_install_failed"] = True
  config["local_failure_reason"] = reason
  return save_config(runtime_dir, config)


def parse_request(text: str) -> dict[str, Any]:
  normalized = normalize_text(text)
  if any(keyword in normalized for keyword in ("重试本地安装", "恢复本地识别", "重新安装本地依赖")):
    return {
      "intent": "retry-local-install",
      "auto_execute": False,
    }
  if "上班" in normalized and any(keyword in normalized for keyword in ("打卡", "打上班卡", "上班卡")):
    return {
      "intent": "clock-in",
      "auto_execute": any(keyword in normalized for keyword in DIRECT_CLOCK_IN_TEXTS),
    }
  if "下班" in normalized and any(keyword in normalized for keyword in ("打卡", "打下班卡", "下班卡")):
    return {
      "intent": "clock-out",
      "auto_execute": any(keyword in normalized for keyword in DIRECT_CLOCK_OUT_TEXTS),
    }
  if any(keyword in normalized for keyword in ("考勤", "打卡页面", "打开打卡", "进入打卡", "打开考勤")):
    return {
      "intent": "open",
      "auto_execute": False,
    }
  raise ValueError(f"无法识别的意图: {text}")


def parse_intent(text: str) -> str:
  return str(parse_request(text)["intent"])


def normalize_text(text: str) -> str:
  return re.sub(r"\s+", "", text or "").strip()


def text_list_contains(texts: list[str], candidates: tuple[str, ...]) -> str | None:
  normalized_texts = [normalize_text(item) for item in texts]
  for candidate in candidates:
    normalized_candidate = normalize_text(candidate)
    for item in normalized_texts:
      if normalized_candidate and normalized_candidate in item:
        return candidate
  return None


def has_marker_text(texts: list[str], markers: tuple[str, ...]) -> bool:
  normalized_texts = [normalize_text(text) for text in texts if normalize_text(text)]
  normalized_markers = [normalize_text(marker) for marker in markers if normalize_text(marker)]
  return any(marker in text for text in normalized_texts for marker in normalized_markers)


def count_tab_matches(texts: list[str], markers: tuple[str, ...]) -> int:
  normalized_texts = {normalize_text(text) for text in texts if normalize_text(text)}
  return sum(1 for marker in markers if normalize_text(marker) in normalized_texts)


def has_dingtalk_tab_bar(texts: list[str]) -> bool:
  return count_tab_matches(texts, DINGTALK_BOTTOM_TABS) >= 2


def has_non_dingtalk_tab_bar(texts: list[str]) -> bool:
  tab_groups = (
    APP_MARKET_BOTTOM_TABS,
    ATTENDANCE_BOTTOM_TABS,
  )
  return any(count_tab_matches(texts, group) >= 2 for group in tab_groups)


def decide_attendance_action(intent: str, texts: list[str]) -> dict[str, str]:
  normalized = [normalize_text(text) for text in texts if normalize_text(text)]
  if intent == "clock-in":
    if any("上班已打卡" in text or "已打上班卡" in text or "今日上班已打卡" in text for text in normalized):
      return {
        "status": "already_done",
        "message": "已经打过上班卡",
      }
    if (
      any("上班" in text for text in normalized)
      and any("打卡结果" in text or "打卡成功" in text or "极速打卡·成功" in text for text in normalized)
    ):
      return {
        "status": "already_done",
        "message": "已经打过上班卡",
      }
    matched = text_list_contains(texts, ("上班打卡", "上班卡", "立即打卡", "更新打卡"))
    if matched:
      return {
        "status": "ready_to_click",
        "matched_text": matched,
      }
  if intent == "clock-out":
    if any("下班已打卡" in text or "已打下班卡" in text or "今日下班已打卡" in text for text in normalized):
      return {
        "status": "needs_confirmation",
        "message": "已经打过下班卡，是否需要再次打下班卡",
      }
    if (
      any("下班" in text for text in normalized)
      and any("打卡结果" in text or "打卡成功" in text or "极速打卡·成功" in text for text in normalized)
    ):
      return {
        "status": "needs_confirmation",
        "message": "已经打过下班卡，是否需要再次打下班卡",
      }
    matched = text_list_contains(texts, ("下班打卡", "下班卡", "立即打卡", "更新打卡"))
    if matched:
      return {
        "status": "ready_to_click",
        "matched_text": matched,
      }
  return {
    "status": "not_found",
    "message": "未识别到可执行的打卡按钮",
  }


def suggest_open_action(page_type: str, texts: list[str]) -> dict[str, str]:
  normalized = [normalize_text(text) for text in texts if normalize_text(text)]
  if page_type == "lockscreen":
    return {"action": "unlock-device", "message": "设备锁屏，先唤醒解锁"}
  if page_type == "external":
    return {"action": "launch-dingtalk", "message": "当前不在钉钉，重新拉起钉钉"}
  if page_type == "attendance":
    return {"action": "done", "message": "已进入考勤主页面"}
  if page_type == "attendance-subpage":
    return {"action": "tap-back", "message": "当前在考勤子页面，先返回到打卡主页"}
  if page_type == "attendance-notice":
    return {"action": "tap-back", "message": "当前是打卡通知页，先返回上一页"}
  if page_type in {"dingtalk-other", "webview"} and has_non_dingtalk_tab_bar(normalized):
    return {"action": "tap-back", "message": "当前页底部 tabs 不是钉钉主 tabs，先返回上一页"}
  if page_type in {"dingtalk-other", "webview"} and "返回" in normalized and not has_dingtalk_tab_bar(normalized):
    return {"action": "tap-back", "message": "当前在钉钉内部页面，先返回上一页"}
  if page_type in {"home", "dingtalk-other", "webview"}:
    return {"action": "tap-workbench", "message": "当前不在工作台，先切到工作台"}
  if page_type == "workbench":
    if any(any(marker in text for marker in ATTENDANCE_TEXTS) for text in normalized):
      return {"action": "tap-attendance-entry", "message": "工作台已出现考勤入口，点击进入"}
    if not has_marker_text(normalized, WORKBENCH_TOP_MARKERS):
      return {
        "action": "scroll-workbench-top",
        "message": "工作台当前不在顶部，先滑动回到顶部",
      }
    return {
      "action": "tap-app-center",
      "message": "工作台首屏未识别到考勤文字，先打开应用中心或更多入口",
    }
  return {"action": "needs-model", "message": "页面状态未知，需要模型查看截图后决定下一步"}


def ensure_command(name: str) -> None:
  if shutil.which(name) is None:
    raise RuntimeError(f"缺少命令: {name}")


def run_command(
  command: list[str],
  *,
  check: bool = True,
  capture_output: bool = True,
  text: bool = True,
  timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
  return subprocess.run(
    command,
    check=check,
    capture_output=capture_output,
    text=text,
    timeout=timeout,
  )


def adb_command(
  serial: str | None,
  *args: str,
  check: bool = True,
  capture_output: bool = True,
  text: bool = True,
  timeout: int = 30,
) -> subprocess.CompletedProcess[str]:
  ensure_command("adb")
  command = ["adb"]
  if serial:
    command.extend(["-s", serial])
  command.extend(args)
  return run_command(
    command,
    check=check,
    capture_output=capture_output,
    text=text,
    timeout=timeout,
  )


def list_connected_devices() -> list[str]:
  result = adb_command(None, "devices", check=True)
  devices: list[str] = []
  for line in result.stdout.splitlines():
    line = line.strip()
    if not line or line.startswith("List of devices"):
      continue
    parts = line.split()
    if len(parts) >= 2 and parts[1] == "device":
      devices.append(parts[0])
  return devices


def choose_device(serial: str | None = None) -> str:
  devices = list_connected_devices()
  if serial:
    if serial not in devices:
      raise RuntimeError(f"未找到指定设备: {serial}")
    return serial
  if not devices:
    raise RuntimeError("未检测到 adb 设备")
  return devices[0]


def wake_unlock_device(
  serial: str,
  runtime_dir: Path | None = None,
  *,
  password: str | None = None,
) -> None:
  adb_command(serial, "shell", "input", "keyevent", "KEYCODE_WAKEUP", check=False)
  adb_command(serial, "shell", "svc", "power", "stayon", "usb", check=False)
  adb_command(serial, "shell", "input", "swipe", "540", "1600", "540", "400", "300", check=False)
  if password:
    if password.isdigit() and tap_unlock_password_by_ocr(serial, password, runtime_dir):
      pass
    elif password.isdigit():
      for digit in password:
        adb_command(serial, "shell", "input", "keyevent", f"KEYCODE_{digit}", check=False)
      adb_command(serial, "shell", "input", "keyevent", "KEYCODE_ENTER", check=False)
    else:
      adb_command(serial, "shell", "input", "text", password, check=False)
      adb_command(serial, "shell", "input", "keyevent", "KEYCODE_ENTER", check=False)
  time.sleep(1)


def launch_dingtalk(serial: str) -> None:
  adb_command(
    serial,
    "shell",
    "monkey",
    "-p",
    PACKAGE_NAME,
    "-c",
    "android.intent.category.LAUNCHER",
    "1",
    check=False,
  )
  time.sleep(2)


def get_focus_snapshot(serial: str) -> str:
  result = adb_command(serial, "shell", "dumpsys", "window", check=False)
  return result.stdout


def current_activity(serial: str) -> str:
  snapshot = get_focus_snapshot(serial)
  for line in snapshot.splitlines():
    if "mCurrentFocus=" in line:
      return line.strip()
  return ""


def classify_page(activity: str, texts: list[str] | None = None) -> str:
  normalized_texts = [normalize_text(text) for text in (texts or [])]
  attendance_markers = ("考勤打卡", "上班打卡", "下班打卡", "打卡结果", "立即打卡", "极速打卡")
  attendance_subpage_markers = ("统计", "设置", "回到今天", "考勤助理")
  if "Keyguard" in activity:
    return "lockscreen"
  if PACKAGE_NAME not in activity:
    return "external"
  if "EnterpriseOAListActivity" in activity:
    return "attendance-notice"
  if any(hint in activity for hint in HOME_ACTIVITY_HINTS):
    if has_marker_text(normalized_texts, MESSAGE_PAGE_MARKERS):
      return "home"
    if has_marker_text(normalized_texts, PROFILE_PAGE_MARKERS):
      return "home"
    if has_marker_text(normalized_texts, WORKBENCH_PAGE_MARKERS):
      return "workbench"
    if "工作台" in normalized_texts:
      return "workbench"
    return "home"
  if any(marker in text for marker in attendance_markers for text in normalized_texts):
    return "attendance"
  if "TheOneActivityMainTask" in activity:
    return "attendance"
  if "TheOneActivity" in activity and has_marker_text(normalized_texts, attendance_subpage_markers):
    return "attendance-subpage"
  if "CommonWebViewActivity" in activity and any("考勤" in text or "打卡" in text for text in normalized_texts):
    return "attendance"
  if "CommonWebViewActivity" in activity:
    return "webview"
  return "dingtalk-other"


def current_page_type(serial: str, texts: list[str] | None = None) -> str:
  activity = current_activity(serial)
  return classify_page(activity, texts)


def should_wait_for_ui(activity: str, texts: list[str]) -> bool:
  normalized_texts = [normalize_text(text) for text in texts if normalize_text(text)]
  if PACKAGE_NAME in activity and not normalized_texts:
    return True
  if "LaunchHomeActivity" in activity and len(normalized_texts) < 2:
    return True
  return False


def make_temp_path(runtime_dir: Path | None, suffix: str) -> Path:
  temp_dir = get_runtime_dir(runtime_dir) / "tmp"
  temp_dir.mkdir(parents=True, exist_ok=True)
  return temp_dir / f"{uuid.uuid4().hex}{suffix}"


def dump_ui_xml(serial: str, runtime_dir: Path | None = None) -> Path:
  remote_path = f"/sdcard/{uuid.uuid4().hex}.xml"
  local_path = make_temp_path(runtime_dir, ".xml")
  adb_command(serial, "shell", "uiautomator", "dump", remote_path, check=False)
  adb_command(serial, "pull", remote_path, str(local_path), check=False)
  adb_command(serial, "shell", "rm", "-f", remote_path, check=False)
  return local_path


def capture_screenshot(serial: str, runtime_dir: Path | None = None) -> Path:
  remote_path = f"/sdcard/{uuid.uuid4().hex}.png"
  local_path = make_temp_path(runtime_dir, ".png")
  adb_command(serial, "shell", "screencap", "-p", remote_path, check=False)
  adb_command(serial, "pull", remote_path, str(local_path), check=False)
  adb_command(serial, "shell", "rm", "-f", remote_path, check=False)
  return local_path


def collect_ui_texts(xml_path: Path) -> list[str]:
  if not xml_path.exists():
    return []
  texts: list[str] = []
  try:
    root = ET.parse(xml_path).getroot()
  except ET.ParseError:
    return texts
  for node in root.iter("node"):
    text = node.attrib.get("text", "")
    desc = node.attrib.get("content-desc", "")
    if text:
      texts.append(text)
    if desc:
      texts.append(desc)
  return texts


def parse_bounds(bounds: str) -> tuple[int, int, int, int] | None:
  match = re.match(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]", bounds or "")
  if not match:
    return None
  return tuple(int(value) for value in match.groups())  # type: ignore[return-value]


def center_of_bounds(bounds: str) -> tuple[int, int] | None:
  parsed = parse_bounds(bounds)
  if not parsed:
    return None
  x1, y1, x2, y2 = parsed
  return ((x1 + x2) // 2, (y1 + y2) // 2)


def find_text_bounds(
  xml_path: Path,
  candidates: tuple[str, ...],
  *,
  contains: bool = True,
) -> tuple[str, tuple[int, int] | None] | None:
  if not xml_path.exists():
    return None
  try:
    root = ET.parse(xml_path).getroot()
  except ET.ParseError:
    return None
  for node in root.iter("node"):
    values = [node.attrib.get("text", ""), node.attrib.get("content-desc", "")]
    for value in values:
      normalized_value = normalize_text(value)
      if not normalized_value:
        continue
      for candidate in candidates:
        normalized_candidate = normalize_text(candidate)
        if contains and normalized_candidate in normalized_value:
          return candidate, center_of_bounds(node.attrib.get("bounds", ""))
        if not contains and normalized_candidate == normalized_value:
          return candidate, center_of_bounds(node.attrib.get("bounds", ""))
  return None


def tap_point(serial: str, x: int, y: int) -> None:
  adb_command(serial, "shell", "input", "tap", str(x), str(y), check=False)
  time.sleep(1)


def swipe_point(serial: str, start_x: int, start_y: int, end_x: int, end_y: int, duration_ms: int = 300) -> None:
  adb_command(
    serial,
    "shell",
    "input",
    "swipe",
    str(start_x),
    str(start_y),
    str(end_x),
    str(end_y),
    str(duration_ms),
    check=False,
  )
  time.sleep(1)


def get_relative_point(width: int, height: int, x_ratio: float, y_ratio: float) -> tuple[int, int]:
  return (int(width * x_ratio), int(height * y_ratio))


def get_screen_size(serial: str) -> tuple[int, int]:
  result = adb_command(serial, "shell", "wm", "size", check=False)
  for line in result.stdout.splitlines():
    if "Physical size:" not in line:
      continue
    try:
      size = line.split("Physical size:", 1)[1].strip()
      width_text, height_text = size.split("x", 1)
      return int(width_text), int(height_text)
    except Exception:
      continue
  return (1080, 1920)


def tap_bounds_center(serial: str, bounds: str) -> bool:
  center = center_of_bounds(bounds)
  if center is None:
    return False
  tap_point(serial, center[0], center[1])
  return True


def press_back(serial: str) -> None:
  adb_command(serial, "shell", "input", "keyevent", "KEYCODE_BACK", check=False)
  time.sleep(1)


def click_first_matching_text(serial: str, xml_path: Path, candidates: tuple[str, ...]) -> str | None:
  found = find_text_bounds(xml_path, candidates)
  if not found:
    return None
  matched, center = found
  if center is None:
    return None
  tap_point(serial, center[0], center[1])
  return matched


def create_paddle_ocr_instance(paddle_ocr_cls: Any) -> Any:
  signature = inspect.signature(paddle_ocr_cls.__init__)
  kwargs: dict[str, Any] = {"lang": "ch"}
  if "use_textline_orientation" in signature.parameters:
    kwargs["use_textline_orientation"] = True
  elif "use_angle_cls" in signature.parameters:
    kwargs["use_angle_cls"] = True
  if "show_log" in signature.parameters:
    kwargs["show_log"] = False
  return paddle_ocr_cls(**kwargs)


def create_rapid_ocr_instance(rapid_ocr_cls: Any) -> Any:
  return rapid_ocr_cls()


def parse_rapid_ocr_result(result: Any) -> list[dict[str, Any]]:
  boxes: list[dict[str, Any]] = []
  for item in result or []:
    if not isinstance(item, (list, tuple)) or len(item) < 3:
      continue
    box, text, score = item[0], item[1], item[2]
    if not isinstance(box, (list, tuple)) or len(box) < 4:
      continue
    xs = [int(point[0]) for point in box]
    ys = [int(point[1]) for point in box]
    boxes.append(
      {
        "text": str(text),
        "score": float(score),
        "bounds": [min(xs), min(ys), max(xs), max(ys)],
      }
    )
  return boxes


def load_local_ocr_boxes(runtime_dir: Path | None, image_path: Path) -> list[dict[str, Any]]:
  global _PADDLE_OCR_INSTANCE, _PADDLE_OCR_UNAVAILABLE, _RAPID_OCR_INSTANCE, _RAPID_OCR_UNAVAILABLE
  add_vendor_to_sys_path(runtime_dir)
  os.environ.setdefault("PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK", "True")
  if not _PADDLE_OCR_UNAVAILABLE:
    try:
      from paddleocr import PaddleOCR  # type: ignore
    except Exception:
      _PADDLE_OCR_UNAVAILABLE = True
    else:
      if _PADDLE_OCR_INSTANCE is None:
        try:
          with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            _PADDLE_OCR_INSTANCE = create_paddle_ocr_instance(PaddleOCR)
        except Exception:
          _PADDLE_OCR_UNAVAILABLE = True
      if _PADDLE_OCR_INSTANCE is not None:
        try:
          with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = _PADDLE_OCR_INSTANCE.ocr(str(image_path), cls=True)
          boxes: list[dict[str, Any]] = []
          for line_group in result or []:
            for line in line_group or []:
              box, payload = line
              text, score = payload
              xs = [int(point[0]) for point in box]
              ys = [int(point[1]) for point in box]
              boxes.append(
                {
                  "text": text,
                  "score": float(score),
                  "bounds": [min(xs), min(ys), max(xs), max(ys)],
                }
              )
          if boxes:
            return boxes
        except Exception:
          _PADDLE_OCR_UNAVAILABLE = True

  if _RAPID_OCR_UNAVAILABLE:
    return []
  if _RAPID_OCR_INSTANCE is None:
    try:
      with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        from rapidocr_onnxruntime import RapidOCR  # type: ignore
    except Exception:
      _RAPID_OCR_UNAVAILABLE = True
      return []
    try:
      with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        _RAPID_OCR_INSTANCE = create_rapid_ocr_instance(RapidOCR)
    except Exception:
      _RAPID_OCR_UNAVAILABLE = True
      return []
  try:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
      result, _ = _RAPID_OCR_INSTANCE(str(image_path))
    return parse_rapid_ocr_result(result)
  except Exception:
    _RAPID_OCR_UNAVAILABLE = True
    return []


def ocr_texts(boxes: list[dict[str, Any]]) -> list[str]:
  return [str(item.get("text", "")) for item in boxes if item.get("text")]


def find_ocr_target(boxes: list[dict[str, Any]], candidates: tuple[str, ...]) -> tuple[str, tuple[int, int] | None] | None:
  for candidate in candidates:
    normalized_candidate = normalize_text(candidate)
    for item in boxes:
      normalized_text = normalize_text(str(item.get("text", "")))
      if normalized_candidate and normalized_candidate in normalized_text:
        bounds = item.get("bounds")
        if isinstance(bounds, list) and len(bounds) == 4:
          x1, y1, x2, y2 = [int(value) for value in bounds]
          return candidate, ((x1 + x2) // 2, (y1 + y2) // 2)
        return candidate, None
  return None


def load_template_match(image_path: Path, template_path: Path, threshold: float = 0.85) -> tuple[int, int] | None:
  add_vendor_to_sys_path(None)
  try:
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
      import cv2  # type: ignore
  except Exception:
    return None
  if not image_path.exists() or not template_path.exists():
    return None
  source = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
  template = cv2.imread(str(template_path), cv2.IMREAD_COLOR)
  if source is None or template is None:
    return None
  result = cv2.matchTemplate(source, template, cv2.TM_CCOEFF_NORMED)
  _, max_score, _, max_loc = cv2.minMaxLoc(result)
  if max_score < threshold:
    return None
  height, width = template.shape[:2]
  return (max_loc[0] + width // 2, max_loc[1] + height // 2)


def click_popup_or_back_if_needed(
  serial: str,
  xml_path: Path,
  runtime_dir: Path | None = None,
  screenshot_path: Path | None = None,
) -> str | None:
  matched = click_first_matching_text(serial, xml_path, POPUP_TEXTS)
  if matched:
    return f"clicked:{matched}"
  screenshot = screenshot_path or capture_screenshot(serial, runtime_dir)
  assets_dir = SKILL_ROOT / "assets"
  for template_name in ("close-template.png", "back-template.png", "update-later-template.png"):
    center = load_template_match(screenshot, assets_dir / template_name)
    if center:
      tap_point(serial, center[0], center[1])
      return f"template:{template_name}"
  return None


def build_model_fallback_payload(
  *,
  intent: str,
  serial: str,
  activity: str,
  screenshot_path: Path,
  message: str,
  texts: list[str] | None = None,
  fallback_reason: str | None = None,
) -> dict[str, Any]:
  visible_texts = texts or []
  prompt_lines = [
    "请查看这张手机截图，并结合当前页面文本与 Activity，只做一步安全操作判断。",
    "优先处理弹窗关闭、暂不更新、左上角返回、进入工作台、进入考勤入口。",
    "如果判断不清楚，不要连续盲点。",
    f"当前意图: {intent}",
    f"当前 Activity: {activity}",
    f"可见文本: {' | '.join(visible_texts[:12]) if visible_texts else '无'}",
    "允许动作: tap-workbench, tap-app-center, tap-attendance-entry, tap-back-icon, back, tap",
    "请直接回答下一步动作，并保持只做一步。",
  ]
  return {
    "status": "needs_model_input",
    "intent": intent,
    "serial": serial,
    "activity": activity,
    "screenshot_path": str(screenshot_path),
    "message": message,
    "fallback_reason": fallback_reason,
    "visible_texts": visible_texts,
    "model_handoff": {
      "image_path": str(screenshot_path),
      "allowed_actions": list(MODEL_ALLOWED_ACTIONS),
      "prompt": "\n".join(prompt_lines),
    },
  }
