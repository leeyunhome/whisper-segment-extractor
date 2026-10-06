"""
매일 정기 실행용: EBS 새 회차 감지 및 자동 전사 파이프라인.

기능:
  1. output_mp3/ 에 저장된 로컬 회차 목록 파악
  2. Playwright(headless)로 EBS 웹사이트 최신 회차 목록 조회
  3. 미처리된 새 회차가 있으면 src.runner 호출하여 다운로드 및 전사 수행
  4. 처리 결과 로깅 및 Windows 시스템 알림(Toast) 전송
"""

import argparse
import datetime
import json
import logging
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Set, Optional

from src.config import (
    PROJECT_DIR,
    OUTPUT_MP3_DIR,
    EBS_REPLAY_URL,
    DEFAULT_MODEL,
    AVAILABLE_MODELS,
)
from src.episode_info import parse_episode_info, SCRIPT_LIST_EPISODES

LOGS_DIR = PROJECT_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)


def setup_logger() -> logging.Logger:
    today_str = datetime.date.today().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"cron_{today_str}.log"

    logger = logging.getLogger("EBS_Cron")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    # 콘솔 핸들러
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("[%(asctime)s] %(message)s", "%Y-%m-%d %H:%M:%S")
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # 파일 핸들러 (UTF-8)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger


def send_windows_toast(title: str, message: str):
    """PowerShell을 이용해 Windows 10/11 시스템 알림(Toast) 전송"""
    try:
        # 안전한 문자열 이스케이프
        clean_title = title.replace('"', '`"').replace("'", "''")
        clean_msg = message.replace('"', '`"').replace("'", "''")
        ps_cmd = f"""
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] > $null
$template = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
$textNodes = $template.GetElementsByTagName('text')
$textNodes.Item(0).AppendChild($template.CreateTextNode('{clean_title}')) > $null
$textNodes.Item(1).AppendChild($template.CreateTextNode('{clean_msg}')) > $null
$notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('EBS Whisper Extractor')
$notification = [Windows.UI.Notifications.ToastNotification]::new($template)
$notifier.Show($notification)
"""
        subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_cmd],
            capture_output=True,
            timeout=10,
        )
    except Exception:
        # 알림 실패는 전체 파이프라인에 영향을 주지 않음
        pass


def get_local_episodes() -> Set[int]:
    """output_mp3/ 에 이미 생성된 회차 번호 집합 반환"""
    if not OUTPUT_MP3_DIR.exists():
        return set()

    episodes = set()
    # *_player.json 또는 *.mp3 파일에서 회차 번호 추출
    for f in OUTPUT_MP3_DIR.glob("*_player.json"):
        m = re.match(r"^(\d+)_", f.name)
        if m:
            episodes.add(int(m.group(1)))
    return episodes


def get_web_episodes(max_pages: int = 2, logger: Optional[logging.Logger] = None) -> List[dict]:
    """Playwright(headless)로 EBS 다시보기 페이지에서 회차 목록 추출"""
    from playwright.sync_api import sync_playwright

    all_episodes = []
    seen_episodes = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--disable-infobars"],
        )
        page = browser.new_page()
        page.set_default_timeout(20000)

        for page_num in range(1, max_pages + 1):
            url = f"{EBS_REPLAY_URL}&page={page_num}"
            if logger:
                logger.info(f"[WEB] 회차 목록 페이지 로드 중 (p.{page_num})...")

            try:
                page.goto(url, wait_until="domcontentloaded")
                page.wait_for_timeout(2000)

                raw = page.evaluate(SCRIPT_LIST_EPISODES)
                page_episodes = []
                for item in raw:
                    info = parse_episode_info(item.get("titleText", ""))
                    if info and "episode" in info:
                        ep = info["episode"]
                        if ep not in seen_episodes:
                            seen_episodes.add(ep)
                            info["lectId"] = item.get("lectId")
                            page_episodes.append(info)

                all_episodes.extend(page_episodes)
                if not page_episodes:
                    break
            except Exception as e:
                if logger:
                    logger.warning(f"[WEB] p.{page_num} 로드 중 예외 발생: {e}")
                break

        browser.close()

    # 회차 번호 내림차순 정렬 (최신순)
    all_episodes.sort(key=lambda x: x["episode"], reverse=True)
    return all_episodes


def format_episodes_arg(episodes: List[int]) -> str:
    """[2784, 2785, 2786] -> '2784-2786' 또는 [2784, 2787] -> '2784,2787'"""
    if not episodes:
        return ""
    sorted_eps = sorted(list(set(episodes)))
    if len(sorted_eps) == 1:
        return str(sorted_eps[0])

    # 연속 구간 확인
    is_consecutive = all(
        sorted_eps[i] + 1 == sorted_eps[i + 1] for i in range(len(sorted_eps) - 1)
    )
    if is_consecutive:
        return f"{sorted_eps[0]}-{sorted_eps[-1]}"
    else:
        return ",".join(str(e) for e in sorted_eps)


def run_pipeline(episode_arg: str, model: str, device: Optional[str], logger: logging.Logger) -> bool:
    """src.runner 프로세스 실행"""
    cmd = [sys.executable, "-m", "src.runner", "--episode", episode_arg, "--model", model]
    if device:
        cmd.extend(["--device", device])

    logger.info(f"[EXEC] 파이프라인 실행: {' '.join(cmd[1:])}")
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}

    res = subprocess.run(cmd, cwd=PROJECT_DIR, env=env)
    return res.returncode == 0


def main():
    parser = argparse.ArgumentParser(description="EBS 새 회차 확인 및 자동 전사 스케줄러")
    parser.add_argument("--max-batch", type=int, default=3, help="한 번에 처리할 최대 회차 수 (기본: 3)")
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL, choices=AVAILABLE_MODELS)
    parser.add_argument("--device", type=str, default=None, choices=["cuda", "cpu", None])
    parser.add_argument("--dry-run", action="store_true", help="실제 전사 실행 없이 확인만 수행")
    parser.add_argument("--force", action="store_true", help="새 회차가 없어도 최신 1개 강제 실행")
    parser.add_argument("--no-notify", action="store_true", help="Windows 토스트 알림 끄기")
    args = parser.parse_args()

    logger = setup_logger()
    logger.info("=" * 60)
    logger.info("[CRON] EBS 자동 전사 스케줄러 점검 시작")
    logger.info("=" * 60)

    # 1. 로컬 처리 완료 회차 확인
    local_eps = get_local_episodes()
    local_max = max(local_eps) if local_eps else 0
    logger.info(f"[LOCAL] 저장된 회차 수: {len(local_eps)}개 (로컬 최신: {local_max}회)")

    # 2. 웹사이트 최신 회차 조회
    try:
        web_eps = get_web_episodes(max_pages=2, logger=logger)
    except Exception as e:
        logger.error(f"[ERROR] 웹사이트 회차 조회 실패: {e}")
        if not args.no_notify:
            send_windows_toast("EBS 자동 전사 실패", f"웹사이트 회차 조회 중 오류 발생: {e}")
        sys.exit(1)

    if not web_eps:
        logger.warning("[WARN] 웹에서 회차 정보를 찾을 수 없습니다.")
        sys.exit(0)

    web_max = web_eps[0]["episode"]
    logger.info(f"[WEB] 웹사이트 최신 회차: {web_max}회 ({web_eps[0].get('air_date', '')} '{web_eps[0].get('subtitle', '')}')")

    # 3. 새 회차 여부 판단 및 대상 선정
    if web_max <= local_max and not args.force:
        logger.info(f"[OK] 새 회차가 없습니다. 이미 최신 회차까지 처리 완료되었습니다. (로컬 최신: {local_max}회)")
        logger.info("[DONE] 스케줄러 점검 완료 (스킵)")
        return

    if args.force and web_max <= local_max:
        logger.info(f"[FORCE] 강제 실행 옵션: 최신 회차({web_max}회) 재처리")
        targets = [web_max]
    else:
        # local_max + 1 부터 web_max 까지 순차적으로 최대 max_batch 개 선택 (누락 방지)
        next_start = local_max + 1
        end_ep = min(next_start + args.max_batch - 1, web_max)
        targets = list(range(next_start, end_ep + 1))

        # 혹시 중간에 이미 존재하는 회차가 섞여있다면 필터링
        targets = [ep for ep in targets if ep not in local_eps]
        if not targets:
            # 만약 위 범위에 없으면 web_eps 중 미처리된 회차 중 가장 오래된 것들 선택
            unprocessed = [ep["episode"] for ep in web_eps if ep["episode"] not in local_eps]
            unprocessed.sort()
            targets = unprocessed[: args.max_batch]

        gap = web_max - local_max
        if gap > args.max_batch:
            logger.info(
                f"[INFO] 웹 최신({web_max}회)까지 {gap}개 회차가 남아있어, 안전을 위해 순서대로 {len(targets)}개만 우선 처리합니다: {targets}"
            )
        else:
            logger.info(f"[NEW] 새 회차 발견! 처리 대상: {targets} (총 {len(targets)}개)")

    ep_arg = format_episodes_arg(targets)

    if args.dry_run:
        logger.info(f"[DRY-RUN] 실제 실행 건너뜀 (인자: --episode {ep_arg})")
        return

    # 4. 파이프라인 실행
    start_time = time.time()
    if not args.no_notify:
        send_windows_toast(
            "EBS 자동 전사 시작",
            f"새 회차({ep_arg}) 다운로드 및 Whisper 전사를 시작합니다.",
        )

    success = run_pipeline(ep_arg, args.model, args.device, logger)
    elapsed = int(time.time() - start_time)
    minutes, seconds = divmod(elapsed, 60)

    if success:
        msg = f"새 회차({ep_arg}) 전사 및 배포가 완료되었습니다. (소요: {minutes}분 {seconds}초)"
        logger.info(f"✅ {msg}")
        if not args.no_notify:
            send_windows_toast("EBS 자동 전사 완료", msg)
    else:
        msg = f"회차({ep_arg}) 처리 중 오류가 발생했습니다. 로그를 확인하세요."
        logger.error(f"❌ {msg}")
        if not args.no_notify:
            send_windows_toast("EBS 자동 전사 실패", msg)
        sys.exit(1)


if __name__ == "__main__":
    main()
