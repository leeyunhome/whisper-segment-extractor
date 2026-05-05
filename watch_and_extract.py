"""
EBS MP3 자동 감시 + 추출 파이프라인 (회차 정보 기반 파일명)

동작:
  1. C:\\EBSe 폴더 감시
  2. 새 MP3 발견 → 다운로드 완료 대기
  3. .episode_info/ 에서 lectId 매핑하여 회차 정보 조회
  4. source_mp3/ 로 이동 (원본 파일명 유지)
  5. smart_extract 실행
  6. 결과를 회차 정보 기반 파일명으로 output_mp3/ 에 저장
     예: 2708_가정_너_정도면_청소년_아니니_20260504.mp3
"""

import argparse
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

try:
    from smart_extract import SmartConversationExtractor, HAS_INA
except ImportError:
    print("[ERROR] smart_extract.py 를 import 할 수 없습니다.")
    sys.exit(1)

try:
    from ebs_episode_info import make_safe_filename
    HAS_EPISODE_INFO = True
except ImportError:
    HAS_EPISODE_INFO = False


# ==============================================================================
# 설정
# ==============================================================================

DEFAULT_WATCH_DIR = r"C:\EBSe"

PROJECT_DIR = Path(__file__).parent.resolve()
SOURCE_MP3_DIR = PROJECT_DIR / "source_mp3"
OUTPUT_MP3_DIR = PROJECT_DIR / "output_mp3"
EPISODE_INFO_DIR = PROJECT_DIR / ".episode_info"

EBS_FILENAME_PATTERN = re.compile(r"^\d{8}_\d{6}_[0-9a-fA-F]+_mp3\.mp3$")

SIZE_STABLE_CHECKS = 3
SIZE_CHECK_INTERVAL = 2.0
POLL_INTERVAL = 3.0

DEBUG = False


def dbg(msg: str):
    if DEBUG:
        print(f"[DEBUG] {msg}")


# ==============================================================================
# 회차 정보 매핑
# ==============================================================================

def find_episode_info_for_file(mp3_path: Path) -> dict:
    """
    EBS Downloader가 받은 MP3 파일에 해당하는 회차 정보를 찾는다.

    EBS Downloader 파일명: 20260504_090000_93c061d7_mp3.mp3
    .episode_info/{lectId}.json 에는 회차 메타데이터.

    매핑 전략 (우선순위 순):
      1. 파일명의 방영일과 .episode_info/*.json 의 air_date_compact 정확 매칭
         (가장 정확. mtime 이나 다운로드 순서에 의존 안 함)
      2. fallback: mp3 파일의 mtime 과 가장 가까운 episode_info

    Returns:
        {episode, category, subtitle, air_date, lectId, ...} 또는 빈 dict
    """
    if not EPISODE_INFO_DIR.exists():
        return {}

    # 1. 파일명에서 방영일 추출 (YYYYMMDD)
    fname_match = re.match(r'^(\d{8})_', mp3_path.name)
    file_date = fname_match.group(1) if fname_match else None

    info_files = list(EPISODE_INFO_DIR.glob("*.json"))
    if not info_files:
        return {}

    # 2. 날짜 정확 매칭 우선
    if file_date:
        for info_file in info_files:
            try:
                with open(info_file, 'r', encoding='utf-8') as f:
                    info = json.load(f)
                if info.get('air_date_compact') == file_date:
                    dbg(f"날짜 매칭: {mp3_path.name} <-> 회차 {info.get('episode')}")
                    return info
            except Exception as e:
                dbg(f"info 로드 실패 {info_file}: {e}")
                continue
        dbg(f"날짜 {file_date} 매칭 실패, mtime fallback 시도")

    # 3. fallback: mtime 매칭
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
            dbg(f"mtime 매칭 (fallback): {best_match.name} -> 회차 {info.get('episode')}")
            return info
        except Exception as e:
            dbg(f"info 로드 실패 {best_match}: {e}")

    return {}


def build_output_basename(mp3_path: Path) -> str:
    """
    출력 파일명의 basename 생성.

    회차 정보가 있으면: '2708_가정_너_정도면_청소년_아니니_20260504'
    없으면: 원본 파일명에서 .mp3 뺀 것
    """
    if HAS_EPISODE_INFO:
        info = find_episode_info_for_file(mp3_path)
        if info and 'episode' in info:
            return make_safe_filename(info)

    # fallback: 원본 파일명
    return mp3_path.stem


# ==============================================================================
# 유틸리티
# ==============================================================================

def is_ebs_mp3(filename: str) -> bool:
    return bool(EBS_FILENAME_PATTERN.match(filename))


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
    stable_count = 0
    elapsed = 0.0

    while stable_count < SIZE_STABLE_CHECKS:
        if elapsed > max_wait:
            print(f"   [WARN] 대기 시간 초과 ({max_wait:.0f}초)")
            return False

        if not filepath.exists():
            print(f"   [ERROR] 파일이 사라짐: {filepath.name}")
            return False

        try:
            current_size = filepath.stat().st_size
        except OSError:
            time.sleep(SIZE_CHECK_INTERVAL)
            elapsed += SIZE_CHECK_INTERVAL
            continue

        if current_size == last_size and current_size > 0:
            stable_count += 1
        else:
            stable_count = 0
            last_size = current_size

        time.sleep(SIZE_CHECK_INTERVAL)
        elapsed += SIZE_CHECK_INTERVAL

    for attempt in range(5):
        try:
            with open(filepath, "rb") as f:
                f.read(1024)
            break
        except (PermissionError, OSError):
            time.sleep(1.0)
    else:
        print(f"   [WARN] 파일 잠김")
        return False

    size_mb = last_size / (1024 * 1024)
    print(f"   [OK] 다운로드 완료 ({size_mb:.2f} MB)")
    return True


def move_to_source(src: Path) -> Path:
    SOURCE_MP3_DIR.mkdir(exist_ok=True)
    dst = SOURCE_MP3_DIR / src.name

    if dst.exists():
        ts = time.strftime("%Y%m%d_%H%M%S")
        dst = SOURCE_MP3_DIR / f"{dst.stem}__dup{ts}{dst.suffix}"

    shutil.move(str(src), str(dst))
    print(f"   [MOVE] {src.name}{dst.relative_to(PROJECT_DIR)}")
    return dst


def move_outputs_to_output_dir(source_basename: str, output_basename: str) -> list:
    """
    smart_extract 가 생성한 결과 파일들을 output_mp3/ 로 이동하면서 이름 변경.

    Args:
        source_basename: 원본 파일명 (확장자 제외, smart_extract가 사용한 이름)
        output_basename: 새 파일명 베이스 (회차 정보 기반)
    """
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
            print(f"   [OUT] {src.name}{dst.name}")
        else:
            print(f"   [WARN] 생성되지 않은 파일: {src.name}")

    return moved


# ==============================================================================
# 핵심 처리
# ==============================================================================

def process_one_file(mp3_path: Path, extractor: SmartConversationExtractor) -> bool:
    print(f"\n{'='*80}")
    print(f"[PROCESS] {mp3_path.name}")
    print(f"{'='*80}")

    # 회차 정보 조회 (이동 전에 mtime 기준으로 매칭)
    output_basename = build_output_basename(mp3_path)
    print(f"   출력 파일명: {output_basename}")

    # source_mp3/ 로 이동 (원본 이름 유지)
    source_path = move_to_source(mp3_path)
    source_basename = source_path.stem

    # smart_extract 실행
    original_cwd = os.getcwd()
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
        os.chdir(original_cwd)

    if not success:
        print(f"   [ERROR] 추출 실패")
        return False

    # 결과 이동 + 이름 변경
    moved = move_outputs_to_output_dir(source_basename, output_basename)
    print(f"\n[DONE] {mp3_path.name} → output_mp3/{output_basename}.mp3")
    print(f"       생성된 파일: {len(moved)}개")
    return True


# ==============================================================================
# 감시 루프
# ==============================================================================

def scan_folder(watch_dir: Path) -> tuple:
    if not watch_dir.exists():
        return [], 0

    ebs_files = []
    other_count = 0

    try:
        entries = list(watch_dir.iterdir())
    except (PermissionError, OSError):
        return [], 0

    for entry in entries:
        if entry.is_dir():
            other_count += 1
            continue
        if not entry.is_file():
            continue
        if is_ebs_mp3(entry.name):
            ebs_files.append(entry)
        else:
            other_count += 1

    return ebs_files, other_count


def watch_loop(watch_dir: Path,
               extractor: SmartConversationExtractor,
               process_existing: bool = False,
               run_once: bool = False,
               max_files: int = 0):
    if not watch_dir.exists():
        print(f"[WARN] 감시 폴더 없음. 생성: {watch_dir}")
        try:
            watch_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"[ERROR] {e}")
            return

    print(f"\n{'='*80}")
    print(f"[WATCH] EBS MP3 감시 시작")
    print(f"{'='*80}")
    print(f"감시 폴더: {watch_dir}")
    print(f"입력 폴더: {SOURCE_MP3_DIR}")
    print(f"출력 폴더: {OUTPUT_MP3_DIR}")
    if max_files > 0:
        print(f"최대 처리: {max_files}개 파일")
    print(f"{'='*80}\n")

    initial_ebs, initial_other = scan_folder(watch_dir)
    print(f"[INFO] 시작 시 폴더: EBS MP3 {len(initial_ebs)}개, 기타 {initial_other}")

    if process_existing:
        already_seen = set()
        if initial_ebs:
            print(f"   → 기존 파일도 처리 (--process-existing)")
    else:
        already_seen = {str(f) for f in initial_ebs}
        if initial_ebs:
            print(f"   → 기존 {len(initial_ebs)}개 무시")

    print()
    processed_count = 0  # 성공한 추출 개수
    attempted_count = 0  # 시도한 파일 개수 (성공/실패 무관)
    failed_files = []    # 실패한 파일 리스트
    print(f"[READY] 새 파일 대기 중. Ctrl+C 로 종료.\n")

    try:
        while True:
            current_ebs, _ = scan_folder(watch_dir)
            new_files = [f for f in current_ebs if str(f) not in already_seen]

            for mp3_path in new_files:
                print(f"\n[NEW] {mp3_path.name}")

                if is_file_complete(mp3_path):
                    try:
                        size_mb = mp3_path.stat().st_size / (1024 * 1024)
                        print(f"   [OK] 이미 다운로드 완료 ({size_mb:.2f} MB)")
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
                    failed_files.append(mp3_path.name)

                # 종료 조건: 시도한 파일 수 기준 (성공/실패 무관)
                if run_once or (max_files > 0 and attempted_count >= max_files):
                    print(f"\n{'='*80}")
                    print(f"[DONE] 처리 완료")
                    print(f"{'='*80}")
                    print(f"  시도: {attempted_count}개")
                    print(f"  성공: {processed_count}개")
                    if failed_files:
                        print(f"  실패: {len(failed_files)}개")
                        for fname in failed_files:
                            print(f"    - {fname}")
                    print(f"{'='*80}")
                    return

            time.sleep(POLL_INTERVAL)

    except KeyboardInterrupt:
        print(f"\n\n[STOP] 종료 (사용자 요청)")
        print(f"  시도: {attempted_count}개")
        print(f"  성공: {processed_count}개")
        if failed_files:
            print(f"  실패: {len(failed_files)}개")
            for fname in failed_files:
                print(f"    - {fname}")


# ==============================================================================
# 진입점
# ==============================================================================

def main():
    global DEBUG

    parser = argparse.ArgumentParser(
        description="EBS MP3 감시 + 추출 (회차 정보 기반 파일명)"
    )
    parser.add_argument("--watch-dir", type=str, default=DEFAULT_WATCH_DIR)
    parser.add_argument("--model", type=str, default="small",
                        choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("--once", action="store_true",
                        help="1개 처리 후 종료")
    parser.add_argument("--max-files", type=int, default=0,
                        help="N개 처리 후 종료 (0 = 무한)")
    parser.add_argument("--process-existing", action="store_true")
    parser.add_argument("--debug", action="store_true")

    args = parser.parse_args()
    DEBUG = args.debug

    if not HAS_INA:
        print("[ERROR] inaSpeechSegmenter 미설치")
        print("   pip install inaSpeechSegmenter tensorflow")
        sys.exit(1)

    watch_dir = Path(args.watch_dir).resolve()

    print(f"\n[INIT] Whisper 모델 로딩... ({args.model})")
    extractor = SmartConversationExtractor(model_size=args.model)
    extractor.load_models()

    watch_loop(
        watch_dir=watch_dir,
        extractor=extractor,
        process_existing=args.process_existing,
        run_once=args.once,
        max_files=args.max_files,
    )


if __name__ == "__main__":
    main()
