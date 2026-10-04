"""
회차 정보 매핑 검증 (추출은 안 함, 매핑 결과만 확인).

사용:
  python -m tools.check_mapping
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from src.config import SOURCE_MP3_DIR, DEFAULT_WATCH_DIR
from src.watcher import find_episode_info_for_file, build_output_basename


def check_dir(label: str, directory: Path):
    print(f"\n{'='*80}")
    print(f"[{label}] {directory}")
    print(f"{'='*80}")

    if not directory.exists():
        print(f"   (폴더 없음)")
        return

    mp3_files = sorted(directory.glob("*.mp3"))
    if not mp3_files:
        print(f"   (mp3 없음)")
        return

    for mp3_path in mp3_files:
        info = find_episode_info_for_file(mp3_path)
        basename = build_output_basename(mp3_path)
        ep = info.get('episode', '?')
        title = info.get('subtitle', '(매핑 실패)')
        print(f"   {mp3_path.name}")
        print(f"      → 회차 {ep}: {title}")
        print(f"      → 파일명: {basename}")


if __name__ == "__main__":
    check_dir("source_mp3", SOURCE_MP3_DIR)
    check_dir("WATCH_DIR", Path(DEFAULT_WATCH_DIR))
