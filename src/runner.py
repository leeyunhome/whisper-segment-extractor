"""
통합 실행: watcher 백그라운드 + auto_download 트리거.

사용:
  python -m src.runner                       # 최신 1개
  python -m src.runner --episode 2707        # 특정
  python -m src.runner --episode 2658-2661   # 범위
  python -m src.runner --model tiny          # 빠른 모델
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from threading import Thread
from typing import Optional

from src.config import PROJECT_DIR, DEFAULT_MODEL, AVAILABLE_MODELS


def run_watcher(model: str, max_files: int, device: Optional[str] = None,
                process_existing: bool = False):
    cmd = [sys.executable, "-m", "src.watcher", "--model", model]
    if device:
        cmd.extend(["--device", device])
    if max_files == 1:
        cmd.append("--once")
    elif max_files > 1:
        cmd.extend(["--max-files", str(max_files)])
    if process_existing:
        cmd.append("--process-existing")

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    print(f"[RUN] watcher: {' '.join(cmd[2:])}")
    global _watcher_proc
    _watcher_proc = subprocess.Popen(cmd, cwd=PROJECT_DIR, env=env)
    _watcher_proc.wait()


_watcher_proc: Optional[subprocess.Popen] = None


def stop_watcher():
    """다운로드 트리거 실패 시 무한 대기 방지를 위해 watcher 종료"""
    if _watcher_proc and _watcher_proc.poll() is None:
        print("[STOP] 다운로드 실패로 watcher 종료")
        _watcher_proc.terminate()


def run_downloader(episode: str = None) -> bool:
    cmd = [sys.executable, "-m", "src.auto_download"]
    if episode:
        cmd.extend(["--episode", episode])

    print(f"[RUN] auto_download: {' '.join(cmd[2:])}")
    return subprocess.run(cmd, cwd=PROJECT_DIR).returncode == 0


def count_episodes(episode_arg: str) -> int:
    if not episode_arg:
        return 1
    total = set()
    for part in episode_arg.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            try:
                a, b = part.split('-', 1)
                a, b = int(a), int(b)
                if a > b:
                    a, b = b, a
                total.update(range(a, b + 1))
            except ValueError:
                continue
        else:
            try:
                total.add(int(part))
            except ValueError:
                continue
    return len(total) or 1


    parser.add_argument("--episode", type=str, default=None)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL,
                       choices=AVAILABLE_MODELS)
    parser.add_argument("--device", type=str, default=None,
                       choices=["cuda", "cpu", None],
                       help="연산 디바이스 (도 안 주면 자동 감지)")
    parser.add_argument("--watch-first-delay", type=float, default=8.0)
    args = parser.parse_args()

    expected = count_episodes(args.episode)

    print(f"\n{'='*80}")
    print(f"[START] EBS 자동화 통합 실행")
    print(f"{'='*80}")
    if args.episode:
        print(f"회차: {args.episode} (총 {expected}개)")
    else:
        print(f"회차: 최신 1개")
    print(f"모델: {args.model}")
    if args.device:
        print(f"디바이스: {args.device}")
    else:
        print(f"디바이스: 자동 감지")
    print(f"{'='*80}\n")

    watcher_thread = Thread(
        target=run_watcher, args=(args.model, expected, args.device), daemon=False
    )
    watcher_thread.start()

    print(f"[WAIT] {args.watch_first_delay}초 후 다운로드 트리거...")
    time.sleep(args.watch_first_delay)

    run_downloader(args.episode)

    print("\n[WAIT] 다운로드 + 추출 처리 대기 중... (Ctrl+C 로 중단)")
    watcher_thread.join()

def sync_to_github_pages():
    """output_mp3/ 의 HTML 파일들을 ebs-learning(temp_repo)으로 복사 후 Push"""
    import shutil
    import subprocess
    from src.config import OUTPUT_MP3_DIR
    
    temp_repo = PROJECT_DIR / "temp_repo"
    if not temp_repo.exists():
        print("\n[SKIP] temp_repo 폴더가 없어 GitHub Pages 동기화를 건너뜁니다.")
        return

    print(f"\n{'='*80}")
    print(f"[SYNC] GitHub Pages 동기화 시작 (temp_repo)")
    print(f"{'='*80}")

    try:
        # 1. 파일 복사 (HTML + JSON)
        # player.html, index.html 및 회차별 데이터 json 파일들
        patterns = ["*.html", "*_player.json"]
        copied_count = 0
        
        for pattern in patterns:
            files = list(OUTPUT_MP3_DIR.glob(pattern))
            for f in files:
                shutil.copy2(f, temp_repo / f.name)
                copied_count += 1
        
        if copied_count == 0:
            print("   - 복사할 파일이 없습니다.")
            return

        print(f"   - {copied_count}개 파일 복사 완료 (HTML, JSON)")

        # 2. Git Commit & Push
        print("   - Git Push 중...")
        subprocess.run(["git", "add", "."], cwd=temp_repo, check=True, capture_output=True)
        
        # 변경 사항이 있는지 확인
        status = subprocess.run(["git", "status", "--porcelain"], cwd=temp_repo, check=True, capture_output=True, text=True)
        if not status.stdout.strip():
            print("   - 변경 사항이 없어 Push를 건너뜁니다.")
            return

        subprocess.run(["git", "commit", "-m", "Auto-update episodes from pipeline"], cwd=temp_repo, check=True, capture_output=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=temp_repo, check=True, capture_output=True)
        print("✅ GitHub Pages 업데이트 완료!")
        
    except Exception as e:
        print(f"❌ 동기화 실패: {e}")
    print(f"{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(
        description="EBS 자동 다운로드 + 추출 통합 실행"
    )
    parser.add_argument("--episode", type=str, default=None)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL,
                       choices=AVAILABLE_MODELS)
    parser.add_argument("--device", type=str, default=None,
                       choices=["cuda", "cpu", None],
                       help="연산 디바이스 (지정 안 하면 자동 감지)")
    parser.add_argument("--watch-first-delay", type=float, default=8.0)
    parser.add_argument("--process-existing", action="store_true",
                       help="감시 시작 시 이미 존재하는 파일도 처리")
    args = parser.parse_args()

    start_time = time.time()
    expected = count_episodes(args.episode)

    print(f"\n{'='*80}")
    print(f"[START] EBS 자동화 통합 실행")
    print(f"{'='*80}")
    if args.episode:
        print(f"회차: {args.episode} (총 {expected}개)")
    else:
        print(f"회차: 최신 1개")
    print(f"모델: {args.model}")
    if args.device:
        print(f"디바이스: {args.device}")
    else:
        print(f"디바이스: 자동 감지")
    print(f"시작 시간: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")
    print(f"{'='*80}\n")

    watcher_thread = Thread(
        target=run_watcher,
        args=(args.model, expected, args.device, args.process_existing),
        daemon=False,
    )
    watcher_thread.start()

    print(f"[WAIT] {args.watch_first_delay}초 후 다운로드 트리거...")
    time.sleep(args.watch_first_delay)

    if not run_downloader(args.episode):
        print("\n[ERROR] 다운로드 트리거 실패 - watcher를 종료합니다.")
        stop_watcher()
    else:
        print("\n[WAIT] 다운로드 + 추출 처리 대기 중... (Ctrl+C 로 중단)")
    watcher_thread.join()

    # R2 누락 파일 일괄 업로드 (watcher 업로드 실패 대비 안전망)
    try:
        import subprocess, sys
        r2_public_url = os.getenv("R2_PUBLIC_URL", "").rstrip("/")
        if r2_public_url:
            print(f"\n[R2] 누락 파일 최종 확인 중...")
            result = subprocess.run(
                [sys.executable, "tools/upload_to_r2.py", "--public-url", r2_public_url],
                cwd=PROJECT_DIR, capture_output=True, text=True, encoding="utf-8", errors="replace"
            )
            for line in result.stdout.splitlines():
                if "[UP]" in line or "완료" in line:
                    print(f"   {line.strip()}")
    except Exception as e:
        print(f"   [WARN] R2 최종 업로드 확인 실패: {e}")

    # 동기화 시도
    sync_to_github_pages()

    # EBS Downloader 종료 시도
    try:
        from src.downloader_clicker import close_downloader_window
        close_downloader_window()
    except Exception:
        pass

    end_time = time.time()
    elapsed = end_time - start_time
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print(f"\n{'='*80}")
    print(f"[DONE] 모든 작업 완료!")
    print(f"   - 총 소요 시간: {minutes}분 {seconds}초")
    print(f"   - 종료 시간: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))}")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()
