"""
개선된 EBS 영어 대화 추출 스크립트
- 앵커 검색 범위: 22분~24분
- 개선된 시작/종료점 감지
"""
import whisper
import os
from pydub import AudioSegment
import json
from pathlib import Path
import argparse

try:
    from inaSpeechSegmenter import Segmenter
    HAS_INA = True
except ImportError:
    HAS_INA = False


class ImprovedExtractor:
    def __init__(self, model_size='tiny'):
        self.model_size = model_size
        self.model = None
        self.segmenter = None
    
    def load_models(self):
        """모델 로딩"""
        if self.model is None:
            print(f"🔄 Whisper 모델 로딩 중... (모델: {self.model_size})")
            self.model = whisper.load_model(self.model_size)
            print("✅ Whisper 모델 로딩 완료\n")
        
        if HAS_INA and self.segmenter is None:
            print("🔄 inaSpeechSegmenter 모델 로딩 중...")
            self.segmenter = Segmenter()
            print("✅ inaSpeechSegmenter 모델 로딩 완료\n")
    
    def _is_korean(self, text):
        """한글 포함 여부 확인"""
        return any('가' <= c <= '힣' for c in text)
    
    def extract_script_text(self, transcription, start_time, end_time, deduplicate=True):
        """스크립트 추출 (중복 제거)"""
        script_lines = []
        seen_texts = set()
        duplicate_count = 0
        
        for segment in transcription['segments']:
            seg_start = segment['start']
            seg_end = segment['end']
            
            if seg_start <= end_time and seg_end >= start_time:
                text = segment['text'].strip()
                
                if deduplicate:
                    normalized = text.lower().strip()
                    if normalized in seen_texts:
                        duplicate_count += 1
                        continue
                    seen_texts.add(normalized)
                
                timestamp = f"[{seg_start/60:.2f}분 - {seg_end/60:.2f}분]"
                script_lines.append(f"{timestamp} {text}")
        
        result = "\n".join(script_lines)
        if deduplicate and duplicate_count > 0:
            result += f"\n\n(중복 제거: {duplicate_count}개 문장)"
        
        return result
    
    def extract_player_data(self, transcription, start_time, end_time, deduplicate=True):
        """플레이어 데이터 추출 (중복 제거)"""
        player_data = []
        seen_texts = set()
        
        for segment in transcription['segments']:
            seg_start = segment['start']
            seg_end = segment['end']
            
            if seg_start <= end_time and seg_end >= start_time:
                text = segment['text'].strip()
                
                if deduplicate:
                    normalized = text.lower().strip()
                    if normalized in seen_texts:
                        continue
                    seen_texts.add(normalized)
                
                rel_start = max(0, seg_start - start_time)
                rel_end = min(end_time - start_time, seg_end - start_time)
                
                player_data.append({
                    "start": round(rel_start, 2),
                    "end": round(rel_end, 2),
                    "text": text
                })
        
        return player_data
    
    def extract_conversation(self, audio_path):
        """대화 추출 메인 함수"""
        print(f"{'='*80}")
        print(f"🎵 파일: {os.path.basename(audio_path)}")
        print(f"{'='*80}\n")
        
        # 오디오 로딩
        audio_full = AudioSegment.from_mp3(audio_path)
        
        # 21분 40초부터 전사 시작
        search_start_time = 1300  # 21분 40초
        start_ms = search_start_time * 1000
        audio_segment = audio_full[start_ms:]
        
        # 임시 파일로 저장
        temp_path = "temp_segment.mp3"
        audio_segment.export(temp_path, format="mp3")
        
        # 1단계: 한국어 전사로 앵커 찾기
        print(f"🔄 1단계: 한국어 전사로 앵커 찾기...")
        result_ko = self.model.transcribe(
            temp_path,
            language='ko',
            word_timestamps=False,
            verbose=False
        )
        
        # 시간 오프셋 보정
        for segment in result_ko['segments']:
            segment['start'] += search_start_time
            segment['end'] += search_start_time
        
        os.remove(temp_path)
        
        # 전사 결과 저장
        base_name = Path(audio_path).stem
        transcription_path = f"transcription_{base_name}.json"
        with open(transcription_path, 'w', encoding='utf-8') as f:
            json.dump(result_ko, f, ensure_ascii=False, indent=2)
        print(f"💾 한국어 전사 결과 저장: {transcription_path}\n")
        
        # 2. 앵커 검색 (22분~24분 범위)
        print(f"🔍 앵커 문구 검색 중 (22분~24분 범위)...")
        anchor_end_time = None
        segments_ko = result_ko['segments']
        
        MIN_ANCHOR_TIME = 1320  # 22분
        MAX_ANCHOR_TIME = 1440  # 24분
        
        anchor_phrases = ["주세요", "전체대화 주세요", "전체대화", "전체 대화"]
        
        # 단일 세그먼트 검색
        for segment in segments_ko:
            seg_start = segment['start']
            
            if seg_start < MIN_ANCHOR_TIME:
                continue
            if seg_start > MAX_ANCHOR_TIME:
                break
            
            text = segment['text'].strip()
            
            for anchor in anchor_phrases:
                if anchor in text:
                    anchor_end_time = segment['end']
                    print(f"✅ 앵커 발견!")
                    print(f"   텍스트: '{text}'")
                    print(f"   시간: {anchor_end_time:.2f}초 ({anchor_end_time/60:.2f}분)\n")
                    break
            
            if anchor_end_time:
                break
        
        if anchor_end_time is None:
            print(f"❌ 앵커를 찾지 못했습니다\n")
            return False, None, None
        
        # 3. 음악/음성 세그먼트 분석
        print(f"🔄 2단계: 음악 기반 추출...")
        
        if not HAS_INA or self.segmenter is None:
            print("❌ inaSpeechSegmenter가 필요합니다.")
            return False, None, None
        
        print("🎼 음악 및 음성 세그먼트 분석 중...")
        ina_segments = self.segmenter(audio_path)
        
        # 앵커 이후 세그먼트만 필터링
        target_segments = [(label, start, end) for label, start, end in ina_segments if start >= anchor_end_time]
        
        if not target_segments:
            print("⚠️  앵커 이후 세그먼트를 찾지 못했습니다.\n")
            return False, None, None
        
        print(f"\n📊 앵커 이후 세그먼트 (처음 30개):")
        for i, (label, start, end) in enumerate(target_segments[:30]):
            duration = end - start
            print(f"  {i+1:2d}. {label:12s} {start:7.2f}초 ~ {end:7.2f}초 (길이: {duration:5.2f}초)")
        if len(target_segments) > 30:
            print(f"  ... 외 {len(target_segments)-30}개 세그먼트")
        
        # 4. 추출 시작점 찾기
        extract_start = None
        
        print(f"\n🔍 추출 시작점 찾기 (앵커 이후 첫 음악)...")
        for i, (label, start, end) in enumerate(target_segments):
            if label == 'music':
                print(f"✅ 첫 음악 발견: {start:.2f}초 ({start/60:.2f}분)")
                
                # 음악 이전에 음성 세그먼트가 있는지 확인
                extract_start = start
                
                for j in range(i-1, -1, -1):
                    prev_label, prev_start, prev_end = target_segments[j]
                    if prev_label in ['male', 'female']:
                        extract_start = prev_start
                        print(f"   ✅ 음악 이전 음성 발견: {prev_label} {prev_start:.2f}초")
                    elif prev_label == 'noEnergy':
                        continue
                    else:
                        break
                
                print(f"   🏁 최종 시작점: {extract_start:.2f}초 ({extract_start/60:.2f}분)")
                break
        
        if extract_start is None:
            print("❌ 앵커 이후 음악을 찾지 못했습니다.\n")
            return False, None, None
        
        # 5. 추출 종료점 찾기
        print(f"\n🔍 추출 종료점 찾기 (선생님 설명 시작 전 마지막 음성)...")
        
        extract_end = None
        
        # 선생님 설명 시작 키워드
        teacher_keywords = [
            '입영작', '입으로', '영작', '타임', '패턴',
            '만나볼까요', '읽어볼게요', '듣겠습니다',
            '여러분', '활용', '갈게요'
        ]
        
        # 한국어 세그먼트 수집 및 선생님 설명 시작점 찾기
        korean_segments_after_anchor = [
            (seg['start'], seg['end'], seg['text']) 
            for seg in result_ko['segments'] 
            if seg['start'] > anchor_end_time + 10 and self._is_korean(seg['text'])
        ]
        
        print(f"  한국어 세그먼트 {len(korean_segments_after_anchor)}개 발견")
        
        # 선생님 설명 시작점 찾기
        teacher_start_time = None
        for ko_start, ko_end, ko_text in korean_segments_after_anchor:
            # 키워드 체크
            for keyword in teacher_keywords:
                if keyword in ko_text:
                    teacher_start_time = ko_start
                    print(f"  ✅ 선생님 설명 감지:")
                    print(f"     시작: {ko_start:.2f}s ({ko_start/60:.2f}분)")
                    print(f"     텍스트: '{ko_text[:50]}'")
                    break
            
            if teacher_start_time:
                break
        
        if teacher_start_time:
            # 선생님 설명 시작 전 마지막 음성(male/female) 세그먼트 찾기
            # 음악이 아닌 실제 대화를 기준으로 종료
            for label, start, end in reversed(target_segments):
                if label in ['male', 'female'] and end <= teacher_start_time:
                    extract_end = end
                    print(f"  ✅ 종료점 발견:")
                    print(f"     마지막 음성: {label} {start:.2f}s ~ {end:.2f}s")
                    print(f"     선생님 설명까지 간격: {teacher_start_time - end:.1f}초")
                    break
        
        # Fallback: 선생님 설명을 못 찾은 경우
        if extract_end is None:
            print(f"  ⚠️  선생님 설명 키워드를 찾지 못했습니다.")
            
            # 시작 후 60초 이내 마지막 음성 사용
            fallback_end = extract_start + 60
            for label, start, end in reversed(target_segments):
                if label in ['male', 'female'] and end <= fallback_end:
                    extract_end = end
                    print(f"  ⚠️  Fallback: 시작 후 60초 이내 마지막 음성 사용")
                    print(f"     종료: {end:.2f}초 ({end/60:.2f}분)")
                    break
            
            if extract_end is None:
                extract_end = fallback_end
                print(f"  ⚠️  Fallback: 시작 후 60초로 제한")
        
        # 6. 오디오 추출
        duration = extract_end - extract_start
        print(f"\n✂️  구간 추출:")
        print(f"   시작: {extract_start:.2f}초 ({extract_start/60:.2f}분)")
        print(f"   종료: {extract_end:.2f}초 ({extract_end/60:.2f}분)")
        print(f"   길이: {duration:.2f}초")
        
        if duration < 20:
            print(f"   ⚠️  경고: 추출 길이가 매우 짧습니다 ({duration:.1f}초 < 20초)")
        elif duration > 90:
            print(f"   ⚠️  경고: 추출 길이가 매우 깁니다 ({duration:.1f}초 > 90초)")
        print()
        
        start_ms = int(extract_start * 1000)
        end_ms = int(extract_end * 1000)
        
        extracted = audio_full[start_ms:end_ms]
        
        # MP3 저장
        output_path = f"extracted_{base_name}.mp3"
        print(f"💾 저장 중: {output_path}")
        extracted.export(output_path, format='mp3', bitrate='320k', parameters=["-q:a", "0"])
        
        actual_duration = len(extracted) / 1000
        print(f"✅ 추출 완료: {actual_duration:.1f}초\n")
        
        # 7. 스크립트 저장
        script_text = self.extract_script_text(result_ko, extract_start, extract_end)
        script_path = f"script_{base_name}.txt"
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(f"{'='*80}\n")
            f.write(f"대화 스크립트: {os.path.basename(audio_path)}\n")
            f.write(f"{'='*80}\n")
            f.write(f"구간: {extract_start:.2f}초 ~ {extract_end:.2f}초 ({duration:.2f}초)\n")
            f.write(f"{'='*80}\n\n")
            f.write(script_text)
        
        print(f"📝 대화 스크립트 저장: {script_path}\n")
        
        # 8. 영어 전사 및 플레이어 데이터
        print(f"🔄 원어민 대화 고품질 영어 전사 중...")
        result_en = self.model.transcribe(output_path, language='en', word_timestamps=False, verbose=False)
        
        player_data = self.extract_player_data(result_en, 0, actual_duration)
        player_json_path = f"player_{base_name}.json"
        with open(player_json_path, 'w', encoding='utf-8') as f:
            json.dump({"audio": output_path, "script": player_data}, f, ensure_ascii=False, indent=2)
        print(f"📱 웹 플레이어 데이터 저장(영어): {player_json_path}\n")
        
        return True, anchor_end_time, output_path


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='개선된 EBS 영어 대화 추출')
    parser.add_argument('--file', '-f', type=str, required=True, help='처리할 MP3 파일 경로')
    parser.add_argument('--model', type=str, default='tiny', choices=['tiny', 'base', 'small', 'medium', 'large'],
                       help='Whisper 모델 크기 (기본: tiny)')
    
    args = parser.parse_args()
    
    if not HAS_INA:
        print("="*80)
        print("WARNING: inaSpeechSegmenter가 설치되지 않았습니다")
        print("="*80)
        print("\n다음 명령으로 설치하세요:")
        print("  pip install inaSpeechSegmenter tensorflow\n")
        return
    
    if not os.path.exists(args.file):
        print(f"❌ 파일을 찾을 수 없습니다: {args.file}")
        return
    
    extractor = ImprovedExtractor(model_size=args.model)
    extractor.load_models()
    success, anchor_time, output_path = extractor.extract_conversation(args.file)
    
    if success:
        print(f"\n✅ 처리 완료!")
        print(f"   출력 파일: {output_path}")
    else:
        print("\n❌ 처리 실패")


if __name__ == "__main__":
    main()
