"""
EBS Downloader 데스크톱 앱의 '다운로드 실행' 버튼 자동 클릭 모듈
(멀티모니터 + DPI 스케일링 + 확장 모니터 환경 대응)

핵심 변경 (이전 버전 대비):
  - PyAutoGUI 의 moveTo/click 은 멀티모니터에서 불안정
  - Windows API (ctypes) 로 직접 마우스 제어 → 모든 모니터 영역 정상 동작
  - SetProcessDPIAware() 로 DPI 스케일링 무력화

전략:
  1. pygetwindow 로 EBS Downloader 창만 정확히 찾기
  2. 창 위치/크기로 '다운로드 실행' 버튼 절대 좌표 계산
  3. Windows API SetCursorPos + mouse_event 로 직접 클릭

이미지 4 분석:
  - 창 크기 약 660 x 650
  - '다운로드 실행' 버튼 위치 (창 기준): 약 (590, 515)
  - 비율: x = 0.89, y = 0.79
"""

import ctypes
import sys
import time

# DPI Awareness 활성화 (멀티모니터 + DPI 스케일링 대응)
# 이걸 안 하면 윈도우가 좌표를 자동 스케일링해서 어긋남
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
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
# Windows API 직접 호출 - 멀티모니터 안전한 마우스 제어
# ==============================================================================

# Windows mouse_event 플래그
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


def win_set_cursor_pos(x: int, y: int) -> bool:
    """Windows SetCursorPos: 멀티모니터 전체 영역에서 동작"""
    try:
        return bool(ctypes.windll.user32.SetCursorPos(int(x), int(y)))
    except Exception as e:
        print(f"   [ERROR] SetCursorPos 실패: {e}")
        return False


def win_get_cursor_pos() -> tuple:
    """현재 마우스 위치 조회 (멀티모니터 안전)"""
    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    pt = POINT()
    ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
    return (pt.x, pt.y)


def win_left_click():
    """현재 위치에서 왼쪽 클릭 (DOWN + UP)"""
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)
    ctypes.windll.user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def win_move_and_click(x: int, y: int) -> bool:
    """좌표로 이동 후 클릭 (멀티모니터 안전)"""
    if not win_set_cursor_pos(x, y):
        return False
    time.sleep(0.3)  # 커서 이동이 반영될 시간

    # 이동이 실제로 됐는지 확인
    actual = win_get_cursor_pos()
    if abs(actual[0] - x) > 5 or abs(actual[1] - y) > 5:
        print(f"   [WARN] 커서 이동 어긋남: 요청 ({x},{y}) vs 실제 {actual}")

    win_left_click()
    return True


def win_set_foreground_window(hwnd) -> bool:
    """창을 앞으로 가져오기 (Windows API)"""
    try:
        # 최소화 해제
        ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
        time.sleep(0.2)
        return bool(ctypes.windll.user32.SetForegroundWindow(hwnd))
    except Exception:
        return False


# ==============================================================================
# 창 검색
# ==============================================================================

# EBS Downloader 창 제목 키워드 (대소문자 무시)
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


def check_dependencies() -> bool:
    if not HAS_PYGETWINDOW:
        print("   [ERROR] pygetwindow 가 필요합니다: pip install pygetwindow")
        return False
    return True


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
            print(f"   [DEBUG] 창 목록 가져오기 실패: {e}")
        return None

    candidates = []

    for win in all_windows:
        if not win.visible:
            continue
        if win.width < 50 or win.height < 50:
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
    """
    EBS Downloader 창에서 '다운로드 실행' 버튼 클릭.
    Windows API 직접 사용으로 멀티모니터/DPI 안전.
    """
    x, y = win.left, win.top
    w, h = win.width, win.height

    btn_x_ratio = 0.89
    btn_y_ratio = 0.79

    btn_x = int(x + w * btn_x_ratio)
    btn_y = int(y + h * btn_y_ratio)

    print(f"   창 위치: ({x}, {y}) / 크기: {w}x{h}")
    print(f"   클릭 좌표: ({btn_x}, {btn_y})")

    if dry_run:
        # dry-run 에서도 마우스는 이동시켜서 좌표 확인 가능하게
        print("   (dry-run: 마우스만 이동, 클릭하지 않음)")
        win_set_cursor_pos(btn_x, btn_y)
        time.sleep(0.5)
        actual = win_get_cursor_pos()
        print(f"   실제 마우스 위치: {actual}")
        return True

    # 창 활성화 (Windows API)
    try:
        hwnd = win._hWnd
        win_set_foreground_window(hwnd)
        time.sleep(0.5)
    except Exception as e:
        if debug:
            print(f"   [DEBUG] 창 활성화 실패: {e}")

    # 클릭
    success = win_move_and_click(btn_x, btn_y)
    return success


def click_download_button(timeout: float = 30.0,
                         dry_run: bool = False,
                         debug: bool = False) -> bool:
    """EBS Downloader 창을 찾아 '다운로드 실행' 버튼 클릭"""
    if not check_dependencies():
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
            print(f"[OK] EBS Downloader 창 발견: '{win.title}'")
            print(f"     크기: {win.width}x{win.height} @ ({win.left},{win.top})")
            break

        elapsed = int(time.time() - start)
        if elapsed - last_print >= 5:
            remaining = int(timeout - elapsed)
            print(f"   ... 대기 중 ({remaining}초 남음)")
            last_print = elapsed

        time.sleep(1.5)

    if not win:
        print("[FAIL] EBS Downloader 창을 찾지 못했습니다.")
        print()
        print("   디버그 명령:")
        print("   python ebs_downloader_clicker.py --list-windows")
        return False

    time.sleep(1.0)

    print("[CLICK] '다운로드 실행' 버튼 클릭...")
    success = click_download_button_in_window(win, dry_run=dry_run, debug=debug)

    if success:
        print("[OK] 클릭 완료. 다운로드가 시작되었는지 확인하세요.")
    return success


def list_all_visible_windows():
    """디버그용: 보이는 모든 창 목록"""
    if not HAS_PYGETWINDOW:
        print("pygetwindow 미설치")
        return

    print("=" * 100)
    print("현재 보이는 모든 창 목록 (멀티모니터 좌표 포함):")
    print("=" * 100)
    print(f"{'IDX':>4} {'TITLE':<60} {'SIZE':<12} {'POSITION':<20}")
    print("-" * 100)

    try:
        for i, win in enumerate(gw.getAllWindows()):
            if not win.visible or win.width < 50:
                continue
            title = (win.title or "(제목 없음)")[:58]
            size = f"{win.width}x{win.height}"
            pos = f"({win.left},{win.top})"

            marker = ""
            title_check = (win.title or "").lower()
            if any(kw.lower() in title_check for kw in STRONG_KEYWORDS):
                if not is_excluded_window(win.title or ""):
                    marker = " ← EBS Downloader 후보"

            print(f"{i:>4} {title:<60} {size:<12} {pos:<20}{marker}")
    except Exception as e:
        print(f"오류: {e}")
    print("=" * 100)


def diagnose_environment():
    """환경 진단: 화면 크기, DPI, 마우스 위치"""
    print("=" * 80)
    print("환경 진단")
    print("=" * 80)

    # 가상 화면 크기 (멀티모니터 전체)
    try:
        SM_XVIRTUALSCREEN = 76
        SM_YVIRTUALSCREEN = 77
        SM_CXVIRTUALSCREEN = 78
        SM_CYVIRTUALSCREEN = 79

        gsm = ctypes.windll.user32.GetSystemMetrics
        vx = gsm(SM_XVIRTUALSCREEN)
        vy = gsm(SM_YVIRTUALSCREEN)
        vw = gsm(SM_CXVIRTUALSCREEN)
        vh = gsm(SM_CYVIRTUALSCREEN)
        print(f"가상 화면 (멀티모니터 전체): ({vx},{vy}) {vw}x{vh}")
    except Exception as e:
        print(f"가상 화면 조회 실패: {e}")

    # 주 모니터 크기
    try:
        SM_CXSCREEN = 0
        SM_CYSCREEN = 1
        pw = ctypes.windll.user32.GetSystemMetrics(SM_CXSCREEN)
        ph = ctypes.windll.user32.GetSystemMetrics(SM_CYSCREEN)
        print(f"주 모니터: {pw}x{ph}")
    except Exception as e:
        print(f"주 모니터 조회 실패: {e}")

    # 현재 마우스 위치
    try:
        pos = win_get_cursor_pos()
        print(f"현재 마우스 위치: {pos}")
    except Exception as e:
        print(f"마우스 위치 조회 실패: {e}")

    print("=" * 80)


# ==============================================================================
# 단독 실행
# ==============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="EBS Downloader '다운로드 실행' 자동 클릭 (멀티모니터 + DPI 대응)"
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="마우스만 이동하고 클릭하지 않음")
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--list-windows", action="store_true")
    parser.add_argument("--diagnose", action="store_true",
                        help="환경 진단 (화면 크기, 마우스 위치)")
    args = parser.parse_args()

    if args.diagnose:
        diagnose_environment()
        sys.exit(0)

    if args.list_windows:
        list_all_visible_windows()
        sys.exit(0)

    success = click_download_button(
        timeout=args.timeout,
        dry_run=args.dry_run,
        debug=args.debug,
    )
    sys.exit(0 if success else 1)
