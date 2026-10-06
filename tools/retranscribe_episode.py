"""
특정 에피소드의 추출된 MP3를 영어로 재전사하여 player.json 의 script 를 갱신.

사용법:
  python tools/retranscribe_episode.py 2754

동작:
  1. output_mp3/<episode_num>_*.mp3 파일 찾기
  2. faster-whisper로 영어 재전사
  3. 한국어/종결문구 필터 + 중복 제거
  4. player.json script 갱신 (mp3_url, episode_num 등 메타는 유지)
"""

import sys
import json
import re
from pathlib import Path
from difflib import SequenceMatcher

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))
from src.config import OUTPUT_MP3_DIR, DEFAULT_MODEL, END_PHRASES, TEACHER_EN_PHRASES

def calculate_ngram_similarity(a: str, b: str, n: int = 3) -> float:
    def to_ngrams(s):
        return set(s[i:i+n] for i in range(len(s) - n + 1))
    a_set, b_set = to_ngrams(a), to_ngrams(b)
    if not a_set or not b_set:
        return 0.0
    return len(a_set & b_set) / max(len(a_set), len(b_set))

def clean_english_segments(raw_segments: list, actual_duration: float) -> list:
    clean = []
    dup_count = ko_filtered = 0

    for seg in raw_segments:
        text = seg['text'].strip()
        if not text:
            continue

        # 한국어 문자 제거
        original_text = text
        text = "".join(c for c in text if not ('가' <= c <= '힣')).strip()
        if not any(c.isalpha() for c in text):
            ko_filtered += 1
            continue

        # 내부 중복 제거
        if len(text) > 10:
            mid = len(text) // 2
            if calculate_ngram_similarity(text[:mid].strip().lower(), text[mid:].strip().lower()) > 0.8:
                text = text[:mid].strip()

        # 겹침(Overlap) 제거
        if clean:
            prev_text = clean[-1]['text'].split(' ')[0]  # Korean translation 제외한 영어 부분
            # 실제로는 전체 텍스트로 비교
            prev_full = clean[-1]['text']
            s = SequenceMatcher(None, prev_full.lower(), text.lower())
            match = s.find_longest_match(0, len(prev_full), 0, len(text))
            if match.size >= 3:
                if (match.a + match.size == len(prev_full)) and (match.b == 0):
                    remaining = text[match.size:]
                    overlap_text = text[:match.size]
                    is_word_split = (remaining and remaining[0].isalnum() and overlap_text[-1].isalnum())
                    if not is_word_split:
                        text = remaining.strip()

        if not text:
            dup_count += 1
            continue

        # 전체 중복 필터
        is_dup = False
        for c_seg in clean[-10:]:
            c_text = c_seg['text'].split('.')[0].strip().lower()  # Korean 번역 앞 영어 부분
            if calculate_ngram_similarity(text.lower(), c_seg['text'].lower()) > 0.85:
                is_dup = True
                break
        if is_dup:
            dup_count += 1
            continue

        # 종료 문구 필터
        if any(ep in original_text for ep in END_PHRASES):
            ko_filtered += 1
            continue

        # 선생님 문구 필터
        text_lower = text.lower()
        if any(tp in text_lower for tp in TEACHER_EN_PHRASES):
            ko_filtered += 1
            continue

        rel_start = max(0, float(seg['start']))
        rel_end = min(actual_duration, float(seg['end']))

        clean.append({
            "start": round(rel_start, 2),
            "end": round(rel_end, 2),
            "text": text,
        })

    print(f"   세그먼트: 총 {len(raw_segments)}개 → 정제 후 {len(clean)}개 (중복 {dup_count}, 한국어 {ko_filtered})")
    return clean

def add_korean_translations(segments: list, base_name: str):
    """한국어 번역 추가 (Gemini 우선, 실패 시 Google 번역). 영어 뒤에 한국어를 이어 붙인다."""
    from src.translator import translate_texts
    english = [seg['text'].strip() for seg in segments]
    translated = translate_texts([e for e in english if e])
    it = iter(translated)
    for seg, eng in zip(segments, english):
        if not eng:
            continue
        ko = next(it)
        if ko:
            seg['text'] = f"{eng} {ko}"
            print(f"   [번역] {eng} → {ko}")
        else:
            print(f"   [번역 실패] {eng}")


def update_txt_script(txt_path: Path, segments: list):
    """txt 스크립트의 세그먼트 줄만 새 내용으로 교체 (헤더/푸터 유지)"""
    if not txt_path.exists():
        return
    lines = txt_path.read_text(encoding='utf-8').splitlines()
    idx = [i for i, l in enumerate(lines) if l.startswith('[')]
    if not idx:
        return
    new_lines = [f"[{seg['start']:>6.2f}s - {seg['end']:>6.2f}s] {seg['text']}" for seg in segments]
    lines[idx[0]:idx[-1] + 1] = new_lines
    txt_path.write_text("\n".join(lines) + "\n", encoding='utf-8')


def main():
    if len(sys.argv) < 2:
        print("사용법: python tools/retranscribe_episode.py <episode_num>")
        print("예시:   python tools/retranscribe_episode.py 2754")
        sys.exit(1)

    ep_num = sys.argv[1]

    # 에피소드 MP3 찾기
    mp3_files = list(OUTPUT_MP3_DIR.glob(f"{ep_num}_*.mp3"))
    mp3_files = [f for f in mp3_files if not f.name.startswith("extracted_")]

    if not mp3_files:
        print(f"[오류] output_mp3/{ep_num}_*.mp3 파일 없음")
        sys.exit(1)

    mp3_path = mp3_files[0]
    stem = mp3_path.stem
    player_json_path = OUTPUT_MP3_DIR / f"{stem}_player.json"

    print(f"MP3: {mp3_path.name}")
    print(f"Player JSON: {player_json_path.name}")

    if not player_json_path.exists():
        print(f"[오류] player.json 없음: {player_json_path}")
        sys.exit(1)

    # 기존 player.json 로드
    with open(player_json_path, encoding='utf-8') as f:
        player_data = json.load(f)

    from pydub import AudioSegment
    audio = AudioSegment.from_mp3(str(mp3_path))
    actual_duration = len(audio) / 1000
    print(f"오디오 길이: {actual_duration:.2f}초")

    # faster-whisper로 영어 재전사 (CPU int8)
    print(f"\n영어 재전사 중... (모델: {DEFAULT_MODEL}, device: cpu)")
    from faster_whisper import WhisperModel
    model = WhisperModel(DEFAULT_MODEL, device="cpu", compute_type="int8")

    seg_iter, info = model.transcribe(
        str(mp3_path),
        language='en',
        word_timestamps=False,
        vad_filter=True,  # VAD 활성화로 무음 구간 스킵
        vad_parameters={"min_silence_duration_ms": 500},
    )

    raw_segments = []
    for s in seg_iter:
        raw_segments.append({"start": float(s.start), "end": float(s.end), "text": s.text})
        print(f"   [{s.start:.1f}s-{s.end:.1f}s] {s.text.strip()}")

    print(f"\n정제 중...")
    clean = clean_english_segments(raw_segments, actual_duration)

    print(f"\n한국어 번역 추가 중...")
    add_korean_translations(clean, stem)

    print(f"\n정제된 세그먼트:")
    for seg in clean:
        print(f"   [{seg['start']:.1f}s-{seg['end']:.1f}s] {seg['text']}")

    # player.json 갱신 (메타는 유지, script만 교체)
    player_data['script'] = clean

    with open(player_json_path, 'w', encoding='utf-8') as f:
        json.dump(player_data, f, ensure_ascii=False, indent=2)

    update_txt_script(OUTPUT_MP3_DIR / f"{stem}.txt", clean)

    print(f"\n✅ player.json / txt 갱신 완료: {player_json_path.name}")
    print(f"   세그먼트: {len(clean)}개")

if __name__ == "__main__":
    main()
