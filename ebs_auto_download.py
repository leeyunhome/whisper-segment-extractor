"""
EBS 자동 다운로드 스크립트 (Playwright + .env + 회차 범위 지원)

기능:
  - 최신 회차 자동 다운로드 (기본)
  - 특정 회차 다운로드: --episode 2707
  - 회차 범위 다운로드: --episode 2658-2661
  - 회차 정보를 .episode_info/ 폴더에 저장 (파일명 매핑용)

요구사항:
    pip install playwright python-dotenv pyautogui
    playwright install chromium
"""

import argparse
import json
import os
import re
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
    print("[ERROR] playwright 가 설치되지 않았습니다.")
    print("    pip install playwright python-dotenv pyautogui")
    print("    playwright install chromium")
    sys.exit(1)

try:
    from dotenv import load_dotenv
except ImportError:
    print("[ERROR] python-dotenv 가 설치되지 않았습니다.")
    sys.exit(1)

from ebs_episode_info import (
    parse_episode_info,
    make_safe_filename,
    SCRIPT_LIST_EPISODES,
)


# ==============================================================================
# 설정
# ==============================================================================

EBS_MAIN_URL = "https://home.ebse.co.kr/beginnerenglish/main"
EBS_REPLAY_URL = (
    "https://home.ebse.co.kr/beginnerenglish/replay/3/list"
    "?courseId=ER2016G0BEG01ZZ&stepId=ET2016G0BEG0101"
)

PROJECT_DIR = Path(__file__).parent.resolve()
USER_DATA_DIR = PROJECT_DIR / ".playwright_profile"
ENV_FILE = PROJECT_DIR / ".env"
EPISODE_INFO_DIR = PROJECT_DIR / ".episode_info"  # 회차 정보 저장

DEFAULT_TIMEOUT_MS = 15000

# 한 페이지에 몇 개 회차가 있는지 (페이지 계산용)
EPISODES_PER_PAGE = 20

# 다운로드 사이 대기 시간 (서버 부하 + EBS Downloader 큐 처리)
DOWNLOAD_INTERVAL_SEC = 30


# ==============================================================================
# .env 로드
# ==============================================================================

def load_credentials() -> tuple:
    if not ENV_FILE.exists():
        print(f"[ERROR] .env 파일이 없습니다: {ENV_FILE}")
        print(f"  cd {PROJECT_DIR}")
        print(f"  copy .env.example .env")
        print(f"  notepad .env")
        sys.exit(1)

    load_dotenv(ENV_FILE)

    username = os.getenv("EBS_USERNAME", "").strip()
    password = os.getenv("EBS_PASSWORD", "").strip()

    if not username or not password:
        print("[ERROR] .env 에서 EBS_USERNAME 또는 EBS_PASSWORD 를 찾지 못했습니다.")
        sys.exit(1)

    if username == "your_ebs_username_here" or password == "your_ebs_password_here":
        print("[ERROR] .env 의 값이 예시 그대로입니다.")
        sys.exit(1)

    print(f"[OK] .env 로드 완료 (사용자: {username})")
    return username, password


# ==============================================================================
# 에피소드 파라미터 파싱
# ==============================================================================

def parse_episode_arg(arg: str) -> list:
    """
    --episode 인자 파싱.

    형식:
      "2707"       → [2707]
      "2658-2661"  → [2658, 2659, 2660, 2661]
      "2700,2705"  → [2700, 2705]
      "2658-2661,2707"  → [2658, 2659, 2660, 2661, 2707]
    """
    episodes = set()

    for part in arg.split(','):
        part = part.strip()
        if not part:
            continue

        if '-' in part:
            try:
                start, end = part.split('-', 1)
                start_n = int(start.strip())
                end_n = int(end.strip())
                if start_n > end_n:
                    start_n, end_n = end_n, start_n
                episodes.update(range(start_n, end_n + 1))
            except ValueError:
                print(f"[ERROR] 잘못된 범위 형식: '{part}'")
                sys.exit(1)
        else:
            try:
                episodes.add(int(part))
            except ValueError:
                print(f"[ERROR] 잘못된 회차 번호: '{part}'")
                sys.exit(1)

    return sorted(episodes)


# ==============================================================================
# 로그인
# ==============================================================================

def is_logged_in(page: Page) -> bool:
    try:
        content = page.content()
        return ("로그아웃" in content) and ("마이페이지" in content)
    except Exception:
        return False


def click_login_link(page: Page) -> bool:
    for get_locator in [
        lambda: page.get_by_role("link", name="로그인").first,
        lambda: page.locator("a:has-text('로그인')").first,
    ]:
        try:
            loc = get_locator()
            loc.wait_for(state="visible", timeout=3000)
            loc.click()
            return True
        except (PlaywrightTimeoutError, Exception):
            continue
    return False


def perform_ebs_login(page: Page, username: str, password: str) -> bool:
    print("\n[LOGIN] EBS 자동 로그인 시도...")

    if "login" not in page.url.lower():
        click_login_link(page)
        page.wait_for_load_state("domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
        page.wait_for_timeout(1000)

    print("   ID 입력란 검색...")
    id_locator = None
    for get_locator in [
        lambda: page.get_by_placeholder("아이디").first,
        lambda: page.locator("input#userId, input#user_id, input#id, input#username").first,
        lambda: page.locator("input[name='userId'], input[name='user_id'], input[name='id'], input[name='username']").first,
        lambda: page.locator("input[type='text']:visible").first,
    ]:
        try:
            loc = get_locator()
            loc.wait_for(state="visible", timeout=3000)
            id_locator = loc
            break
        except (PlaywrightTimeoutError, Exception):
            continue

    if not id_locator:
        print("[ERROR] 아이디 입력란을 찾지 못했습니다.")
        return False

    print("   PW 입력란 검색...")
    pw_locator = None
    for get_locator in [
        lambda: page.locator("input[type='password']:visible").first,
    ]:
        try:
            loc = get_locator()
            loc.wait_for(state="visible", timeout=3000)
            pw_locator = loc
            break
        except (PlaywrightTimeoutError, Exception):
            continue

    if not pw_locator:
        print("[ERROR] 비밀번호 입력란을 찾지 못했습니다.")
        return False

    print("   계정 정보 입력...")
    id_locator.fill(username)
    pw_locator.fill(password)

    print("   로그인 제출...")
    submitted = False
    for get_locator in [
        lambda: page.get_by_role("button", name="로그인").first,
        lambda: page.locator("button:has-text('로그인'):visible").first,
        lambda: page.locator("input[type='submit']:visible").first,
        lambda: page.locator("button[type='submit']:visible").first,
    ]:
        try:
            loc = get_locator()
            loc.wait_for(state="visible", timeout=2000)
            loc.click()
            submitted = True
            break
        except (PlaywrightTimeoutError, Exception):
            continue

    if not submitted:
        pw_locator.press("Enter")

    page.wait_for_load_state("domcontentloaded", timeout=DEFAULT_TIMEOUT_MS)
    page.wait_for_timeout(2000)

    if is_logged_in(page):
        print("[OK] 로그인 성공!\n")
        return True

    print("[WAIT] 추가 인증 가능. 60초 대기...")
    for i in range(30):
        time.sleep(2)
        if is_logged_in(page):
            print("[OK] 로그인 감지!\n")
            return True

    print("[ERROR] 로그인 실패")
    return False


# ==============================================================================
# 회차 목록 + 검색 (검색 우선 → 페이지네이션 fallback)
# ==============================================================================

def get_current_page_episodes(page: Page) -> list:
    """현재 페이지의 회차 목록 추출 (파싱된 형태로)"""
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
    """
    검색창에 회차 번호를 입력하고 goSearch() 호출.
    검색 결과에서 정확한 회차 찾기.

    검색창 특성:
      - input#searchKeywordAjax 에 값 입력
      - goSearch() 함수 호출
      - '2658' 결과에 '제2658회 뿐 아니라 제2658X회' 같은 부분 매칭도 나올 수 있음
        → 정확한 회차 매칭 필요
    """
    print(f"   [SEARCH] 회차 {episode_num} 검색...")

    # 검색 실행
    js = f"""
    (() => {{
        const input = document.getElementById('searchKeywordAjax');
        if (!input) return {{ error: 'searchKeywordAjax 없음' }};
        input.value = '{episode_num}';
        if (typeof goSearch === 'function') {{
            goSearch();
            return {{ ok: true }};
        }}
        return {{ error: 'goSearch 함수 없음' }};
    }})()
    """
    result = page.evaluate(js)
    if not result.get('ok'):
        print(f"   [WARN] 검색 실행 실패: {result.get('error')}")
        return None

    # AJAX 결과 로딩 대기
    page.wait_for_timeout(2500)

    # 결과 추출
    episodes = get_current_page_episodes(page)
    if not episodes:
        print(f"   [WARN] 검색 결과 없음")
        return None

    # 정확히 일치하는 회차만 채택 ('제2658회' === episode 2658)
    for ep in episodes:
        if ep.get('episode') == episode_num:
            print(f"   [FOUND] {episode_num}: {ep.get('subtitle', '')}")
            return ep

    # 정확 매칭 안 되면 접두어 매칭 결과 표시
    print(f"   [WARN] 회차 {episode_num} 정확 매칭 실패. 검색 결과 {len(episodes)}개:")
    for ep in episodes[:3]:
        print(f"           - {ep.get('episode')}: {ep.get('subtitle', '')}")
    return None


def find_episodes_in_pages(page: Page, target_episodes: list,
                          max_pages: int = 30) -> dict:
    """
    여러 회차를 찾는다. 검색 우선, 페이지네이션 fallback.

    전략:
      1. 각 회차에 대해 검색 시도 (가장 빠르고 안정적)
      2. 검색 실패 시 페이지네이션으로 fallback
    """
    found = {}
    target_set = set(target_episodes)

    print(f"\n[SEARCH] 회차 검색 시작 (목표: {sorted(target_set)})")

    # 전략 1: 각 회차에 대해 검색 시도
    for ep_num in sorted(target_set):
        info = search_episode(page, ep_num)
        if info:
            found[ep_num] = info
        # 검색 사이 짧은 대기 (서버 부하 방지)
        page.wait_for_timeout(500)

    # 전략 2: 검색으로 못 찾은 회차는 페이지네이션으로
    missing = target_set - set(found.keys())
    if missing:
        print(f"\n   [FALLBACK] 검색 실패 회차 페이지네이션으로 재시도: {sorted(missing)}")

        # 먼저 검색 초기화 (빈 값 으로 goSearch)
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
        while page_num <= max_pages and missing:
            if page_num > 1:
                print(f"   페이지 {page_num} 로 이동...")
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
            print(f"   페이지 {page_num}: 회차 {page_max} ~ {page_min}")

            for ep_info in episodes:
                ep_num = ep_info['episode']
                if ep_num in missing:
                    found[ep_num] = ep_info
                    missing.discard(ep_num)
                    print(f"   [FOUND] {ep_num}: {ep_info.get('subtitle', '')}")

            if not missing:
                break
            if page_min < min(target_set):
                break
            page_num += 1

    if missing:
        print(f"   [WARN] 최종적으로 매칭 못 한 회차: {sorted(missing)}")

    return found


# ==============================================================================
# 다운로드
# ==============================================================================

def save_episode_info(info: dict):
    """회차 정보를 .episode_info/ 에 JSON 으로 저장 (파일명 매핑용)"""
    EPISODE_INFO_DIR.mkdir(exist_ok=True)
    lect_id = info.get('lectId')
    if not lect_id:
        return

    info_path = EPISODE_INFO_DIR / f"{lect_id}.json"
    with open(info_path, 'w', encoding='utf-8') as f:
        json.dump(info, f, ensure_ascii=False, indent=2)


def trigger_download(page: Page, ep_info: dict) -> bool:
    """
    단일 회차 MP3 다운로드 트리거 (검색 + 실제 MP3 버튼 클릭).

    중요: downloadMultiFile() JS 함수 직접 호출이 아니라
    실제 MP3 버튼을 클릭해야 EBS Downloader 큐에 제대로 쌓인다.

    동작:
      1. 검색창에 회차 번호 입력 + goSearch()
      2. 해당 회차의 MP3 버튼 실제 클릭 (Playwright .click())
      3. EBS Downloader 가 큐에 자동 추가
    """
    lect_id = ep_info['lectId']
    ep_num = ep_info['episode']
    subtitle = ep_info.get('subtitle', '')

    print(f"\n[QUEUE] {ep_num}회: {subtitle}")
    print(f"        lectId: {lect_id}")

    # 회차 정보 저장 (파일명 매핑용)
    save_episode_info(ep_info)

    # 1. 검색으로 해당 회차 표시
    print(f"   [SEARCH] 회차 {ep_num} 검색...")
    try:
        page.evaluate(f"""
        (() => {{
            const input = document.getElementById('searchKeywordAjax');
            if (input) {{
                input.value = '{ep_num}';
                if (typeof goSearch === 'function') goSearch();
            }}
        }})()
        """)
    except Exception as e:
        print(f"   [ERROR] 검색 실패: {e}")
        return False

    # AJAX 결과 로딩 대기
    page.wait_for_timeout(2000)

    # 2. 해당 lectId 의 MP3 버튼 실제 클릭
    #    (검색 결과에 키워드가 부분 매칭되어 여러개 나올 수 있으므로
    #    onclick 쓰기에 정확한 lectId 가 들어있는 버튼만 골라서 클릭)
    selector = f'div.icon_mp3 > a[onclick*="downloadMultiFile(\'{lect_id}\'"]'
    print(f"   [CLICK] MP3 버튼 클릭...")
    try:
        button = page.locator(selector).first
        button.wait_for(state="visible", timeout=5000)
        button.click()
        print(f"   [OK] 큐에 추가됨")
    except PlaywrightTimeoutError:
        # fallback: 해당 lectId 가 포함된 onclick 각도가 다를 수 있음
        try:
            print(f"   [WARN] 정확한 셔렉터 실패, fallback 시도...")
            buttons = page.locator("div.icon_mp3 > a[onclick*='downloadMultiFile']").all()
            for btn in buttons:
                onclick = btn.get_attribute("onclick") or ""
                if f"'{lect_id}'" in onclick or f'"{lect_id}"' in onclick:
                    btn.click()
                    print(f"   [OK] 큐에 추가됨 (fallback)")
                    break
            else:
                print(f"   [ERROR] lectId {lect_id} 에 해당하는 MP3 버튼을 못 찾음")
                return False
        except Exception as e:
            print(f"   [ERROR] fallback 실패: {e}")
            return False
    except Exception as e:
        print(f"   [ERROR] 클릭 실패: {e}")
        return False

    # 3. EBS Downloader 가 큐에 추가할 시간
    page.wait_for_timeout(1500)

    return True


def setup_dialog_handler(page: Page):
    """JS 다이얼로그 자동 수락"""
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
                      episodes: list = None,
                      use_clicker: bool = True) -> bool:
    """
    전체 다운로드 흐름.

    전략 (EBS Downloader 의 큐 기능 활용):
      1. 모든 회차를 downloadMultiFile() 로 큐에 쌓기 (빠름)
      2. 큐 쌓기가 끝난 후 '다운로드 실행' 버튼 단 1회 클릭
      3. EBS Downloader 가 자동으로 큐의 모든 파일 순차 다운로드

    이전 방식(회차마다 클릭 + 30초 대기) 대비 장점:
      - 클릭 실패 위험이 N번 → 1번으로 감소
      - 대기 시간 제거
      - '항목 없음' 팭업 회피
    """
    # 1. 메인 페이지 + 로그인
    print(f"\n[NAV] 메인 페이지 이동")
    page.goto(EBS_MAIN_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(1500)

    if not is_logged_in(page):
        if not perform_ebs_login(page, username, password):
            return False
    else:
        print("[OK] 이미 로그인됨")

    # 2. 다시보기 페이지
    print(f"\n[NAV] 다시보기 페이지 이동")
    page.goto(EBS_REPLAY_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(2000)

    # 3a. 회차 미지정: 최신 1개
    if not episodes:
        print("\n[MODE] 최신 회차 다운로드")
        episodes_data = get_current_page_episodes(page)
        if not episodes_data:
            print("[ERROR] 회차 목록을 가져오지 못했습니다.")
            return False
        latest = episodes_data[0]

        # 큐에 추가
        if not trigger_download(page, latest):
            return False

        # 큐 안정 대기 후 클릭
        print("\n[WAIT] EBS Downloader 큐 안정 대기 (3초)...")
        page.wait_for_timeout(3000)

        if use_clicker:
            return execute_download_queue()
        return True

    # 3b. 회차 지정: 검색 + 일괄 큐 추가
    print(f"\n[MODE] 회차 지정 다운로드: {episodes}")
    found = find_episodes_in_pages(page, episodes)

    if not found:
        print("[ERROR] 지정한 회차를 하나도 찾지 못했습니다.")
        return False

    # 전략: 모든 회차를 큐에 동시에 추가
    print(f"\n{'='*80}")
    print(f"[QUEUE] EBS Downloader 큐에 일괄 추가 시작")
    print(f"{'='*80}")

    queued_count = 0
    sorted_episodes = sorted(found.keys())
    total = len(sorted_episodes)

    for i, ep_num in enumerate(sorted_episodes, 1):
        ep_info = found[ep_num]
        print(f"\n>>> {i}/{total} <<<")

        if trigger_download(page, ep_info):
            queued_count += 1

        # 큐 추가 사이 짧은 대기 (EBS Downloader 처리 시간)
        if i < total:
            page.wait_for_timeout(800)

    print(f"\n{'='*80}")
    print(f"[QUEUE] {queued_count}/{total} 회차 큐에 추가 완료")
    print(f"{'='*80}")

    if queued_count == 0:
        return False

    # 큐 안정화 대기
    print("\n[WAIT] EBS Downloader 큐 안정 대기 (3초)...")
    page.wait_for_timeout(3000)

    # '다운로드 실행' 버튼 단 1회 클릭
    if use_clicker:
        return execute_download_queue()
    else:
        print("\n[SKIP] --no-clicker: '다운로드 실행' 버튼을 직접 눌러주세요")

    return True


def execute_download_queue() -> bool:
    """
    EBS Downloader 의 '다운로드 실행' 버튼을 단 1회 클릭해 큐 전체를 실행.

    클릭 실패 시 N번이 아닌 1번만 실패해도 전체가 멈추므로
    재시도 로직을 넣는다 (최대 3회).
    """
    print("\n[EXECUTE] EBS Downloader '다운로드 실행' 버튼 클릭...")

    try:
        from ebs_downloader_clicker import click_download_button
    except ImportError:
        print("[WARN] ebs_downloader_clicker 모듈 없음. 수동 클릭 필요.")
        return False

    # 최대 3회 재시도
    for attempt in range(1, 4):
        if attempt > 1:
            print(f"\n[RETRY] 재시도 {attempt}/3...")
            time.sleep(2)

        try:
            ok = click_download_button(timeout=30.0)
            if ok:
                return True
        except Exception as e:
            print(f"[WARN] 클릭 시도 {attempt} 실패: {e}")

    print("[ERROR] '다운로드 실행' 버튼 클릭 실패 (3회 재시도)")
    print("        EBS Downloader 에서 직접 눌러주세요.")
    return False


def run_codegen():
    cmd = [sys.executable, "-m", "playwright", "codegen", EBS_MAIN_URL]
    subprocess.run(cmd)


# ==============================================================================
# 진입점
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="EBS 왕초보 영어 자동 다운로드 (회차 범위 지원)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python ebs_auto_download.py                       # 최신 회차
  python ebs_auto_download.py --episode 2707        # 2707회만
  python ebs_auto_download.py --episode 2658-2661   # 2658~2661회
  python ebs_auto_download.py --episode 2700,2705   # 2700, 2705회
  python ebs_auto_download.py --episode 2658-2661,2707  # 혼합
""",
    )
    parser.add_argument("--episode", type=str, default=None,
                        help="다운로드할 회차 (단일/범위/혼합). 미지정 시 최신.")
    parser.add_argument("--user-data-dir", type=str, default=str(USER_DATA_DIR))
    parser.add_argument("--keep-open", action="store_true")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--slow-mo", type=int, default=0)
    parser.add_argument("--no-clicker", action="store_true",
                        help="EBS Downloader 자동 클릭 끄기")
    parser.add_argument("--codegen", action="store_true")

    args = parser.parse_args()

    if args.codegen:
        run_codegen()
        return

    # 회차 인자 파싱
    target_episodes = None
    if args.episode:
        target_episodes = parse_episode_arg(args.episode)
        print(f"[INFO] 다운로드 대상 회차: {target_episodes} ({len(target_episodes)}개)")

    username, password = load_credentials()

    profile_dir = Path(args.user_data_dir).resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n{'='*80}")
    print(f"[START] EBS 자동 다운로드")
    print(f"{'='*80}")
    print(f"프로필 폴더 : {profile_dir}")
    if target_episodes:
        print(f"회차        : {target_episodes}")
    else:
        print(f"회차        : 최신 1개")
    print(f"{'='*80}\n")

    with sync_playwright() as p:
        try:
            chromium_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=ExternalProtocolDialog",
                "--disable-infobars",
            ]

            context: BrowserContext = p.chromium.launch_persistent_context(
                user_data_dir=str(profile_dir),
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
                print("\n[KEEP-OPEN] 브라우저 유지")
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
