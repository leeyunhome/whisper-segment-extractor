"""
한국어 해석이 빠진 회차에 번역만 채워 넣는 복구 도구 (오디오 재추출 없음).

사용법:
  python -m tools.backfill_translations 2784-2819
  python -m tools.backfill_translations 2818,2819 --dry-run

동작:
  1. output_mp3/<회차>_*_player.json 의 script 중 한글이 없는 문장을 찾음
  2. 지연 + 재시도 번역(extractor.translate_with_retry)으로 "영어 한국어" 형태로 채움
  3. 같은 회차의 .txt 스크립트도 동일하게 갱신

갱신 후 웹에 반영하려면 GitHub Pages 동기화(src.runner.sync_to_github_pages)가 필요하다.
"""

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.config import OUTPUT_MP3_DIR
from src.extractor import translate_with_retry

HANGUL = re.compile("[가-힣]")


def parse_episodes(arg: str) -> list:
    result = set()
    for part in arg.split(","):
        part = part.strip()
        if "-" in part:
            a, b = part.split("-", 1)
            result.update(range(int(a), int(b) + 1))
        elif part:
            result.add(int(part))
    return sorted(result)


def backfill_episode(translator, ep: int, dry_run: bool) -> tuple:
    """(번역한 문장 수, 실패 문장 수) 반환"""
    json_files = sorted(OUTPUT_MP3_DIR.glob(f"{ep}_*_player.json"))
    if not json_files:
        print(f"[{ep}회] player.json 없음 - 건너뜀")
        return 0, 0

    json_path = json_files[0]
    data = json.loads(json_path.read_text(encoding="utf-8"))
    mapping = {}  # 영어 원문 -> "영어 한국어"
    failed = 0

    for seg in data.get("script", []):
        eng = seg.get("text", "").strip()
        if not eng or HANGUL.search(eng):
            continue
        if dry_run:
            mapping[eng] = eng
            continue
        ko = translate_with_retry(translator, eng)
        if ko:
            mapping[eng] = f"{eng} {ko}"
            seg["text"] = mapping[eng]
        else:
            failed += 1

    if not mapping:
        print(f"[{ep}회] 번역할 문장 없음")
        return 0, failed

    if dry_run:
        print(f"[{ep}회] (dry-run) 번역 대상 {len(mapping)}문장")
        return len(mapping), 0

    json_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # txt 스크립트: "[ 0.00s - 7.00s] 영어" 줄의 영어 부분을 치환
    for txt_path in sorted(OUTPUT_MP3_DIR.glob(f"{ep}_*.txt")):
        lines = txt_path.read_text(encoding="utf-8").splitlines()
        for i, line in enumerate(lines):
            m = re.match(r"^(\[\s*[\d.]+s\s*-\s*[\d.]+s\]\s)(.*)$", line)
            if m and m.group(2).strip() in mapping:
                lines[i] = m.group(1) + mapping[m.group(2).strip()]
        txt_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[{ep}회] {len(mapping)}문장 번역 완료" + (f", {failed}문장 실패" if failed else ""))
    return len(mapping), failed


def main():
    parser = argparse.ArgumentParser(description="누락된 한국어 해석 복구")
    parser.add_argument("episodes", help="회차 (예: 2784-2819 또는 2818,2819)")
    parser.add_argument("--dry-run", action="store_true", help="번역/저장 없이 대상만 확인")
    args = parser.parse_args()

    translator = None
    if not args.dry_run:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source="en", target="ko")

    total_ok = total_fail = 0
    for ep in parse_episodes(args.episodes):
        ok, fail = backfill_episode(translator, ep, args.dry_run)
        total_ok += ok
        total_fail += fail

    print(f"\n완료: 번역 {total_ok}문장, 실패 {total_fail}문장")


if __name__ == "__main__":
    main()
