"""
전원/세션 상태 보조 (Windows).

스케줄러가 20:00에 PC를 깨워도 사용자가 없으면 Modern Standby 로 곧바로 다시 들어가
다운로더 앱과 GUI 클릭 자동화가 동작하지 않는다 (2026-10-12/13: 20:01~20:07 사이 절전 진입/해제 7회
반복, 클릭 12회가 모두 무효). 파이프라인이 도는 동안 절전을 막고, 화면이 꺼져 있으면 깨우고,
세션이 잠겨 있으면 알 수 있게 한다.
"""

import ctypes
import sys
import time

ES_CONTINUOUS = 0x80000000
ES_SYSTEM_REQUIRED = 0x00000001
ES_DISPLAY_REQUIRED = 0x00000002

MOUSEEVENTF_MOVE = 0x0001
DESKTOP_SWITCHDESKTOP = 0x0100


def prevent_sleep() -> bool:
    """이 스레드가 살아 있는 동안 시스템/디스플레이 절전을 막는다. allow_sleep() 으로 해제."""
    if sys.platform != "win32":
        return False
    try:
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_DISPLAY_REQUIRED))
    except Exception:
        return False


def allow_sleep() -> None:
    if sys.platform != "win32":
        return
    try:
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except Exception:
        pass


def wake_display() -> None:
    """꺼진 화면을 켜기 위해 마우스를 1px 움직였다 되돌린다 (입력 이벤트로 취급됨)."""
    if sys.platform != "win32":
        return
    try:
        mouse_event = ctypes.windll.user32.mouse_event
        mouse_event(MOUSEEVENTF_MOVE, 1, 0, 0, 0)
        time.sleep(0.05)
        mouse_event(MOUSEEVENTF_MOVE, -1, 0, 0, 0)
    except Exception:
        pass


def is_desktop_locked() -> bool:
    """잠금 화면(보안 데스크톱)이면 True. 이때는 클릭 자동화가 전달되지 않는다."""
    if sys.platform != "win32":
        return False
    try:
        user32 = ctypes.windll.user32
        handle = user32.OpenInputDesktop(0, False, DESKTOP_SWITCHDESKTOP)
        if not handle:
            return True
        switched = user32.SwitchDesktop(handle)
        user32.CloseDesktop(handle)
        return not switched
    except Exception:
        return False
