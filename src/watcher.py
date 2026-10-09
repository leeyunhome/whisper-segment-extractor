"""
다운로드 감시 + 자동 추출 파이프라인.

흐름:
  1. C:\\EBSe 감시 → 새 MP3 발견
  2. 다운로드 완료 대기 (크기 안정화)
  3. 회차 정보 매핑 (파일명 날짜 우선)
  4. source_mp3/ 로 이동
  5. SmartConversationExtractor 로 추출
  6. output_mp3/ 에 회차 정보 기반 파일명으로 저장
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

from src.config import (
    SOURCE_MP3_DIR, OUTPUT_MP3_DIR, EPISODE_INFO_DIR,
    DEFAULT_WATCH_DIR, DEFAULT_MODEL, AVAILABLE_MODELS,
    EBS_FILENAME_PATTERN, SIZE_STABLE_CHECKS, SIZE_CHECK_INTERVAL, POLL_INTERVAL,
    PROJECT_DIR,
)
from src.episode_info import make_safe_filename
from src.extractor import SmartConversationExtractor, HAS_INA


EBS_PATTERN = re.compile(EBS_FILENAME_PATTERN)
DEBUG = False


def dbg(msg: str):
    if DEBUG:
        print(f"[DEBUG] {msg}")


# ==============================================================================
# 회차 정보 매핑 (날짜 우선 → mtime fallback)
# ==============================================================================

def find_episode_info_for_file(mp3_path: Path) -> dict:
    """
    EBS 파일명: 20260316_173000_xxx_mp3.mp3 → 날짜 20260316
    .episode_info/{lectId}.json 의 air_date_compact 와 정확 매칭
    """
    if not EPISODE_INFO_DIR.exists():
        return {}

    fname_match = re.match(r'^(\d{8})_', mp3_path.name)
    file_date = fname_match.group(1) if fname_match else None

    info_files = list(EPISODE_INFO_DIR.glob("*.json"))
    if not info_files:
        return {}

    # 1. 날짜 정확 매칭
    if file_date:
        for info_file in info_files:
            try:
                with open(info_file, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                if info.get('air_date_compact') == file_date:
                    dbg(f"날짜 매칭: {mp3_path.name} ↔ 회차 {info.get('episode')}")
                    return info
            except Exception:
                continue
        dbg(f"날짜 {file_date} 매칭 실패, mtime fallback")

    # 2. mtime fallback
    info_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    try:
        mp3_mtime = mp3_path.stat().st_mtime
    except OSError:
        mp3_mtime = time.time()

    best_match = None
    best_diff = float('inf')

    for info_file in info_files:
        try:
            info_mtime = info_file.stat().st_mtime
            diff = mp3_mtime - info_mtime
            if -60 <= diff <= 600:
                if abs(diff) < abs(best_diff):
                    best_diff = diff
                    best_match = info_file
        except OSError:
            continue

    if not best_match and info_files:
        best_match = info_files[0]

    if best_match:
        try:
            with open(best_match, 'r', encoding='utf-8') as f:
                info = json.load(f)
            dbg(f"mtime fallback: {best_match.name} → 회차 {info.get('episode')}")
            return info
        except Exception:
            pass

    return {}


def build_output_basename(mp3_path: Path) -> str:
    info = find_episode_info_for_file(mp3_path)
    if info and 'episode' in info:
        return make_safe_filename(info)
    return mp3_path.stem


# ==============================================================================
# 파일 처리
# ==============================================================================

def is_ebs_mp3(filename: str) -> bool:
    return bool(EBS_PATTERN.match(filename))


def is_file_complete(filepath: Path) -> bool:
    if not filepath.exists():
        return False
    try:
        size = filepath.stat().st_size
        if size == 0:
            return False
        with open(filepath, "rb") as f:
            f.read(1024)
        return True
    except (PermissionError, OSError):
        return False


def wait_for_download_complete(filepath: Path, max_wait: float = 600.0) -> bool:
    print(f"   [WAIT] 다운로드 완료 대기...")
    last_size = -1
    stable = 0
    elapsed = 0.0

    while stable < SIZE_STABLE_CHECKS:
        if elapsed > max_wait:
            print(f"   [WARN] 시간 초과")
            return False

        if not filepath.exists():
            print(f"   [ERROR] 파일이 사라짐")
            return False

        try:
            size = filepath.stat().st_size
        except OSError:
            time.sleep(SIZE_CHECK_INTERVAL)
            elapsed += SIZE_CHECK_INTERVAL
            continue

        if size == last_size and size > 0:
            stable += 1
        else:
            stable = 0
            last_size = size

        time.sleep(SIZE_CHECK_INTERVAL)
        elapsed += SIZE_CHECK_INTERVAL

    # 잠금 해제 확인
    for _ in range(5):
        try:
            with open(filepath, "rb") as f:
                f.read(1024)
            break
        except (PermissionError, OSError):
            time.sleep(1.0)
    else:
        return False

    print(f"   [OK] 완료 ({last_size / (1024*1024):.2f} MB)")
    return True


def move_to_source(src: Path) -> Path:
    SOURCE_MP3_DIR.mkdir(exist_ok=True)
    dst = SOURCE_MP3_DIR / src.name
    if dst.exists():
        ts = time.strftime("%Y%m%d_%H%M%S")
        dst = SOURCE_MP3_DIR / f"{dst.stem}__dup{ts}{dst.suffix}"
    shutil.move(str(src), str(dst))
    print(f"   [MOVE] {src.name} → {dst.relative_to(PROJECT_DIR)}")
    return dst


def move_outputs_to_output_dir(source_basename: str, output_basename: str) -> list:
    """smart_extract 결과 파일들을 output_mp3/ 로 이동 + 이름 변경"""
    OUTPUT_MP3_DIR.mkdir(exist_ok=True)
    moved = []

    file_specs = [
        ("extracted_{}.mp3", "{}.mp3"),
        ("script_{}.txt", "{}.txt"),
        ("transcription_{}.json", "{}_transcription.json"),
        ("player_{}.json", "{}_player.json"),
    ]

    for src_pattern, dst_pattern in file_specs:
        src = PROJECT_DIR / src_pattern.format(source_basename)
        if src.exists():
            dst_name = dst_pattern.format(output_basename)
            dst = OUTPUT_MP3_DIR / dst_name
            if dst.exists():
                dst.unlink()
            shutil.move(str(src), str(dst))
            moved.append(dst)
            print(f"   [OUT] {src.name} → {dst.name}")
        else:
            print(f"   [WARN] 생성 안 됨: {src.name}")

    return moved


def _upload_via_subprocess(output_basename: str) -> bool:
    """boto3가 없는 환경(whisper_env)에서도 동작하도록 miniconda base python으로 업로드 실행."""
    import subprocess
    # conda base python 경로 추정 (whisper_env -> base)
    base_python = Path(sys.executable).parent.parent.parent / "python.exe"
    if not base_python.exists():
        # fallback: 현재 환경에서 직접 시도
        from src.uploader import process_and_upload
        return process_and_upload(output_basename, OUTPUT_MP3_DIR, {})

    script = (
        f"import sys; sys.path.insert(0, r'{PROJECT_DIR}')\n"
        f"from src.uploader import process_and_upload\n"
        f"from pathlib import Path\n"
        f"ok = process_and_upload(r'{output_basename}', Path(r'{OUTPUT_MP3_DIR}'), {{}})\n"
        f"sys.exit(0 if ok else 1)\n"
    )
    result = subprocess.run(
        [str(base_python), "-c", script],
        cwd=str(PROJECT_DIR),
        capture_output=True, text=True, encoding="utf-8", errors="replace"
    )
    for line in result.stdout.splitlines():
        print(f"   {line}")
    return result.returncode == 0


def process_one_file(mp3_path: Path, extractor: SmartConversationExtractor) -> bool:
    print(f"\n{'='*80}")
    print(f"[PROCESS] {mp3_path.name}")
    print(f"{'='*80}")

    output_basename = build_output_basename(mp3_path)
    print(f"   출력 파일명: {output_basename}")

    source_path = move_to_source(mp3_path)
    source_basename = source_path.stem

    cwd = os.getcwd()
    try:
        os.chdir(PROJECT_DIR)
        success, anchor_time, output_path = extractor.find_anchor_and_extract_smart(
            str(source_path)
        )
    except Exception as e:
        print(f"   [ERROR] 추출 오류: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        os.chdir(cwd)

    if not success:
        print(f"   [ERROR] 추출 실패")
        return False

    moved = move_outputs_to_output_dir(source_basename, output_basename)
    print(f"\n[DONE] {mp3_path.name} → output_mp3/{output_basename}.mp3")
    print(f"       생성: {len(moved)}개")

    # 웹 플레이어 + 대시보드 자동 생성 (로컬 확인용)
    try:
        from tools.build_player import (
            build_universal_player_html,
            build_episode_data_json,
            build_dashboard,
            collect_episodes,
        )
        build_episode_data_json(output_basename, OUTPUT_MP3_DIR)
        episodes = collect_episodes(OUTPUT_MP3_DIR)
        build_universal_player_html(OUTPUT_MP3_DIR, episodes)
        build_dashboard(OUTPUT_MP3_DIR)
        print(f"       🎧 플레이어 준비 완료 (player.html)")
        print(f"       📊 대시보드 갱신 완료 (index.html)")
    except Exception as e:
        print(f"   [WARN] 플레이어 생성 실패: {e}")

    # R2 업로드 (Phase 2)
    # boto3가 현재 환경(whisper_env)에 없을 수 있으므로 miniconda base python으로 subprocess 실행
    try:
        upload_ok = _upload_via_subprocess(output_basename)
        if upload_ok:
            print(f"       ☁️  R2 업로드 완료")
            try:
                from tools.build_player import build_dashboard
                from src.runner import sync_to_github_pages
                build_dashboard(OUTPUT_MP3_DIR)
                print(f"       📊 대시보드 최종 갱신 완료")
                print(f"       🚀 GitHub Pages 실시간 동기화 중...")
                sync_to_github_pages()
            except Exception as e:
                print(f"       ⚠️ 실시간 동기화 실패: {e}")
        else:
            print(f"       ⚠️  R2 업로드 실패 (runner 종료 시 재시도됨)")
    except Exception as e:
        print(f"   [WARN] 업로드 과정 오류: {e}")

    return True


# ==============================================================================
# 감시 루프
# ==============================================================================

def scan_folder(watch_dir: Path) -> tuple:
    if not watch_dir.exists():
        return [], 0
    ebs_files, other = [], 0
    try:
        for entry in watch_dir.iterdir():
            if entry.is_dir():
                other += 1
                continue
            if not entry.is_file():
                continue
            if is_ebs_mp3(entry.name):
                ebs_files.append(entry)
            else:
                other += 1
    except (PermissionError, OSError):
        pass
    return ebs_files, other


def watch_loop(watch_dir: Path, extractor: SmartConversationExtractor,
              process_existing: bool = False, run_once: bool = False,
              max_files: int = 0, since: float = 0.0):
    if not watch_dir.exists():
        print(f"[WARN] 감시 폴더 생성: {watch_dir}")
        try:
            watch_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"[ERROR] {e}")
            return

    print(f"\n{'='*80}")
    print(f"[WATCH] EBS MP3 감시 시작")
    print(f"{'='*80}")
    print(f"감시: {watch_dir}")
    print(f"입력: {SOURCE_MP3_DIR}")
    print(f"출력: {OUTPUT_MP3_DIR}")
    if max_files > 0:
        print(f"최대: {max_files}개")
    print(f"{'='*80}\n")

    initial_ebs, initial_other = scan_folder(watch_dir)
    print(f"[INFO] 시작 시: EBS MP3 {len(initial_ebs)}개, 기타 {initial_other}")

    if process_existing:
        already_seen = set()
        if initial_ebs:
            print(f"   → 기존 파일도 처리 (--process-existing)")
    else:
        # since: 실행 시작 시각. 모델 로딩이 길어져 다운로드가 감시 시작보다 먼저 끝나도,
        # 이 시각 이후에 생긴 파일은 '기존 파일'이 아니라 이번 실행의 새 파일로 처리한다.
        def _is_old(f: Path) -> bool:
            if not since:
                return True
            try:
                return f.stat().st_mtime < since
            except OSError:
                return True

        already_seen = {str(f) for f in initial_ebs if _is_old(f)}
        fresh = len(initial_ebs) - len(already_seen)
        if already_seen:
            print(f"   → 기존 {len(already_seen)}개 무시")
        if fresh:
            print(f"   → 이번 실행 중 받은 {fresh}개는 새 파일로 처리 (--since)")

    print()
    processed_count = 0
    attempted_count = 0
    failed_files = []
    print(f"[READY] 새 파일 대기. Ctrl+C 로 종료.\n")

    try:
        while True:
            current_ebs, _ = scan_folder(watch_dir)
            new_files = [f for f in current_ebs if str(f) not in already_seen]

            for mp3_path in new_files:
                print(f"\n[NEW] {mp3_path.name}")

                if is_file_complete(mp3_path):
                    try:
                        size_mb = mp3_path.stat().st_size / (1024 * 1024)
                        print(f"   [OK] 다운로드 완료 ({size_mb:.2f} MB)")
                    except OSError:
                        pass
                else:
                    if not wait_for_download_complete(mp3_path):
                        continue

                already_seen.add(str(mp3_path))
                attempted_count += 1

                ok = process_one_file(mp3_path, extractor)
                if ok:
                    processed_count += 1
                else:
                    info = find_episode_info_for_file(mp3_path)
                    ep_str = f"{info.get('episode')}회" if info.get('episode') else "회차미상"
                    failed_files.append(f"{ep_str} ({mp3_path.name})")

                if run_once or (max_files > 0 and attempted_count >= max_files):
                    print(f"\n{'='*80}")
                    print(f"[DONE] 처리 완료")
                    print(f"{'='*80}")
                    print(f"  시도: {attempted_count}개")
                    print(f"  성공: {processed_count}개")
                    if failed_files:
                        print(f"  실패: {len(failed_files)}개")
                        for msg in failed_files:
                            print(f"    - {msg}")
                    print(f"{'='*80}")
                    return

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print(f"\n\n[STOP] 사용자 중단")
        print(f"  시도: {attempted_count}개")
        print(f"  성공: {processed_count}개")
        if failed_files:
            print(f"  실패: {len(failed_files)}개")
            for msg in failed_files:
                print(f"    - {msg}")


# ==============================================================================
# 진입점
# ==============================================================================

def main():
    global DEBUG

    parser = argparse.ArgumentParser(
        description="EBS MP3 감시 + 추출"
    )
    parser.add_argument("--watch-dir", type=str, default=DEFAULT_WATCH_DIR)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL,
                       choices=AVAILABLE_MODELS)
    parser.add_argument("--device", type=str, default=None,
                       choices=["cuda", "cpu", None],
                       help="연산 디바이스 (도 안 주면 자동 감지)")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--max-files", type=int, default=0)
    parser.add_argument("--process-existing", action="store_true")
    parser.add_argument("--since", type=float, default=0.0,
                        help="이 epoch 시각 이후 생긴 파일은 감시 시작 전에 있었어도 새 파일로 처리")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()
    DEBUG = args.debug

    if not HAS_INA:
        print("[ERROR] inaSpeechSegmenter 미설치")
        print("   pip install inaSpeechSegmenter tensorflow")
        sys.exit(1)

    watch_dir = Path(args.watch_dir).resolve()

    print(f"\n[INIT] Whisper 모델 로딩 ({args.model})...")
    extractor = SmartConversationExtractor(model_size=args.model, device=args.device)
    extractor.load_models()

    watch_loop(
        watch_dir=watch_dir,
        extractor=extractor,
        process_existing=args.process_existing,
        run_once=args.once,
        max_files=args.max_files,
        since=args.since,
    )


if __name__ == "__main__":
    main()
