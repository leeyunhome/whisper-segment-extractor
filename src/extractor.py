"""
음악 기반 영어 대화 구간 추출 엔진.

처리 흐름:
  1. 앵커 찾기: Whisper 한국어 전사로 "전체대화..." 같은 문구 검색
  2. 음악 패턴 감지: inaSpeechSegmenter 로 한글→음악→영어→음악→영어→음악→한글 패턴 감지
  3. 시작점/종료점 결정
  4. MP3 추출 + 영어 재전사 + 스크립트 + 플레이어용 JSON 생성

앵커 못 찾을 때:
  - 자동으로 진단 정보 출력 (검색 범위 내 한국어 텍스트, "전체"/"대화" 포함 세그먼트)
  - tools/find_anchor.py 로 수동 진단 가능
"""

import json
import os
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional, Tuple



from src.config import (
    ANCHOR_PHRASES,
    ANCHOR_TIME_MIN,
    ANCHOR_TIME_MAX,
    TRANSCRIBE_START_SEC,
    END_PHRASES,
    TEACHER_EN_PHRASES,
    EXTRACT_MIN_DURATION,
    EXTRACT_MAX_DURATION,
    MIN_ENGLISH_DURATION_AFTER_ANCHOR,
    SIMILARITY_THRESHOLD,
    NGRAM_N,
)

# inaSpeechSegmenter(TF)를 모듈 레벨에서 import하면 watcher 시작 시점에
# TF가 CUDA를 선점해 ctranslate2(Whisper GPU)와 충돌→크래시 발생.
# 패키지 존재 여부만 확인하고, 실제 import는 load_models()에서 지연 실행.
import importlib.util as _ilu
HAS_INA = _ilu.find_spec("inaSpeechSegmenter") is not None


def detect_device() -> str:
    """GPU(CUDA) 사용 가능하면 'cuda', 아니면 'cpu' 반환"""
    try:
        import torch
        if torch.cuda.is_available():
            return "cuda"
    except ImportError:
        pass
    return "cpu"


class FasterWhisperBackend:
    """faster-whisper wrapper. openai-whisper와 동일한 dict 형태로 결과 반환.

    이 shim 덕에 호출부(extractor / tools)는 `result['segments']` 형태를
    그대로 쓰면서 백엔드만 CTranslate2로 바뀜.
    """

    def __init__(self, model_size: str, device: str):
        if device == "cuda":
            import os, site
            # ctranslate2는 LoadLibrary(플래그 없음)로 DLL을 로드하므로
            # os.add_dll_directory()가 아닌 PATH 환경변수에 추가해야 인식됨.
            _paths_to_add = []

            # 1. nvidia-cudnn-cu12 패키지 (cudnn_ops_infer64_8.dll 등 서브 DLL 포함)
            try:
                for sp in site.getsitepackages():
                    _p = os.path.join(sp, "nvidia", "cudnn", "bin")
                    if os.path.isdir(_p):
                        _paths_to_add.append(_p)
            except Exception:
                pass

            # 2. PyTorch 번들 CUDA DLL (cublas, cudart 등)
            try:
                import torch
                _p = os.path.join(os.path.dirname(torch.__file__), "lib")
                if os.path.isdir(_p):
                    _paths_to_add.append(_p)
            except ImportError:
                pass

            if _paths_to_add:
                os.environ["PATH"] = os.pathsep.join(_paths_to_add) + os.pathsep + os.environ.get("PATH", "")

        from faster_whisper import WhisperModel
        # float16: CUDA 권장 (속도/정확도 균형). int8: CPU 또는 VRAM 부족 시.
        compute_type = "float16" if device == "cuda" else "int8"
        self._model = WhisperModel(
            model_size, device=device, compute_type=compute_type
        )

    def transcribe(self, audio_path: str, language: str,
                   word_timestamps: bool = False, **_ignored) -> dict:
        seg_iter, info = self._model.transcribe(
            audio_path,
            language=language,
            word_timestamps=word_timestamps,
            vad_filter=False,
        )
        segments = []
        for s in seg_iter:
            segments.append({
                "start": float(s.start),
                "end": float(s.end),
                "text": s.text,
            })
        return {"segments": segments, "language": info.language}


def load_whisper_model(model_size: str, device: str) -> FasterWhisperBackend:
    """공용 모델 로더 (extractor + tools/find_anchor.py 공유)."""
    return FasterWhisperBackend(model_size, device)


class SmartConversationExtractor:
    """영어 대화 구간 자동 추출기."""

    def __init__(self, model_size: str = 'small', device: Optional[str] = None):
        self.model_size = model_size
        self.device = device or detect_device()
        self.model = None
        self.segmenter = None

    def load_models(self):
        """faster-whisper + inaSpeechSegmenter 로딩.

        순서: INA(TF/CPU) 먼저 → Whisper(ctranslate2/GPU) 나중.
        TF가 CUDA를 건드리기 전에 ctranslate2가 GPU 컨텍스트를 선점하면
        두 라이브러리의 CUDA 컨텍스트가 충돌해 inference 중 crash 발생.
        INA를 먼저 CPU로 초기화한 뒤 Whisper가 GPU를 독점 사용하면 안전.
        """
        # INA는 서브프로세스로 실행 (src/ina_worker.py) → 직접 로드 불필요
        # self.segmenter는 더 이상 사용하지 않음

        if self.model is None:
            print(f"🔄 Whisper 모델 로딩 중... (모델: {self.model_size}, 디바이스: {self.device}, 백엔드: faster-whisper)")
            if self.device == "cuda":
                try:
                    import torch
                    name = torch.cuda.get_device_name(0)
                    mem = torch.cuda.get_device_properties(0).total_memory / (1024**3)
                    print(f"   🎮 GPU: {name} ({mem:.1f} GB)")
                except Exception:
                    pass
            self.model = load_whisper_model(self.model_size, self.device)
            print("✅ Whisper 모델 로딩 완료\n")

    # ==========================================================================
    # 메인 진입점
    # ==========================================================================

    def find_anchor_and_extract_smart(self, audio_path: str) -> Tuple[bool, Optional[float], Optional[str]]:
        """
        영어 대화 구간 자동 추출.

        Returns:
            (성공 여부, 앵커 시간(초), 추출된 mp3 경로)
        """
        print(f"{'='*80}")
        print(f"🎵 파일: {os.path.basename(audio_path)}")
        print(f"{'='*80}\n")

        # 1단계: 한국어 전사
        result_ko = self._transcribe_korean(audio_path)
        base_name = Path(audio_path).stem
        self._save_transcription(result_ko, base_name)

        # 2단계: 앵커 찾기
        anchor_end_time = self._find_anchor(result_ko['segments'])
        if anchor_end_time is None:
            self._print_anchor_diagnosis(result_ko['segments'], audio_path)
            return False, None, None

        # 3단계: 음악 세그먼트 분석 (INA는 서브프로세스로 실행)
        if not HAS_INA:
            print("❌ inaSpeechSegmenter 가 필요합니다.")
            print("   pip install inaSpeechSegmenter tensorflow")
            return False, None, None

        ina_segments = self._analyze_audio_segments(audio_path, anchor_end_time)
        if not ina_segments:
            return False, None, None

        # 4단계: 시작점/종료점 결정
        extract_start = self._find_extract_start(ina_segments)
        if extract_start is None:
            return False, None, None

        extract_end = self._find_extract_end(
            ina_segments, result_ko['segments'], extract_start, anchor_end_time
        )

        # 5단계: 추출 + 결과 파일들 생성
        return self._extract_and_save(
            audio_path, base_name, result_ko,
            extract_start, extract_end, anchor_end_time
        )

    # ==========================================================================
    # 1단계: 한국어 전사
    # ==========================================================================

    def _transcribe_korean(self, audio_path: str) -> dict:
        """앵커 찾기용 한국어 전사 (search_start_time 부터)"""
        from pydub import AudioSegment
        print("🔄 1단계: 한국어 전사로 앵커 찾기...")

        audio_full = AudioSegment.from_mp3(audio_path)
        start_ms = TRANSCRIBE_START_SEC * 1000
        audio_segment = audio_full[start_ms:]

        temp_path = "temp_segment.mp3"
        audio_segment.export(temp_path, format="mp3")

        result_ko = self.model.transcribe(
            temp_path, language='ko', word_timestamps=False, verbose=False
        )

        # 시간 오프셋 보정
        for segment in result_ko['segments']:
            segment['start'] += TRANSCRIBE_START_SEC
            segment['end'] += TRANSCRIBE_START_SEC

        os.remove(temp_path)
        return result_ko

    def _save_transcription(self, result_ko: dict, base_name: str):
        """한국어 전사 결과 저장 (디버그용)"""
        path = f"transcription_{base_name}.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(result_ko, f, ensure_ascii=False, indent=2)
        print(f"💾 한국어 전사 저장: {path}\n")

    # ==========================================================================
    # 2단계: 앵커 찾기 (+ 진단)
    # ==========================================================================

    def _find_anchor(self, segments_ko: list) -> Optional[float]:
        """앵커 문구 검색 (단일 → 병합 순)"""
        min_min = ANCHOR_TIME_MIN / 60
        max_min = ANCHOR_TIME_MAX / 60
        print(f"🔍 앵커 검색 ({min_min:.0f}분~{max_min:.0f}분 범위)...")

        # 단일 세그먼트 검색
        for segment in segments_ko:
            seg_start = segment['start']
            if seg_start < ANCHOR_TIME_MIN:
                continue
            if seg_start > ANCHOR_TIME_MAX:
                break

            text = segment['text'].strip()
            for anchor in ANCHOR_PHRASES:
                # 1. 완전 일치 (빠름)
                if anchor in text:
                    end_time = segment['end']
                    print(f"✅ 앵커 발견 (일치)!")
                    print(f"   텍스트: '{text}'")
                    print(f"   시간: {end_time:.2f}초 ({end_time/60:.2f}분)\n")
                    return end_time

                # 2. N-gram 유사도 매칭 (Whisper 오타 대응)
                similarity = self._calculate_ngram_similarity(anchor, text)
                if similarity >= SIMILARITY_THRESHOLD:
                    end_time = segment['end']
                    print(f"✅ 앵커 발견 (Fuzzy: {similarity:.2f})!")
                    print(f"   패턴: '{anchor}' ↔ 텍스트: '{text}'")
                    print(f"   시간: {end_time:.2f}초 ({end_time/60:.2f}분)\n")
                    return end_time

        # 연속 세그먼트 병합 검색
        print(f"🔍 연속 세그먼트 병합 검색...")
        for i, segment in enumerate(segments_ko):
            if segment['start'] < ANCHOR_TIME_MIN:
                continue
            if segment['start'] > ANCHOR_TIME_MAX:
                break

            if i < len(segments_ko) - 2:
                combined = (
                    segment['text'] +
                    segments_ko[i+1]['text'] +
                    segments_ko[i+2]['text']
                ).strip()

                for anchor in ANCHOR_PHRASES:
                    # 1. 완전 일치
                    if anchor in combined:
                        end_time = segments_ko[i+2]['end']
                        print(f"✅ 앵커 발견 (병합 일치)!")
                        print(f"   텍스트: '{combined[:80]}'")
                        print(f"   시간: {end_time:.2f}초 ({end_time/60:.2f}분)\n")
                        return end_time

                    # 2. Fuzzy 매칭
                    similarity = self._calculate_ngram_similarity(anchor, combined)
                    if similarity >= SIMILARITY_THRESHOLD:
                        end_time = segments_ko[i+2]['end']
                        print(f"✅ 앵커 발견 (병합 Fuzzy: {similarity:.2f})!")
                        print(f"   패턴: '{anchor}' ↔ 텍스트: '{combined[:60]}...'")
                        print(f"   시간: {end_time:.2f}초 ({end_time/60:.2f}분)\n")
                        return end_time

        return None

    def _print_anchor_diagnosis(self, segments_ko: list, audio_path: str):
        """
        앵커 못 찾았을 때 진단 정보 자동 출력.

        사용자가 무엇을 보고 어떻게 패치할지 단서를 제공.
        """
        print(f"\n{'='*80}")
        print("❌ 앵커를 찾지 못했습니다")
        print(f"{'='*80}")

        # 검색 범위 확장 (진단용 ±2분)
        diag_min = ANCHOR_TIME_MIN - 120
        diag_max = ANCHOR_TIME_MAX + 120

        candidates = [s for s in segments_ko if diag_min <= s['start'] <= diag_max]

        # "전체" 또는 "대화" 가 포함된 세그먼트 찾기
        keyword_hits = []
        for seg in candidates:
            text = seg['text'].strip()
            if '전체' in text or '대화' in text:
                keyword_hits.append(seg)

        print(f"\n📋 진단 정보:")
        print(f"   현재 등록된 앵커 문구: {ANCHOR_PHRASES}")
        print(f"   검색 시간 범위: {ANCHOR_TIME_MIN/60:.0f}분~{ANCHOR_TIME_MAX/60:.0f}분")
        print(f"   진단 확장 범위: {diag_min/60:.0f}분~{diag_max/60:.0f}분")

        if keyword_hits:
            print(f"\n🎯 '전체' 또는 '대화' 포함 세그먼트 ({len(keyword_hits)}개):")
            for seg in keyword_hits[:10]:
                t = seg['start']
                print(f"   [{t/60:.2f}분 / {t:.0f}s] {seg['text'].strip()}")
            if len(keyword_hits) > 10:
                print(f"   ... 외 {len(keyword_hits)-10}개")

            print(f"\n💡 위 텍스트 중 영어 대화 시작점에 해당하는 것이 있으면:")
            print(f"   src/config.py 의 ANCHOR_PHRASES 에 추가하세요.")
        else:
            print(f"\n⚠️  '전체'/'대화' 포함 세그먼트를 찾지 못했습니다.")
            print(f"   해당 회차 transcription 을 직접 확인해 보세요:")
            print(f"   tools/find_anchor.py {audio_path}")

        # 검색 범위 안의 모든 세그먼트 (앞뒤 5개씩)
        in_range = [s for s in segments_ko
                   if ANCHOR_TIME_MIN <= s['start'] <= ANCHOR_TIME_MAX]
        if in_range:
            print(f"\n📍 검색 범위({ANCHOR_TIME_MIN/60:.0f}~{ANCHOR_TIME_MAX/60:.0f}분) 내 세그먼트 (앞부분):")
            for seg in in_range[:8]:
                t = seg['start']
                print(f"   [{t/60:.2f}분] {seg['text'].strip()[:70]}")

        print(f"\n{'='*80}\n")

    # ==========================================================================
    # 3단계: 음악/음성 분석
    # ==========================================================================

    def _analyze_audio_segments(self, audio_path: str, anchor_end_time: float) -> list:
        """inaSpeechSegmenter 로 분석 후 앵커 이후 세그먼트만 반환.

        TF(INA)와 ctranslate2(Whisper) CUDA 충돌 방지를 위해
        INA를 별도 서브프로세스(src/ina_worker.py)로 실행해 완전 격리.
        """
        import sys
        import subprocess
        import json

        print("🔄 2단계: 음악/음성 세그먼트 분석...")
        print("🎼 분석 중 (시간 걸림)...")

        import os
        sub_env = {**os.environ, "CUDA_VISIBLE_DEVICES": "-1"}

        result = subprocess.run(
            [sys.executable, "-m", "src.ina_worker", audio_path],
            capture_output=True, text=True, encoding="utf-8",
            env=sub_env
        )
        if result.returncode != 0:
            print(f"⚠️  INA 서브프로세스 오류 (exitcode {result.returncode}): {result.stderr[:200]}")
            return []

        stdout_clean = result.stdout.strip()
        first_idx = -1
        for i, c in enumerate(stdout_clean):
            if c in ['[', '{']:
                first_idx = i
                break
        last_idx = -1
        for i in range(len(stdout_clean) - 1, -1, -1):
            if stdout_clean[i] in [']', '}']:
                last_idx = i
                break

        if first_idx != -1 and last_idx != -1:
            stdout_clean = stdout_clean[first_idx:last_idx+1]

        try:
            raw = json.loads(stdout_clean)
        except json.JSONDecodeError:
            print(f"⚠️  INA 출력 파싱 실패: {result.stdout[:200]}")
            return []

        if isinstance(raw, dict) and "error" in raw:
            print(f"⚠️  INA 오류: {raw['error']}")
            return []

        ina_segments = [(seg["label"], seg["start"], seg["end"]) for seg in raw]

        target = [
            (label, start, end)
            for label, start, end in ina_segments
            if start >= anchor_end_time
        ]

        if not target:
            print("⚠️  앵커 이후 세그먼트가 없습니다.\n")
            return []

        print(f"\n📊 앵커 이후 세그먼트 (처음 30개):")
        for i, (label, start, end) in enumerate(target[:30]):
            duration = end - start
            print(f"  {i+1:2d}. {label:12s} {start:7.2f}초 ~ {end:7.2f}초 (길이: {duration:5.2f}초)")
        if len(target) > 30:
            print(f"  ... 외 {len(target)-30}개")

        return target

    # ==========================================================================
    # 4단계: 시작/종료점 결정
    # ==========================================================================

    def _find_extract_start(self, target_segments: list) -> Optional[float]:
        """추출 시작점: 앵커 이후 첫 번째 음악 (직전 음성 포함)"""
        print(f"\n🔍 추출 시작점 찾기 (앵커 이후 첫 음악)...")

        for i, (label, start, end) in enumerate(target_segments):
            if label != 'music':
                continue

            print(f"✅ 첫 음악: {start:.2f}초 ({start/60:.2f}분)")
            extract_start = start

            # 음악 직전 음성 세그먼트들도 포함
            for j in range(i-1, -1, -1):
                prev_label, prev_start, prev_end = target_segments[j]
                if prev_label in ['male', 'female']:
                    extract_start = prev_start
                    print(f"   ✅ 직전 음성 발견: {prev_label} {prev_start:.2f}초")
                elif prev_label == 'noEnergy':
                    continue
                else:
                    break

            print(f"   🏁 시작점: {extract_start:.2f}초 ({extract_start/60:.2f}분)")
            return extract_start

        print("❌ 앵커 이후 음악이 없습니다.\n")
        return None

    def _find_extract_end(self, target_segments: list, segments_ko: list,
                         extract_start: float, anchor_end_time: float) -> float:
        """
        추출 종료점: 영어가 끝나고 한국어 설명이 시작되는 지점.

        두 가지 신호:
          1. 명시적 종료 문구 ("입영작" 등)
          2. 연속된 한국어 세그먼트 (3개 이상 5초 이내 간격, 다양성 OK)
        """
        print(f"\n🔍 추출 종료점 찾기...")

        # 앵커 이후 한국어 세그먼트 (충분히 한국어인 것만)
        ko_after_anchor = [
            (s['start'], s['end'], s['text'])
            for s in segments_ko
            if s['start'] > anchor_end_time + 5 and self._is_mostly_korean(s['text'])
        ]
        print(f"  한국어 세그먼트: {len(ko_after_anchor)}개")

        music_segments = [(s, e) for label, s, e in target_segments if label == 'music']
        print(f"  음악 세그먼트: {len(music_segments)}개")

        # 두 신호 중 빠른 것 선택
        teacher_start = self._find_teacher_explanation_start(ko_after_anchor, extract_start)
        explicit_stop = self._find_explicit_stop_phrase(ko_after_anchor)

        if teacher_start and explicit_stop:
            teacher_start = min(teacher_start, explicit_stop)
        elif explicit_stop:
            teacher_start = explicit_stop

        # 종료점 결정
        extract_end = None
        if teacher_start:
            for label, start, end in target_segments:
                if start < extract_start:
                    continue
                if end > teacher_start:
                    if start < teacher_start:
                        extract_end = teacher_start
                        print(f"  ✂️  세그먼트 중간 자르기: {start:.1f}s ~ {teacher_start:.1f}s")
                    else:
                        extract_end = end
                    print(f"  ⏹️  종료점: {extract_end:.2f}초")
                    break

        # Fallback: 60초 또는 마지막 음악
        if extract_end is None:
            fallback_end = extract_start + 60
            for music_start, music_end in reversed(music_segments):
                if music_end <= fallback_end:
                    extract_end = music_end
                    print(f"  ⚠️  Fallback (60초 내 마지막 음악): {music_end:.2f}초")
                    break
            if extract_end is None:
                extract_end = fallback_end
                print(f"  ⚠️  Fallback (60초 제한): {extract_end:.2f}초")

        return extract_end

    def _find_teacher_explanation_start(self, ko_segments: list,
                                       extract_start: float) -> Optional[float]:
        """연속된 한국어 = 진짜 선생님 설명.

        extract_start 기준으로 최소 대기 시간 적용.
        Whisper 음악 구간 환각(짧은 노이즈 세그먼트)을 최소 발화 시간으로 필터링.
        """
        MIN_SEG_DURATION = 0.5  # 이보다 짧은 세그먼트는 Whisper 환각으로 간주 (네, 오케이 등 짦은 발화 정상 수용)

        for i in range(len(ko_segments) - 2):
            s1, e1, t1 = ko_segments[i]
            s2, e2, t2 = ko_segments[i + 1]
            s3, e3, t3 = ko_segments[i + 2]

            if s1 < extract_start + MIN_ENGLISH_DURATION_AFTER_ANCHOR:
                continue

            # 너무 짧은 세그먼트는 음악 구간에서 나온 환각 (ex: "한 잔 у")
            if (e1 - s1) < MIN_SEG_DURATION or (e2 - s2) < MIN_SEG_DURATION or (e3 - s3) < MIN_SEG_DURATION:
                continue

            gap1 = s2 - s1
            gap2 = s3 - s2

            # 환각 방지: 비슷한 문장 반복은 거름
            def sim(a, b):
                return SequenceMatcher(None, a, b).ratio()
            is_repetitive = sim(t1, t2) > 0.8 or sim(t2, t3) > 0.8

            if gap1 <= 6.0 and gap2 <= 6.0 and not is_repetitive:
                print(f"\n  📍 진짜 한국어 설명 감지:")
                print(f"    [{s1:.1f}s] {t1[:30]}")
                print(f"    [{s2:.1f}s] {t2[:30]} (gap: {gap1:.1f}s)")
                print(f"    [{s3:.1f}s] {t3[:30]} (gap: {gap2:.1f}s)")
                return s1

        return None

    def _find_explicit_stop_phrase(self, ko_segments: list) -> Optional[float]:
        """명시적 종료 문구 검색 (Fuzzy 매칭 포함)"""
        for start, end, text in ko_segments:
            for phrase in END_PHRASES:
                # 완전 일치
                if phrase in text:
                    print(f"\n  🛑 명시적 종료 문구: '{phrase}' [{start:.1f}s]")
                    return start

                # Fuzzy 매칭
                similarity = self._calculate_ngram_similarity(phrase, text)
                if similarity >= SIMILARITY_THRESHOLD:
                    print(f"\n  🛑 명시적 종료 문구 (Fuzzy: {similarity:.2f}): '{phrase}' ↔ '{text}' [{start:.1f}s]")
                    return start
        return None

    # ==========================================================================
    # 5단계: 추출 + 결과 저장
    # ==========================================================================

    def _extract_and_save(self, audio_path, base_name, result_ko,
                         extract_start, extract_end, anchor_end_time):
        """오디오 추출 + 영어 재전사 + 스크립트 + 플레이어 JSON

        흐름:
          1. MP3 자르기
          2. 추출된 MP3 만 영어로 재전사 (고품질, 정확함)
          3. 영어 전사 결과로 스크립트 + 플레이어 JSON 동시 생성
        """
        duration = extract_end - extract_start
        print(f"\n✂️  구간 추출:")
        print(f"   {extract_start:.2f}초 ({extract_start/60:.2f}분) ~ "
              f"{extract_end:.2f}초 ({extract_end/60:.2f}분)")
        print(f"   길이: {duration:.2f}초")

        if duration < EXTRACT_MIN_DURATION:
            print(f"   ⚠️  매우 짧음 ({duration:.1f}초 < {EXTRACT_MIN_DURATION}초)")
        elif duration > EXTRACT_MAX_DURATION:
            print(f"   ⚠️  매우 긺 ({duration:.1f}초 > {EXTRACT_MAX_DURATION}초)")
        print()

        # 1. MP3 추출
        from pydub import AudioSegment
        audio_full = AudioSegment.from_mp3(audio_path)
        start_ms = int(extract_start * 1000)
        end_ms = int(extract_end * 1000)
        extracted = audio_full[start_ms:end_ms]

        # 모노 변환 (영어 학습용 — 음성만 명확하면 충분)
        extracted_mono = extracted.set_channels(1).set_frame_rate(22050)

        output_path = f"extracted_{base_name}.mp3"
        print(f"💾 저장: {output_path}")
        extracted_mono.export(
            output_path,
            format='mp3',
            bitrate='64k',
            parameters=["-ac", "1", "-ar", "22050"],
        )
        actual_duration = len(extracted) / 1000
        size_kb = Path(output_path).stat().st_size / 1024
        print(f"✅ {actual_duration:.1f}초 추출 완료 ({size_kb:.0f} KB, 64k 모노)\n")

        # 2. 추출된 부분만 영어 고품질 재전사
        print(f"🔄 영어 고품질 전사 중...")
        result_en = self.model.transcribe(
            output_path, language='en', word_timestamps=False, verbose=False
        )

        # 3. 영어 전사 결과를 정제 (한국어/종결문구 필터 + 중복 제거)
        clean_segments = self._clean_english_segments(result_en, actual_duration)

        # 3.5. 한국어 해석 추가 (공식 강의안 PDF 매칭 우선, 없을 시 자동 번역 Fallback)
        self._add_korean_translations(clean_segments, base_name)

        # 4. 선생님 영어 메타 문구 감지 → 오디오 + 스크립트 재트리밍
        trim_time = self._apply_teacher_phrase_trim(clean_segments, extracted_mono, output_path)
        if trim_time is not None:
            actual_duration = trim_time
            extract_end = extract_start + trim_time

        # 5. 스크립트 (txt) + 플레이어 JSON (같은 데이터 재사용)
        self._save_script_from_segments(
            clean_segments, base_name, audio_path,
            extract_start, extract_end, actual_duration
        )
        self._save_player_json_from_segments(
            clean_segments, output_path, base_name
        )

        return True, anchor_end_time, output_path

    def _apply_teacher_phrase_trim(self, clean_data: dict, extracted_mono,
                                   output_path: str) -> Optional[float]:
        """선생님 영어 메타 문구 감지 → 스크립트 + 오디오 재트리밍.

        EBS 진행자가 대화 후 드릴/미션으로 전환할 때 쓰는 고유 문구를
        영어 전사 결과에서 탐지. 탐지 시 해당 지점에서 오디오와 스크립트 모두 잘라냄.
        """
        segments = clean_data["segments"]

        for i, seg in enumerate(segments):
            text_lower = seg['text'].lower()
            for phrase in TEACHER_EN_PHRASES:
                if phrase in text_lower:
                    trim_time = seg['start']
                    if trim_time < 10.0:
                        # 10초 미만에 나오면 실제 대화일 가능성 → 무시
                        continue
                    print(f"\n  ✂️  선생님 전환 문구 감지 [{trim_time:.1f}s]: '{seg['text']}'")
                    clean_data["segments"] = segments[:i]
                    trimmed = extracted_mono[:int(trim_time * 1000)]
                    trimmed.export(
                        output_path,
                        format='mp3',
                        bitrate='64k',
                        parameters=["-ac", "1", "-ar", "22050"],
                    )
                    print(f"     → {trim_time:.1f}초로 재트리밍 완료")
                    return trim_time

        return None

    def _clean_english_segments(self, result_en, actual_duration):
        """영어 전사 결과 정제 (중복 및 겹침 제거)"""
        raw_segments = result_en['segments']
        clean = []
        
        dup_count = 0
        ko_filtered = 0
        internal_rep_count = 0
        overlap_fix_count = 0

        for seg in raw_segments:
            text = seg['text'].strip()
            if not text:
                continue

            # 1. 한국어 문자 제거
            original_text = text
            text = "".join(c for c in text if not ('가' <= c <= '힣')).strip()
            if not any(c.isalpha() for c in text):
                ko_filtered += 1
                continue

            # 2. 내부 중복 제거 (예: "Hello Hello" -> "Hello")
            if len(text) > 10:
                mid = len(text) // 2
                first_half = text[:mid].strip().lower()
                second_half = text[mid:].strip().lower()
                if self._calculate_ngram_similarity(first_half, second_half) > 0.8:
                    text = text[:mid].strip()
                    internal_rep_count += 1

            # 3. 앞 세그먼트와의 경계 겹침(Overlap) 제거
            if clean:
                prev_text = clean[-1]['text']
                # SequenceMatcher로 겹치는 부분 찾기
                s = SequenceMatcher(None, prev_text.lower(), text.lower())
                match = s.find_longest_match(0, len(prev_text), 0, len(text))
                
                # 겹치는 부분이 앞 세그먼트의 끝 + 뒤 세그먼트의 시작일 경우
                if match.size >= 3:  # 최소 3글자 이상 겹칠 때
                    # 겹치는 위치가 경계면인지 확인
                    if (match.a + match.size == len(prev_text)) and (match.b == 0):
                        overlap_text = text[:match.size]
                        remaining_text = text[match.size:]
                        
                        # [개선] 단어 중간이 잘리는지 확인 (Word Boundary check)
                        # 남은 텍스트의 시작이 글자이고, 겹친 텍스트의 끝이 글자이면 단어 중간임
                        is_word_split = (
                            remaining_text and 
                            remaining_text[0].isalnum() and 
                            overlap_text[-1].isalnum()
                        )
                        
                        if is_word_split:
                            # 단어 중간이면 자르지 않음 (Whisper 환각보다는 단어 깨짐이 더 치명적)
                            pass
                        else:
                            # 뒤 세그먼트에서 겹치는 만큼 제거
                            text = remaining_text.strip()
                            overlap_fix_count += 1
                    elif (match.a == 0) and (match.b + match.size == len(text)):
                        # 앞 세그먼트 전체가 뒤에 포함되는 경우 (완전 중복)
                        # 이건 아래 4번에서 걸러짐
                        pass

            if not text:
                dup_count += 1
                continue

            # 4. 전체 문장 유사도 체크 (최종 중복 필터)
            is_full_dup = False
            # 이전 10개 세그먼트까지 검사 (반복되는 대화 블록 대응)
            for c_seg in clean[-10:]:
                if self._calculate_ngram_similarity(text.lower(), c_seg['text'].lower()) > 0.85:
                    is_full_dup = True
                    break
            
            if is_full_dup:
                dup_count += 1
                continue

            # 5. 종료 문구 필터
            if any(end_phrase in original_text for end_phrase in END_PHRASES):
                ko_filtered += 1
                continue

            rel_start = max(0, float(seg['start']))
            rel_end = min(actual_duration, float(seg['end']))

            clean.append({
                "start": round(rel_start, 2),
                "end": round(rel_end, 2),
                "text": text,
            })

        # 통계
        clean_meta = {
            "duplicates_removed": dup_count,
            "korean_filtered": ko_filtered,
            "internal_repetitions_fixed": internal_rep_count,
            "overlap_fixed": overlap_fix_count,
            "total_segments": len(clean),
        }

        return {"segments": clean, "meta": clean_meta}

    def _add_korean_translations(self, clean_data: dict, base_name: str):
        """영어 세그먼트에 한국어 번역 추가 (공식 PDF 강의안 매칭 우선, 없을 시 deep-translator 사용)"""
        import re
        from difflib import SequenceMatcher
        from src.pdf_parser import get_parsed_lecture

        # 1. base_name에서 에피소드 회차 번호 정교한 추출
        ep_num = None
        
        # 1-1. 날짜 기반 매칭 (예: 20260526) -> .episode_info 참고
        date_match = re.search(r'(\d{8})', base_name)
        if date_match:
            file_date = date_match.group(1)
            info_dir = Path(__file__).parent.parent.resolve() / ".episode_info"
            if info_dir.exists():
                for info_file in info_dir.glob("*.json"):
                    try:
                        with open(info_file, 'r', encoding='utf-8') as f:
                            info = json.load(f)
                        if info.get('air_date_compact') == file_date:
                            ep_num = str(info.get('episode'))
                            print(f"   [TRANS] 파일 날짜 {file_date} 기반 회차 정보 매핑 성공: {ep_num}회")
                            break
                    except Exception:
                        continue

        # 1-2. 날짜 매칭 실패 시, 4자리 회차 번호 직접 추출 (연도 2026 제외 및 2600~2800 범위 제한)
        if not ep_num:
            all_nums = re.findall(r'\d{4}', base_name)
            for num in all_nums:
                if 2600 <= int(num) <= 2800:
                    ep_num = num
                    print(f"   [TRANS] 파일명 4자리 숫자 기반 회차 정보 매핑 성공: {ep_num}회")
                    break

        parsed_lecture = None
        if ep_num:
            print(f"   [TRANS] {ep_num}회 공식 강의안 번역 매핑 매칭 시도...")
            parsed_lecture = get_parsed_lecture(ep_num)

        # 2. 공식 교안이 존재할 경우 Fuzzy Match 진행
        if parsed_lecture:
            matched_count = 0
            for p_seg in clean_data["segments"]:
                eng_text = p_seg["text"].strip()
                if not eng_text:
                    continue

                best_match = None
                best_ratio = 0.0

                # PDF의 공식 문장과 전사 문장 유사도 비교
                for pdf_item in parsed_lecture:
                    # 빈칸 '____' 문구는 유사도 계산 시 노이즈이므로 제거하고 매칭력 극대화
                    pdf_eng_clean = re.sub(r'_{2,}', '', pdf_item["english_raw"].lower())
                    pdf_eng_clean = re.sub(r'[^a-zA-Z0-9\s]', '', pdf_eng_clean)
                    
                    eng_clean = re.sub(r'[^a-zA-Z0-9\s]', '', eng_text.lower())

                    ratio = SequenceMatcher(None, eng_clean, pdf_eng_clean).ratio()
                    if ratio > best_ratio:
                        best_ratio = ratio
                        best_match = pdf_item

                # 유사도 임계치 0.65 이상일 경우 매칭 확정
                if best_ratio >= 0.65 and best_match:
                    ko_official = best_match["korean_official"]
                    p_seg["text"] = f"{eng_text} {ko_official}"
                    matched_count += 1
                    print(f"      [MATCH] '{eng_text[:30]}...' ↔ 공식 번역: '{ko_official}' (유사도: {best_ratio:.2f})")
                else:
                    # 매칭 실패 시 기계 번역 Fallback
                    try:
                        from deep_translator import GoogleTranslator
                        translator = GoogleTranslator(source='en', target='ko')
                        ko_text = translator.translate(eng_text)
                        p_seg["text"] = f"{eng_text} {ko_text}"
                    except Exception as e:
                        print(f"      [Fallback 번역 오류] {eng_text} - {e}")

            print(f"   [TRANS] 공식 번역 매핑 성공: {matched_count}/{len(clean_data['segments'])}개 세그먼트")
            return

        # 3. 공식 교안이 없는 경우 기존 기계 번역 실행 (Fallback)
        print("   [TRANS] 공식 강의안이 없어 기계 번역(GoogleTranslator)을 적용합니다.")
        try:
            from deep_translator import GoogleTranslator
            translator = GoogleTranslator(source='en', target='ko')
            
            for p_seg in clean_data["segments"]:
                eng_text = p_seg["text"].strip()
                if not eng_text:
                    continue
                
                # 이미 한국어가 섞여있는지 확인
                if sum(1 for c in eng_text if '가' <= c <= '힣') > 0:
                    continue
                    
                try:
                    ko_text = translator.translate(eng_text)
                    p_seg["text"] = f"{eng_text} {ko_text}"
                except Exception as e:
                    print(f"  [번역 오류] {eng_text} - {e}")
        except ImportError:
            print("  [경고] deep_translator 패키지가 설치되지 않아 번역을 추가할 수 없습니다.")
            print("  설치: pip install deep-translator")

    def _save_script_from_segments(self, clean_data, base_name, audio_path,
                                   extract_start, extract_end, actual_duration):
        """정제된 세그먼트로 txt 스크립트 저장"""
        script_path = f"script_{base_name}.txt"
        segments = clean_data["segments"]
        meta = clean_data["meta"]

        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(f"{'='*80}\n")
            f.write(f"대화 스크립트: {os.path.basename(audio_path)}\n")
            f.write(f"{'='*80}\n")
            f.write(f"원본 구간: {extract_start:.2f}초 ~ {extract_end:.2f}초 (원본 30분 mp3 기준)\n")
            f.write(f"추출 MP3 길이: {actual_duration:.2f}초 ({actual_duration/60:.2f}분)\n")
            f.write(f"시간 기준: 추출 MP3 시작점(0초)\n")
            f.write(f"{'='*80}\n\n")

            if segments:
                for s in segments:
                    timestamp = f"[{s['start']:>6.2f}s - {s['end']:>6.2f}s]"
                    f.write(f"{timestamp} {s['text']}\n")
            else:
                f.write("(영어 대화 인식 결과 없음)\n")

            footer_parts = []
            if meta["duplicates_removed"] > 0:
                footer_parts.append(f"중복 제거: {meta['duplicates_removed']}개")
            if meta["korean_filtered"] > 0:
                footer_parts.append(f"한국어/종결문구 필터: {meta['korean_filtered']}개")
            if meta.get("internal_repetitions_fixed", 0) > 0:
                footer_parts.append(f"내부 중복 수정: {meta['internal_repetitions_fixed']}개")
            if meta.get("overlap_fixed", 0) > 0:
                footer_parts.append(f"경계 겹침 수정: {meta['overlap_fixed']}개")
            if footer_parts:
                f.write(f"\n({', '.join(footer_parts)})\n")

        print(f"📝 스크립트 저장: {script_path}")
        print(f"   영어 대사 {len(segments)}줄 (중복 {meta['duplicates_removed']}, "
              f"한국어 필터 {meta['korean_filtered']})\n")

    def _save_player_json_from_segments(self, clean_data, output_path, base_name):
        """정제된 세그먼트로 플레이어 JSON 저장"""
        player_path = f"player_{base_name}.json"
        with open(player_path, 'w', encoding='utf-8') as f:
            json.dump({
                "audio": output_path,
                "script": clean_data["segments"],
            }, f, ensure_ascii=False, indent=2)

        print(f"📱 플레이어 JSON 저장: {player_path}\n")

    # ==========================================================================
    # 유틸리티
    # ==========================================================================

    @staticmethod
    def _is_mostly_korean(text: str) -> bool:
        """절반 이상이 한글이면 True"""
        korean = sum(1 for c in text if '가' <= c <= '힣')
        total = sum(1 for c in text if not c.isspace())
        return total > 0 and korean / total > 0.5

    @staticmethod
    def _calculate_ngram_similarity(s1: str, s2: str, n: Optional[int] = None) -> float:
        """
        문자 레벨 N-gram 유사도 (Sørensen–Dice coefficient).
        "전체대화" ↔ "전체대와" 같은 오타를 잡기 위함.
        """
        n = n or NGRAM_N

        def get_ngrams(text: str, n_val: int):
            text = text.replace(" ", "").lower()
            if len(text) < n_val:
                return set(text)
            return {text[i:i+n_val] for i in range(len(text)-n_val+1)}

        b1 = get_ngrams(s1, n)
        b2 = get_ngrams(s2, n)

        if not b1 or not b2:
            return 0.0

        intersection = b1.intersection(b2)
        return 2.0 * len(intersection) / (len(b1) + len(b2))
