"""
앵커 못 찾을 때 수동 진단 도구.

사용:
  python -m tools.find_anchor source_mp3/20260313_xxx.mp3
  python -m tools.find_anchor source_mp3/20260313_xxx.mp3 --use-existing-transcription

동작:
  1. (transcription 없으면) Whisper 한국어 전사 생성
  2. 검색 범위(22~28분 ± 진단 확장) 내 모든 세그먼트 표시
  3. "전체"/"대화"/"들어"/"주세요" 등 키워드 강조
  4. 사용자가 그 중 영어 시작점 텍스트를 발견하면
     config.py 의 ANCHOR_PHRASES 에 추가하면 됨
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
sys.stdout.reconfigure(encoding='utf-8')

from src.config import (
    ANCHOR_PHRASES, ANCHOR_TIME_MIN, ANCHOR_TIME_MAX,
    TRANSCRIBE_START_SEC, PROJECT_DIR, SIMILARITY_THRESHOLD,
)


# 진단 시 살펴볼 키워드들
DIAGNOSIS_KEYWORDS = [
    "전체", "대화", "들어", "주세요", "들어볼", "들어보",
    "함께", "한번", "한 번", "볼게요", "드릴게요",
]


def transcribe_korean(audio_path: Path, model_size: str = "small",
                     device: str = None) -> dict:
    """한국어 전사 (TRANSCRIBE_START_SEC 부터)"""
    from pydub import AudioSegment
    from src.extractor import detect_device, load_whisper_model

    if device is None:
        device = detect_device()

    print(f"🔄 Whisper 모델 로딩 ({model_size}, {device}, 백엔드: faster-whisper)...")
    model = load_whisper_model(model_size, device)
    print("✅ 로딩 완료\n")

    print(f"🔄 한국어 전사 ({TRANSCRIBE_START_SEC/60:.0f}분 부터)...")
    audio_full = AudioSegment.from_mp3(str(audio_path))
    audio_segment = audio_full[TRANSCRIBE_START_SEC * 1000:]

    temp_path = "_tmp_anchor_diag.mp3"
    audio_segment.export(temp_path, format="mp3")

    result = model.transcribe(
        temp_path, language='ko', word_timestamps=False
    )

    for seg in result['segments']:
        seg['start'] += TRANSCRIBE_START_SEC
        seg['end'] += TRANSCRIBE_START_SEC

    os.remove(temp_path)
    return result


def load_existing_transcription(audio_path: Path) -> dict:
    """이미 전사된 JSON 사용 (재전사 방지)"""
    base_name = audio_path.stem
    candidates = [
        PROJECT_DIR / f"transcription_{base_name}.json",
        Path(f"transcription_{base_name}.json"),
    ]
    for path in candidates:
        if path.exists():
            print(f"💾 기존 transcription 사용: {path}")
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)

    return None


def highlight_keyword(text: str) -> str:
    """텍스트에 키워드 강조 (▶...◀)"""
    result = text
    for kw in DIAGNOSIS_KEYWORDS:
        if kw in result:
            result = result.replace(kw, f"▶{kw}◀")
    return result


def check_anchor_match(text: str) -> str:
    """현재 등록된 앵커와 매칭되는지 (Fuzzy 포함)"""
    from src.extractor import SmartConversationExtractor
    calc = SmartConversationExtractor._calculate_ngram_similarity

    for anchor in ANCHOR_PHRASES:
        # 1. 완전 일치
        if anchor in text:
            return f"✅ 매칭: '{anchor}'"
        
        # 2. Fuzzy 매칭
        sim = calc(anchor, text)
        if sim >= SIMILARITY_THRESHOLD:
            return f"✅ Fuzzy 매칭 ({sim:.2f}): '{anchor}'"
            
    return ""


def diagnose(audio_path: Path, use_existing: bool = False, model_size: str = "small",
            device: str = None):
    """진단 실행"""
    print(f"\n{'='*80}")
    print(f"🔍 앵커 진단: {audio_path.name}")
    print(f"{'='*80}\n")

    # 전사 결과 가져오기
    result = None
    if use_existing:
        result = load_existing_transcription(audio_path)

    if result is None:
        if use_existing:
            print("⚠️  기존 transcription 없음. 새로 전사합니다.")
        result = transcribe_korean(audio_path, model_size, device)

    segments = result['segments']

    # 1. 현재 검색 범위 안에서 매칭되는지 확인
    print(f"📋 현재 설정:")
    print(f"   ANCHOR_PHRASES: {ANCHOR_PHRASES}")
    print(f"   검색 범위: {ANCHOR_TIME_MIN/60:.0f}분 ~ {ANCHOR_TIME_MAX/60:.0f}분")
    print()

    in_range = [s for s in segments
               if ANCHOR_TIME_MIN <= s['start'] <= ANCHOR_TIME_MAX]
    print(f"📍 검색 범위 내 세그먼트: {len(in_range)}개\n")

    matches = []
    for seg in in_range:
        text = seg['text'].strip()
        match = check_anchor_match(text)
        if match:
            matches.append((seg, match))

    if matches:
        print(f"✅ 현재 앵커로 매칭되는 세그먼트: {len(matches)}개")
        for seg, match in matches[:5]:
            t = seg['start']
            print(f"   [{t/60:.2f}분 / {t:.0f}s] {seg['text'].strip()}")
            print(f"      {match}")
        print(f"\n💡 추출이 정상 동작해야 합니다.")
        print(f"   만약 그래도 실패한다면 음악 패턴 분석 단계 문제일 수 있습니다.\n")
    else:
        print(f"❌ 현재 앵커로 매칭 불가\n")

    # 2. 진단 확장 범위 (±2분) 에서 키워드 후보 찾기
    diag_min = ANCHOR_TIME_MIN - 120
    diag_max = ANCHOR_TIME_MAX + 120

    print(f"🎯 진단 범위({diag_min/60:.0f}~{diag_max/60:.0f}분) 키워드 포함 세그먼트:")
    print(f"   (▶키워드◀ 강조 표시)\n")

    keyword_hits = []
    for seg in segments:
        if not (diag_min <= seg['start'] <= diag_max):
            continue
        text = seg['text'].strip()
        if any(kw in text for kw in DIAGNOSIS_KEYWORDS):
            keyword_hits.append(seg)

    if keyword_hits:
        for seg in keyword_hits:
            t = seg['start']
            highlighted = highlight_keyword(seg['text'].strip())
            print(f"   [{t/60:.2f}분 / {t:.0f}s] {highlighted}")
    else:
        print(f"   (없음)")

    # 3. 검색 범위 내 모든 세그먼트 (전체 보기)
    print(f"\n📜 검색 범위 내 모든 세그먼트:")
    if in_range:
        for seg in in_range:
            t = seg['start']
            text = seg['text'].strip()[:80]
            print(f"   [{t/60:.2f}분] {text}")
    else:
        print(f"   (없음)")

    # 4. 다음 액션 안내
    print(f"\n{'='*80}")
    print(f"💡 다음 액션:")
    print(f"{'='*80}")
    print(f"   1. 위에서 영어 대화 시작점에 해당하는 텍스트를 발견했다면")
    print(f"      → src/config.py 의 ANCHOR_PHRASES 리스트에 추가")
    print(f"")
    print(f"   2. 시간 범위가 안 맞으면")
    print(f"      → src/config.py 의 ANCHOR_TIME_MIN/MAX 조정")
    print(f"")
    print(f"   3. 그 후 다시 추출:")
    print(f"      python -m src.watcher --process-existing --max-files 1")
    print(f"{'='*80}\n")


def main():
    parser = argparse.ArgumentParser(
        description="앵커 못 찾을 때 수동 진단",
    )
    parser.add_argument("audio_path", help="MP3 파일 경로")
    parser.add_argument("--use-existing-transcription", action="store_true",
                       help="기존 transcription_*.json 재사용 (재전사 방지)")
    parser.add_argument("--model", type=str, default="small",
                       choices=["tiny", "base", "small", "medium", "large"])
    parser.add_argument("--device", type=str, default=None,
                       choices=["cuda", "cpu", None],
                       help="연산 디바이스 (도 안 주면 자동 감지)")
    args = parser.parse_args()

    audio_path = Path(args.audio_path).resolve()
    if not audio_path.exists():
        print(f"❌ 파일 없음: {audio_path}")
        sys.exit(1)

    diagnose(
        audio_path,
        use_existing=args.use_existing_transcription,
        model_size=args.model,
        device=args.device,
    )


if __name__ == "__main__":
    main()
