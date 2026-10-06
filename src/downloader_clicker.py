"""
EBS Downloader 데스크톱 앱 자동 클릭 (멀티모니터 + DPI 대응).

PyAutoGUI 대신 Windows API (ctypes) 직접 호출로 멀티모니터 안전.
"""

import ctypes
import sys
import time

# DPI Awareness 활성화
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except (AttributeError, OSError):
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except (AttributeError, OSError):
        pass

try:
    import pygetwindow as gw
    HAS_PYGETWINDOW = True
except ImportError:
    HAS_PYGETWINDOW = False


# ==============================================================================
# Windows API 직접 호출
# ==============================================================================

MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def win_set_cursor_pos(x: int, y: int) -> bool:
    try:
        return bool(ctypes.windll.user32.SetCursorPos(int(x), int(y)))
    except Exception as e:
        print(f"   [ERROR] SetCursorPos 실패: {e}")
        return False


def win_get_cursor_pos() -> tuple:
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return (pt.x, pt.y)


def win_left_click():
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def win_move_and_click(x: int, y: int) -> bool:
    if not win_set_cursor_pos(x, y):
        return False
    time.sleep(0.3)
    actual = win_get_cursor_pos()
    if abs(actual[0] - x) > 5 or abs(actual[1] - y) > 5:
        print(f"   [WARN] 커서 이동 어긋남: 요청 ({x},{y}) vs 실제 {actual}")
    win_left_click()
    return True


def win_set_foreground_window(hwnd) -> bool:
    try:
        ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        time.sleep(0.2)
        return bool(ctypes.windll.user32.SetForegroundWindow(hwnd))
    except Exception:
        return False


# ==============================================================================
# 창 검색
# ==============================================================================

STRONG_KEYWORDS = ["다운로더", "downloader"]

EXCLUDE_KEYWORDS = [
    "Chrome", "Chromium", "Edge", "Firefox", "Safari", "Opera",
    "Whale", "Brave", "Internet Explorer",
    "Visual Studio", "VSCode", "Cursor", "PyCharm",
    "PowerShell", "cmd", "터미널", "Terminal",
    "왕초보 영어", "교육의 중심", "EBS - ",
    "탐색기", "Explorer",
]

MIN_WIDTH, MAX_WIDTH = 300, 1500
MIN_HEIGHT, MAX_HEIGHT = 300, 1500


def is_excluded_window(title: str) -> bool:
    title_lower = title.lower()
    for kw in EXCLUDE_KEYWORDS:
        if kw.lower() in title_lower:
            return True
    return False


def is_size_in_range(win) -> bool:
    return (MIN_WIDTH <= win.width <= MAX_WIDTH and
            MIN_HEIGHT <= win.height <= MAX_HEIGHT)


def find_ebs_downloader_window(debug: bool = False):
    """EBS Downloader 창만 정확히 찾기"""
    if not HAS_PYGETWINDOW:
        return None

    try:
        all_windows = gw.getAllWindows()
    except Exception as e:
        if debug:
            print(f"   [DEBUG] 창 목록 실패: {e}")
        return None

    candidates = []
    for win in all_windows:
        if not win.visible or win.width < 50 or win.height < 50:
            continue

        title = win.title or ""
        title_lower = title.lower()

        if not any(kw.lower() in title_lower for kw in STRONG_KEYWORDS):
            continue

        if is_excluded_window(title):
            if debug:
                print(f"   [DEBUG] 제외(브라우저/IDE): '{title[:50]}'")
            continue

        if not is_size_in_range(win):
            if debug:
                print(f"   [DEBUG] 제외(크기 {win.width}x{win.height}): '{title[:50]}'")
            continue

        candidates.append(win)
        if debug:
            print(f"   [DEBUG] 후보: '{title[:50]}' ({win.width}x{win.height} @ {win.left},{win.top})")

    if not candidates:
        return None

    candidates.sort(key=lambda w: w.width * w.height)
    return candidates[0]


def click_download_button_in_window(win, dry_run: bool = False, debug: bool = False) -> bool:
    """창의 '다운로드 실행' 버튼만 클릭"""
    x, y = win.left, win.top
    w, h = win.width, win.height

    btn_x = int(x + w * 0.89)
    btn_y = int(y + h * 0.79)

    print(f"   창 위치: ({x}, {y}) / 크기: {w}x{h}")
    print(f"   [CLICK] '다운로드 실행' 버튼 클릭: ({btn_x}, {btn_y})")

    if not dry_run:
        hwnd = win._hWnd
        win_set_foreground_window(hwnd)
        time.sleep(0.5)
        ok = win_move_and_click(btn_x, btn_y)
        # 백그라운드 프로세스의 포커스 제한으로 첫 클릭이 창 활성화에만 쓰일 수 있어 한 번 더 클릭.
        # 다운로드가 이미 시작됐다면 버튼이 비활성화되어 두 번째 클릭은 영향이 없다.
        time.sleep(2.0)
        win_set_foreground_window(hwnd)
        time.sleep(0.5)
        win_move_and_click(btn_x, btn_y)
        return ok
    return True


def close_downloader_window(timeout: float = 10.0) -> bool:
    """EBS Downloader 창의 우측 상단 'X' 버튼을 눌러 종료"""
    print(f"\n[CLOSE] EBS Downloader 종료 시도...")
    win = find_ebs_downloader_window()
    if not win:
        print("   - 종료할 창을 찾지 못했습니다. (이미 닫혔을 수 있음)")
        return False

    x, y = win.left, win.top
    w, h = win.width, win.height
    
    # 1. 우측 상단 'X' 버튼 클릭
    close_x = int(x + w * 0.965)
    close_y = int(y + h * 0.045)
    
    print(f"   - 'X' 버튼 클릭: ({close_x}, {close_y})")
    win_set_foreground_window(win._hWnd)
    time.sleep(0.5)
    win_move_and_click(close_x, close_y)
    
    # 2. 종료 확인 다이얼로그 대응 ("예(Y)" 버튼 클릭)
    # 다이얼로그가 뜨는 시간을 대기
    time.sleep(1.2)
    
    # 다이얼로그 창을 다시 찾음 (보통 메인 창보다 작음)
    dialog = find_ebs_downloader_window()
    if dialog and dialog.width < w:
        print(f"   - 확인 다이얼로그 발견: '{dialog.title}'")
        win_set_foreground_window(dialog._hWnd)
        time.sleep(0.3)
        # 다이얼로그 내의 "예(Y)" 버튼 위치 (중앙보다 약간 왼쪽)
        ok_x = int(dialog.left + dialog.width * 0.40)
        ok_y = int(dialog.top + dialog.height * 0.73)
    else:
        # 다이얼로그를 못 찾으면 메인 창 기준 추정 좌표 (이미지 기반 보정)
        print("   - 다이얼로그를 개별 창으로 찾지 못해 메인 창 기준 좌표로 시도")
        ok_x = int(x + w * 0.44)
        ok_y = int(y + h * 0.585)

    print(f"   - '예(Y)' 버튼 클릭 시도: ({ok_x}, {ok_y})")
    win_move_and_click(ok_x, ok_y)
    
    print("✅ EBS Downloader 종료 시도 완료.")
    return True


def click_download_button(timeout: float = 30.0,
                         dry_run: bool = False,
                         debug: bool = False) -> bool:
    """EBS Downloader 창을 찾아 '다운로드 실행' 버튼 클릭"""
    if not HAS_PYGETWINDOW:
        print("   [ERROR] pygetwindow 미설치: pip install pygetwindow")
        return False

    print(f"[FIND] EBS Downloader 창 검색 중... (최대 {timeout:.0f}초)")
    if debug:
        print("   [DEBUG] 디버그 모드 ON")

    start = time.time()
    last_print = 0
    win = None

    while time.time() - start < timeout:
        win = find_ebs_downloader_window(debug=debug)
        if win:
            print(f"[OK] 창 발견: '{win.title}'")
            print(f"     크기: {win.width}x{win.height} @ ({win.left},{win.top})")
            break

        elapsed = int(time.time() - start)
        if elapsed - last_print >= 5:
            print(f"   ... 대기 중 ({int(timeout - elapsed)}초 남음)")
            last_print = elapsed
        time.sleep(1.5)

    if not win:
        print("[FAIL] EBS Downloader 창을 찾지 못했습니다.")
        return False

    time.sleep(1.0)
    print("[CLICK] '다운로드 실행' 버튼 클릭...")
    success = click_download_button_in_window(win, dry_run=dry_run, debug=debug)

    if success:
        print("[OK] 클릭 완료.")
    return success


def list_all_visible_windows():
    """디버그용: 모든 창 목록"""
    if not HAS_PYGETWINDOW:
        print("pygetwindow 미설치")
        return

    print("=" * 100)
    print("현재 보이는 모든 창:")
    print("=" * 100)

    try:
        for i, win in enumerate(gw.getAllWindows()):
            if not win.visible or win.width < 50:
                continue
            title = (win.title or "(제목 없음)")[:58]
            size = f"{win.width}x{win.height}"
            pos = f"({win.left},{win.top})"

            marker = ""
            if any(kw.lower() in (win.title or "").lower() for kw in STRONG_KEYWORDS):
                if not is_excluded_window(win.title or ""):
                    marker = " ← EBS Downloader 후보"

            print(f"{i:>4} {title:<60} {size:<12} {pos:<20}{marker}")
    except Exception as e:
        print(f"오류: {e}")
    print("=" * 100)


# ==============================================================================
# 단독 실행
# ==============================================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--list-windows", action="store_true")
    args = parser.parse_args()

    if args.list_windows:
        list_all_visible_windows()
        sys.exit(0)

    success = click_download_button(
        timeout=args.timeout, dry_run=args.dry_run, debug=args.debug
    )
    sys.exit(0 if success else 1)
