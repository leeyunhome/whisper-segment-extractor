"""
EBS 자동 다운로드 (Playwright + .env + PyAutoGUI 통합).

전략:
  1. 회차 검색 (searchKeywordAjax + goSearch)
  2. 회차마다 MP3 버튼 실제 클릭 → EBS Downloader 큐에 누적
  3. 모두 큐에 추가 후 '다운로드 실행' 버튼 1회 자동 클릭
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Optional

try:
    from playwright.sync_api import (
        sync_playwright,
        TimeoutError as PlaywrightTimeoutError,
        Dialog,
        Page,
        BrowserContext,
    )
except ImportError:
    print("[ERROR] playwright 미설치: pip install playwright python-dotenv pyautogui")
    print("   playwright install chromium")
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("[ERROR] python-dotenv 미설치")
    sys.exit(1)

from src.config import (
    EBS_MAIN_URL, EBS_REPLAY_URL, ENV_FILE, EPISODE_INFO_DIR,
    PLAYWRIGHT_PROFILE_DIR, DEFAULT_TIMEOUT_MS, MAX_PAGES_FALLBACK,
)
from src.episode_info import parse_episode_info, SCRIPT_LIST_EPISODES


# ==============================================================================
# 자격증명
# ==============================================================================

def load_credentials() -> tuple:
    if not ENV_FILE.exists():
        print(f"[ERROR] .env 없음: {ENV_FILE}")
        sys.exit(1)

    load_dotenv(ENV_FILE)
    username = os.getenv("EBS_USERNAME", "").strip()
    password = os.getenv("EBS_PASSWORD", "").strip()

    if not username or not password:
        print("[ERROR] .env 에 EBS_USERNAME/EBS_PASSWORD 누락")
        sys.exit(1)

    if username == "your_ebs_username_here" or password == "your_ebs_password_here":
        print("[ERROR] .env 의 값이 예시 그대로입니다.")
        sys.exit(1)

    print(f"[OK] .env 로드 (사용자: {username})")
    return username, password


# ==============================================================================
# 회차 인자 파싱
# ==============================================================================

def parse_episode_arg(arg: str) -> list:
    """
    "2707"      -> [2707]
    "2658-2661" -> [2658, 2659, 2660, 2661]
    "2700,2705" -> [2700, 2705]
    "2658-2661,2707" -> [2658, 2659, 2660, 2661, 2707]
    """
    episodes = set()
    for part in arg.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            try:
                start, end = part.split('-', 1)
                a, b = int(start), int(end)
                if a > b:
                    a, b = b, a
                episodes.update(range(a, b + 1))
            except ValueError:
                print(f"[ERROR] 잘못된 범위: '{part}'")
                sys.exit(1)
        else:
            try:
                episodes.add(int(part))
            except ValueError:
                print(f"[ERROR] 잘못된 회차: '{part}'")
                sys.exit(1)
    return sorted(episodes)


# ==============================================================================
# 로그인
# ==============================================================================

def is_logged_in(page: Page) -> bool:
    try:
        content = page.content()
        return "로그아웃" in content and "마이페이지" in content
    except Exception:
        return False


def click_login_link(page: Page) -> bool:
    for get_loc in [
        lambda: page.get_by_role("link", name="로그인").first,
        lambda: page.locator("a:has-text('로그인')").first,
    ]:
        try:
            loc = get_loc()
            loc.wait_for(state="visible", timeout=3000)
            loc.click()
            return True
        except Exception:
            continue
    return False


def perform_ebs_login(page: Page, username: str, password: str) -> bool:
    print("\n[LOGIN] EBS 자동 로그인...")

    if "login" not in page.url.lower():
        click_login_link(page)
        page.wait_for_load_state("domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
        page.wait_for_timeout(1000)

    # ID 입력란
    id_loc = None
    for get_loc in [
        lambda: page.get_by_placeholder("아이디").first,
        lambda: page.locator("input#userId, input#user_id, input#id, input#username").first,
        lambda: page.locator("input[name='userId'], input[name='user_id'], input[name='id']").first,
        lambda: page.locator("input[type='text']:visible").first,
    ]:
        try:
            loc = get_loc()
            loc.wait_for(state="visible", timeout=3000)
            id_loc = loc
            break
        except Exception:
            continue

    if not id_loc:
        print("[ERROR] ID 입력란 못 찾음")
        return False

    # PW 입력란
    pw_loc = None
    try:
        loc = page.locator("input[type='password']:visible").first
        loc.wait_for(state="visible", timeout=3000)
        pw_loc = loc
    except Exception:
        print("[ERROR] PW 입력란 못 찾음")
        return False

    id_loc.fill(username)
    pw_loc.fill(password)

    # 제출
    submitted = False
    for get_loc in [
        lambda: page.get_by_role("button", name="로그인").first,
        lambda: page.locator("button:has-text('로그인'):visible").first,
        lambda: page.locator("input[type='submit']:visible").first,
        lambda: page.locator("button[type='submit']:visible").first,
    ]:
        try:
            loc = get_loc()
            loc.wait_for(state="visible", timeout=2000)
            loc.click()
            submitted = True
            break
        except Exception:
            continue

    if not submitted:
        pw_loc.press("Enter")

    page.wait_for_load_state("domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
    page.wait_for_timeout(2000)

    if is_logged_in(page):
        print("[OK] 로그인 성공\n")
        return True

    print("[WAIT] 추가 인증 가능. 60초 대기...")
    for _ in range(30):
        time.sleep(2)
        if is_logged_in(page):
            print("[OK] 로그인 감지\n")
            return True

    print("[ERROR] 로그인 실패")
    return False


# ==============================================================================
# 회차 검색
# ==============================================================================

def get_current_page_episodes(page: Page) -> list:
    raw = page.evaluate(SCRIPT_LIST_EPISODES)
    result = []
    for item in raw:
        info = parse_episode_info(item.get('titleText', ''))
        if info and 'episode' in info:
            info['lectId'] = item.get('lectId')
            info['raw_title'] = item.get('titleText', '')
            result.append(info)
    return result


def search_episode(page: Page, episode_num: int) -> Optional[dict]:
    """검색창에 회차 번호 입력 + goSearch() -> 정확 매칭만 반환"""
    print(f"   [SEARCH] 회차 {episode_num} 검색...")

    js = """
    (() => {
        const input = document.getElementById('searchKeywordAjax');
        if (!input) return { error: 'no input' };
        input.value = '__EPNUM__';
        if (typeof goSearch === 'function') { goSearch(); return { ok: true }; }
        return { error: 'no goSearch' };
    })()
    """.replace("__EPNUM__", str(episode_num))
    result = page.evaluate(js)
    if not result.get('ok'):
        print(f"   [WARN] 검색 실패: {result.get('error')}")
        return None

    page.wait_for_timeout(2500)

    episodes = get_current_page_episodes(page)
    if not episodes:
        return None

    # 정확 매칭만
    for ep in episodes:
        if ep.get('episode') == episode_num:
            print(f"   [FOUND] {episode_num}: {ep.get('subtitle', '')}")
            return ep

    print(f"   [WARN] {episode_num} 정확 매칭 실패. 검색 결과 {len(episodes)}개")
    return None


def find_episodes_in_pages(page: Page, target_episodes: list) -> dict:
    """검색 우선, 페이지네이션 fallback"""
    found = {}
    target_set = set(target_episodes)

    print(f"\n[SEARCH] 회차 검색 시작 (목표: {sorted(target_set)})")

    # 1차: 각 회차 검색
    for ep_num in sorted(target_set):
        info = search_episode(page, ep_num)
        if info:
            found[ep_num] = info
        page.wait_for_timeout(500)

    # 2차: 페이지네이션 fallback
    missing = target_set - set(found.keys())
    if missing:
        print(f"\n   [FALLBACK] 페이지네이션으로 재시도: {sorted(missing)}")

        try:
            page.evaluate("""
                (() => {
                    const input = document.getElementById('searchKeywordAjax');
                    if (input) input.value = '';
                    if (typeof goSearch === 'function') goSearch();
                })()
            """)
            page.wait_for_timeout(2000)
        except Exception:
            pass

        page_num = 1
        while page_num <= MAX_PAGES_FALLBACK and missing:
            if page_num > 1:
                print(f"   페이지 {page_num} 이동...")
                try:
                    page.evaluate(f"goPage({page_num})")
                    page.wait_for_timeout(2000)
                except Exception as e:
                    print(f"   [WARN] 페이지 이동 실패: {e}")
                    break

            episodes = get_current_page_episodes(page)
            if not episodes:
                break

            page_min = min(e['episode'] for e in episodes)
            page_max = max(e['episode'] for e in episodes)
            print(f"   페이지 {page_num}: {page_max}~{page_min}")

            for ep in episodes:
                num = ep['episode']
                if num in missing:
                    found[num] = ep
                    missing.discard(num)
                    print(f"   [FOUND] {num}: {ep.get('subtitle', '')}")

            if not missing or page_min < min(target_set):
                break
            page_num += 1

    if missing:
        print(f"   [WARN] 매칭 실패: {sorted(missing)}")

    return found


# ==============================================================================
# 다운로드
# ==============================================================================

def save_episode_info(info: dict):
    EPISODE_INFO_DIR.mkdir(exist_ok=True)
    lect_id = info.get('lectId')
    if not lect_id:
        return
    path = EPISODE_INFO_DIR / f"{lect_id}.json"
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)


def trigger_download(page: Page, ep_info: dict) -> bool:
    """검색 + MP3 버튼 클릭 (실제 클릭이라야 큐에 쌓임)"""
    lect_id = ep_info['lectId']
    ep_num = ep_info['episode']
    subtitle = ep_info.get('subtitle', '')

    print(f"\n[QUEUE] {ep_num}회: {subtitle}")
    print(f"        lectId: {lect_id}")

    save_episode_info(ep_info)

    # 검색
    print(f"   [SEARCH] 회차 {ep_num} 검색...")
    try:
        js = """
        (() => {
            const input = document.getElementById('searchKeywordAjax');
            if (input) {
                input.value = '__EPNUM__';
                if (typeof goSearch === 'function') goSearch();
            }
        })()
        """.replace("__EPNUM__", str(ep_num))
        page.evaluate(js)
    except Exception as e:
        print(f"   [ERROR] 검색 실패: {e}")
        return False

    page.wait_for_timeout(2000)

    # MP3 버튼 실제 클릭 (lectId 매칭)
    # f-string + backslash escape 회피: 변수로 분리 후 문자열 연결
    onclick_substr = "downloadMultiFile('" + str(lect_id) + "'"
    selector = 'div.icon_mp3 > a[onclick*="' + onclick_substr + '"]'
    print(f"   [CLICK] MP3 버튼...")

    clicked = False
    try:
        button = page.locator(selector).first
        button.wait_for(state="visible", timeout=5000)
        button.click()
        clicked = True
        print(f"   [OK] 큐 추가됨")
    except PlaywrightTimeoutError:
        print(f"   [WARN] 정확한 셀렉터 실패, fallback 시도...")
    except Exception as e:
        print(f"   [WARN] 클릭 실패: {e}, fallback 시도...")

    # Fallback: 모든 다운로드 버튼 검사
    if not clicked:
        try:
            buttons = page.locator("div.icon_mp3 > a[onclick*='downloadMultiFile']").all()
            quoted_single = "'" + str(lect_id) + "'"
            quoted_double = '"' + str(lect_id) + '"'
            for btn in buttons:
                onclick = btn.get_attribute("onclick") or ""
                if quoted_single in onclick or quoted_double in onclick:
                    btn.click()
                    clicked = True
                    print(f"   [OK] 큐 추가됨 (fallback)")
                    break
            if not clicked:
                print(f"   [ERROR] lectId {lect_id} MP3 버튼 못 찾음")
                return False
        except Exception as e:
            print(f"   [ERROR] fallback 실패: {e}")
            return False

    page.wait_for_timeout(1500)
    return True


def execute_download_queue() -> bool:
    """EBS Downloader '다운로드 실행' 버튼 1회 클릭 (최대 3회 재시도)"""
    print("\n[EXECUTE] EBS Downloader '다운로드 실행' 클릭...")

    try:
        from src.downloader_clicker import click_download_button
    except ImportError:
        print("[WARN] downloader_clicker 없음. 수동 클릭 필요.")
        return False

    for attempt in range(1, 4):
        if attempt > 1:
            print(f"\n[RETRY] {attempt}/3...")
            time.sleep(2)
        try:
            if click_download_button(timeout=30.0):
                return True
        except Exception as e:
            print(f"[WARN] 시도 {attempt} 실패: {e}")

    print("[ERROR] 클릭 3회 실패. 수동으로 눌러주세요.")
    return False


def setup_dialog_handler(page: Page):
    def on_dialog(dialog: Dialog):
        print(f"[DIALOG] 자동 수락: {dialog.message[:60]!r}")
        try:
            dialog.accept()
        except Exception as e:
            print(f"   수락 실패: {e}")
    page.on("dialog", on_dialog)


# ==============================================================================
# 메인 흐름
# ==============================================================================

def run_download_flow(page: Page, username: str, password: str,
                      episodes: list = None, use_clicker: bool = True) -> bool:
    print(f"\n[NAV] 메인 페이지...")
    page.goto(EBS_MAIN_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)

    if not is_logged_in(page):
        if not perform_ebs_login(page, username, password):
            return False
    else:
        print("[OK] 이미 로그인됨")

    print(f"\n[NAV] 다시보기 페이지...")
    page.goto(EBS_REPLAY_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    # 최신 1개
    if not episodes:
        print("\n[MODE] 최신 회차")
        eps = get_current_page_episodes(page)
        if not eps:
            print("[ERROR] 회차 목록 못 가져옴")
            return False
        if not trigger_download(page, eps[0]):
            return False

        page.wait_for_timeout(3000)
        if use_clicker:
            return execute_download_queue()
        return True

    # 지정 회차
    print(f"\n[MODE] 회차 지정: {episodes}")
    found = find_episodes_in_pages(page, episodes)
    if not found:
        print("[ERROR] 회차 하나도 못 찾음")
        return False

    print(f"\n{'='*80}")
    print(f"[QUEUE] EBS Downloader 큐에 일괄 추가 시작")
    print(f"{'='*80}")

    queued = 0
    sorted_eps = sorted(found.keys())
    for i, num in enumerate(sorted_eps, 1):
        print(f"\n>>> {i}/{len(sorted_eps)} <<<")
        if trigger_download(page, found[num]):
            queued += 1
        if i < len(sorted_eps):
            page.wait_for_timeout(800)

    print(f"\n{'='*80}")
    print(f"[QUEUE] {queued}/{len(sorted_eps)} 큐 추가 완료")
    print(f"{'='*80}")

    if queued == 0:
        return False

    print("\n[WAIT] 큐 안정 대기 (3초)...")
    page.wait_for_timeout(3000)

    if use_clicker:
        return execute_download_queue()

    print("\n[SKIP] --no-clicker: '다운로드 실행' 직접 누르세요.")
    return True


def run_codegen():
    cmd = [sys.executable, "-m", "playwright", "codegen", EBS_MAIN_URL]
    subprocess.run(cmd)


def main():
    parser = argparse.ArgumentParser(
        description="EBS 왕초보 영어 자동 다운로드",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python -m src.auto_download                       # 최신
  python -m src.auto_download --episode 2707        # 단일
  python -m src.auto_download --episode 2658-2661   # 범위
  python -m src.auto_download --episode 2700,2705   # 콤마
""",
    )
    parser.add_argument("--episode", type=str, default=None)
    parser.add_argument("--keep-open", action="store_true")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--slow-mo", type=int, default=0)
    parser.add_argument("--no-clicker", action="store_true")
    parser.add_argument("--codegen", action="store_true")
    args = parser.parse_args()

    if args.codegen:
        run_codegen()
        return

    target_episodes = None
    if args.episode:
        target_episodes = parse_episode_arg(args.episode)
        print(f"[INFO] 대상 회차: {target_episodes} ({len(target_episodes)}개)")

    username, password = load_credentials()

    PLAYWRIGHT_PROFILE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*80}")
    print(f"[START] EBS 자동 다운로드")
    print(f"{'='*80}")
    print(f"프로필: {PLAYWRIGHT_PROFILE_DIR}")
    if target_episodes:
        print(f"회차: {target_episodes}")
    else:
        print(f"회차: 최신 1개")
    print(f"{'='*80}\n")

    with sync_playwright() as p:
        try:
            chromium_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=ExternalProtocolDialog",
                "--disable-infobars",
            ]
            context: BrowserContext = p.chromium.launch_persistent_context(
                user_data_dir=str(PLAYWRIGHT_PROFILE_DIR),
                headless=args.headless,
                slow_mo=args.slow_mo,
                args=chromium_args,
                ignore_default_args=["--enable-automation"],
            )
        except Exception as e:
            print(f"[ERROR] 브라우저 실행 실패: {e}")
            sys.exit(1)

        context.set_default_timeout(DEFAULT_TIMEOUT_MS)
        page = context.pages[0] if context.pages else context.new_page()
        setup_dialog_handler(page)

        try:
            success = run_download_flow(
                page, username, password,
                episodes=target_episodes,
                use_clicker=not args.no_clicker,
            )

            if success:
                print("\n[OK] 다운로드 트리거 완료!")
            else:
                print("\n[ERROR] 다운로드 트리거 실패")
                if not args.keep_open:
                    sys.exit(1)
        finally:
            if args.keep_open:
                print("\n[KEEP-OPEN] 브라우저 유지. Ctrl+C")
                try:
                    while context.pages:
                        time.sleep(1)
                except KeyboardInterrupt:
                    pass
            try:
                context.close()
            except Exception:
                pass


if __name__ == "__main__":
    main()
