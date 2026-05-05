"""
EBS 자동화 통합 실행 스크립트

ebs_auto_download.py + watch_and_extract.py 를 함께 실행.

사용법:
    python run_all.py                       # 최신 회차 1개
    python run_all.py --episode 2707        # 특정 회차
    python run_all.py --episode 2658-2661   # 회차 범위
    python run_all.py --model tiny          # Whisper 모델
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path
from threading import Thread

PROJECT_DIR = Path(__file__).parent.resolve()


def run_watch(model: str, max_files: int):
    """watch_and_extract.py 실행"""
    cmd = [
        sys.executable,
        str(PROJECT_DIR / "watch_and_extract.py"),
        "--model", model,
    ]
    if max_files == 1:
        cmd.append("--once")
    elif max_files > 1:
        cmd.extend(["--max-files", str(max_files)])

    print(f"[RUN] watch_and_extract: {' '.join(cmd)}")
    subprocess.run(cmd)


def run_download(episode: str = None):
    """ebs_auto_download.py 실행"""
    cmd = [
        sys.executable,
        str(PROJECT_DIR / "ebs_auto_download.py"),
    ]
    if episode:
        cmd.extend(["--episode", episode])

    print(f"[RUN] ebs_auto_download: {' '.join(cmd)}")
    subprocess.run(cmd)


def count_episodes(episode_arg: str) -> int:
    """--episode 인자에서 총 회차 수 계산"""
    if not episode_arg:
        return 1

    total = set()
    for part in episode_arg.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            try:
                start, end = part.split('-', 1)
                start_n, end_n = int(start), int(end)
                if start_n > end_n:
                    start_n, end_n = end_n, start_n
                total.update(range(start_n, end_n + 1))
            except ValueError:
                continue
        else:
            try:
                total.add(int(part))
            except ValueError:
                continue
    return len(total) or 1


def main():
    parser = argparse.ArgumentParser(
        description="EBS 자동 다운로드 + 추출 통합 실행"
    )
    parser.add_argument("--episode", type=str, default=None,
                        help="회차 (예: 2707, 2658-2661, 2700,2705)")
    parser.add_argument("--model", type=str, default="small",
                        choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("--watch-first-delay", type=float, default=8.0,
                        help="watch 시작 후 download 시작까지 대기(초)")
    args = parser.parse_args()

    expected_count = count_episodes(args.episode)

    print(f"\n{'='*80}")
    print(f"[START] EBS 자동화 통합 실행")
    print(f"{'='*80}")
    if args.episode:
        print(f"회차: {args.episode} (총 {expected_count}개)")
    else:
        print(f"회차: 최신 1개")
    print(f"모델: {args.model}")
    print(f"{'='*80}\n")

    # 1) watch 시작
    watch_thread = Thread(
        target=run_watch,
        args=(args.model, expected_count),
        daemon=False,
    )
    watch_thread.start()

    # 2) 모델 로딩 대기
    print(f"[WAIT] {args.watch_first_delay}초 후 다운로드 트리거...")
    time.sleep(args.watch_first_delay)

    # 3) 다운로드 실행
    run_download(args.episode)

    # 4) watch 종료 대기
    print("\n[WAIT] 다운로드 + 추출 처리 대기 중... (Ctrl+C 로 중단)")
    watch_thread.join()

    print("\n[DONE] 모든 작업 완료!")


if __name__ == "__main__":
    main()
