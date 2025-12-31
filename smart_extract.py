"""
음악 기반 지능형 추출 스크립트 (개선 버전)

기능:
- 음악과 음성 자동 인식 및 정확한 추출
- 대화 스크립트 텍스트 추출
- 23분부터 전사 (속도 향상)
- 단일 파일 처리 지원
"""

import whisper
import os
import glob
from pydub import AudioSegment
import json
from pathlib import Path
import argparse

try:
    from inaSpeechSegmenter import Segmenter
    HAS_INA = True
except ImportError:
    HAS_INA = False


class SmartConversationExtractor:
    def __init__(self, model_size='tiny'):
        self.model_size = model_size
        self.model = None
        self.segmenter = None
        
    def load_models(self):
        """Whisper 및 inaSpeechSegmenter 로딩"""
        if self.model is None:
            print(f"🔄 Whisper 모델 로딩 중... (모델: {self.model_size})")
            self.model = whisper.load_model(self.model_size)
            print("✅ Whisper 모델 로딩 완료\n")
        
        if HAS_INA and self.segmenter is None:
            print("🔄 inaSpeechSegmenter 모델 로딩 중...")
            self.segmenter = Segmenter()
            print("✅ inaSpeechSegmenter 모델 로딩 완료\n")
    
    def extract_script_text(self, transcription, start_time, end_time):
        """
        지정된 시간 범위의 대화 스크립트 추출
        
        Args:
            transcription: Whisper 전사 결과
            start_time: 시작 시간 (초)
            end_time: 종료 시간 (초)
            
        Returns:
            대화 스크립트 텍스트
        """
        script_lines = []
        
        for segment in transcription['segments']:
            seg_start = segment['start']
            seg_end = segment['end']
            
            # 추출 구간과 겹치는 세그먼트만
            if seg_start <= end_time and seg_end >= start_time:
                timestamp = f"[{seg_start/60:.2f}분 - {seg_end/60:.2f}분]"
                text = segment['text'].strip()
                script_lines.append(f"{timestamp} {text}")
        
        return "\n".join(script_lines)

    def extract_player_data(self, transcription, start_time, end_time):
        """
        웹 플레이어용 데이터 추출 (상대 시간)
        """
        player_data = []
        
        for segment in transcription['segments']:
            seg_start = segment['start']
            seg_end = segment['end']
            
            if seg_start <= end_time and seg_end >= start_time:
                # 상대 시간 계산 (추출된 오디오의 시작이 0초)
                rel_start = max(0, seg_start - start_time)
                rel_end = min(end_time - start_time, seg_end - start_time)
                
                player_data.append({
                    "start": round(rel_start, 2),
                    "end": round(rel_end, 2),
                    "text": segment['text'].strip()
                })
        
        return player_data
    
    def _is_korean(self, text):
        """텍스트에 한글이 포함되어 있는지 확인"""
        for char in text:
            if '가' <= char <= '힣':
                return True
        return False
    
    def _is_english_segment(self, text, debug=False):
        """세그먼트가 주로 영어인지 판단 (영어 전사 기준)"""
        text = text.strip()
        if not text:
            if debug: print(f"      ❌ 빈 텍스트")
            return False
        
        # 한글이 하나라도 있으면 한국어 (영어 전사에서도 한글이 남을 수 있음)
        if any('가' <= c <= '힣' for c in text):
            if debug: print(f"      ❌ 한글 포함")
            return False
        
        # 영어 전사 모드에서:
        # 1. 길이가 너무 짧으면 무시 (hallucination이나 노이즈)
        if len(text) < 12:  # 완화: 20 → 12 (짧은 응답 허용)
            if debug: print(f"      ❌ 너무 짧음 ({len(text)}자 < 12자)")
            return False
        
        # 2. 한국어를 영어로 잘못 전사한 패턴 감지
        korean_transliteration_patterns = [
            '입영작', '타임', '패턴', '만나볼까요', '연기', '연습',
            '읽어볼게요', '전체대화', '듣겠습니다', '주세요',
            '그렇죠', '여러분', '이거', '활용', '갈게요',
            '졸업했어', '뺐어', '파운드', '개월', 'kg'
        ]
        
        text_lower = text.lower()
        for pattern in korean_transliteration_patterns:
            if pattern.lower() in text_lower:
                if debug: print(f"      ❌ 한국어 패턴 '{pattern}' 감지")
                return False
        
        # 3. 공백으로 분리된 단어가 2개 미만이면 의심  
        words = text.split()
        if len(words) < 2:  # 완화: 3 → 2 ("Please." 등 짧은 응답 허용)
            if debug: print(f"      ❌ 단어 수 부족 ({len(words)}개 < 2개)")
            return False
        
        # 한글과 한국어 패턴 체크만으로도 충분 - 영어 단어 검증은 너무 제한적
        if debug: print(f"      ✅ 통과!")
        return True
    
    def find_anchor_and_extract_smart(self, audio_path,
                                      search_start_time=1380,
                                      anchor_phrases=["전체대화 주세요", "전체대화", "전체 대화", "전체되어", "전체 되어"]):
        """
        음악 기반 지능형 추출 + Whisper 전사로 영어 구간만 필터링
        
        Returns:
            (성공 여부, 앵커 시간, 추출 파일 경로)
        """
        print(f"{'='*80}")
        print(f"🎵 파일: {os.path.basename(audio_path)}")
        print(f"{'='*80}\n")
        
        # 오디오 로딩
        audio_full = AudioSegment.from_mp3(audio_path)
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
        
        # 시간 오프셋 보정 (23분 추가)
        for segment in result_ko['segments']:
            segment['start'] += search_start_time
            segment['end'] += search_start_time
        
        # 임시 파일 삭제
        os.remove(temp_path)
        
        # 전사 결과 저장 (한국어)
        base_name = Path(audio_path).stem
        transcription_path = f"transcription_{base_name}.json"
        with open(transcription_path, 'w', encoding='utf-8') as f:
            json.dump(result_ko, f, ensure_ascii=False, indent=2)
        print(f"💾 한국어 전사 결과 저장: {transcription_path}\n")
        
        # 2. 앵커 검색 (한국어 전사 사용)
        print(f"🔍 앵커 문구 검색 중...")
        anchor_end_time = None
        segments_ko = result_ko['segments']
        
        # 단일 세그먼트 검색
        for segment in segments_ko:
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
        
        # 병합 검색
        if anchor_end_time is None:
            print(f"🔍 연속 세그먼트 병합 검색 중...")
            for i, segment in enumerate(segments_ko):
                if i < len(segments_ko) - 2:
                    combined_text = (
                        segment['text'] + 
                        segments_ko[i+1]['text'] + 
                        segments_ko[i+2]['text']
                    ).strip()
                    
                    for anchor in anchor_phrases:
                        if anchor in combined_text:
                            anchor_end_time = segments_ko[i+2]['end']
                            print(f"✅ 앵커 발견 (병합)!")
                            print(f"   텍스트: '{combined_text}'")
                            print(f"   시간: {anchor_end_time:.2f}초 ({anchor_end_time/60:.2f}분)\n")
                            break
                    
                    if anchor_end_time:
                        break
        
        if anchor_end_time is None:
            print(f"❌ 앵커를 찾지 못했습니다\n")
            return False, None, None
        
        
        # 2단계: 음악 구간 감지로 대화 추출
        print(f"🔄 2단계: 음악 구간 감지 중...")
        
        # inaSpeechSegmenter로 음악/대화 구간 분석
        if not HAS_INA or self.segmenter is None:
            print("❌ inaSpeechSegmenter가 필요합니다.")
            print("다음 명령으로 설치하세요:")
            print("  pip install inaSpeechSegmenter tensorflow\n")
            return False, None, None
        
        print("🎼 음악 및 음성 세그먼트 분석 중...")
        ina_segments = self.segmenter(audio_path)
        
        # 앵커 이후 세그먼트만 필터링
        target_segments = [(label, start, end) for label, start, end in ina_segments if start >= anchor_end_time]
        
        if not target_segments:
            print("⚠️  앵커 이후 세그먼트를 찾지 못했습니다.\n")
            return False, None, None
        
        print(f"\n📊 앵커 이후 세그먼트 (처음 20개):")
        for i, (label, start, end) in enumerate(target_segments[:20]):
            duration = end - start
            print(f"  {i+1:2d}. {label:12s} {start:7.2f}초 ~ {end:7.2f}초 (길이: {duration:5.2f}초)")
        if len(target_segments) > 20:
            print(f"  ... 외 {len(target_segments)-20}개 세그먼트")
        
        # 3. 음악 시작점 찾기 (앵커 이후 첫 음악)
        extract_start = None
        for label, start, end in target_segments:
            if label == 'music':
                extract_start = start
                print(f"\n  🎵 음악 시작: {start:.2f}초 ({start/60:.2f}분)")
                break
        
        if extract_start is None:
            print("\n⚠️  음악을 찾지 못했습니다. 앵커 직후부터 시작합니다.")
            extract_start = anchor_end_time
        
        
        
        # 4. 음악 종료점 찾기 (음악 끝나고 한국어 계속 나오면 종료)
        # 한국어 전사 데이터에서 앵커 이후 세그먼트 추출
        korean_segments_after_anchor = [
            (seg['start'], seg['end'], seg['text']) 
            for seg in result_ko['segments'] 
            if seg['start'] > anchor_end_time + 5  # 앵커 5초 후부터
        ]
        
        print(f"\n  📋 앵커 이후 한국어 세그먼트 (처음 10개):")
        for i, (start, end, text) in enumerate(korean_segments_after_anchor[:10]):
            print(f"    {i+1}. [{start:.1f}s] {text[:50]}")
        
        extract_end = extract_start
        segment_count = 0
        
        # 한국어 세그먼트의 연속성 분석: 진짜 한국어는 촘촘하게, 잘못된 전사는 드문드문
        def find_teacher_explanation_start():
            """연속된 한국어 세그먼트를 찾아 진짜 선생님 설명 시작점 반환"""
            for i in range(len(korean_segments_after_anchor) - 2):
                seg1_start, seg1_end, seg1_text = korean_segments_after_anchor[i]
                seg2_start, seg2_end, seg2_text = korean_segments_after_anchor[i + 1]
                seg3_start, seg3_end, seg3_text = korean_segments_after_anchor[i + 2]
                
                gap1 = seg2_start - seg1_start
                gap2 = seg3_start - seg2_start
                
                # 3개 연속 세그먼트가 각각 5초 이내 간격 → 진짜 한국어 설명
                if gap1 <= 5.0 and gap2 <= 5.0:
                    print(f"\n  📍 진짜 한국어 설명 감지:")
                    print(f"    [{seg1_start:.1f}s] {seg1_text[:30]}")
                    print(f"    [{seg2_start:.1f}s] {seg2_text[:30]} (gap: {gap1:.1f}s)")
                    print(f"    [{seg3_start:.1f}s] {seg3_text[:30]} (gap: {gap2:.1f}s)")
                    return seg1_start
            
            return None
        
        teacher_start = find_teacher_explanation_start()
        
        print(f"\n  🔍 세그먼트 처리 중:")
        for label, start, end in target_segments:
            if start >= extract_start:
                segment_count += 1
                duration = end - start
                
                # 선생님 설명 시작점 도달하면 종료
                if teacher_start and end > teacher_start:
                    print(f"    {segment_count}. {label.upper():7s} [{start:.1f}s-{end:.1f}s] ({duration:.1f}s)")
                    print(f"\n  ⏹️  선생님 설명 시작 ({teacher_start:.1f}s) 전에 추출 종료")
                    print(f"  ⏹️  {extract_end:.2f}초에서 추출 종료")
                    break
                
                if label == 'music':
                    extract_end = end
                    print(f"    {segment_count}. MUSIC   [{start:.1f}s-{end:.1f}s] ({duration:.1f}s) ✅ 포함 (extract_end={extract_end:.1f})")
                    
                elif label in ['male', 'female']:
                    extract_end = end
                    print(f"    {segment_count}. {label.upper():7s} [{start:.1f}s-{end:.1f}s] ({duration:.1f}s) ✅ 포함 (extract_end={extract_end:.1f})")
                    
                elif label == 'noEnergy':
                    print(f"    {segment_count}. SILENCE [{start:.1f}s-{end:.1f}s] ({duration:.1f}s) ⏭️ 건너뜀")
                    
                else:
                    print(f"    {segment_count}. {label.upper():7s} [{start:.1f}s-{end:.1f}s] ({duration:.1f}s) ⏭️ 건너뜀")
        
        print(f"\n  총 처리한 세그먼트: {segment_count}개")
        
        
        # 5. 오디오 추출
        duration = extract_end - extract_start
        print(f"\n✂️  구간 추출:")
        print(f"   시작: {extract_start:.2f}초 ({extract_start/60:.2f}분)")
        print(f"   종료: {extract_end:.2f}초 ({extract_end/60:.2f}분)")
        print(f"   길이: {duration:.2f}초\n")
        
        start_ms = int(extract_start * 1000)
        end_ms = int(extract_end * 1000)
        
        extracted = audio_full[start_ms:end_ms]
        
        # MP3 저장
        output_path = f"extracted_{base_name}.mp3"
        print(f"💾 저장 중: {output_path}")
        extracted.export(
            output_path,
            format='mp3',
            bitrate='320k',
            parameters=["-q:a", "0"]
        )
        
        actual_duration = len(extracted) / 1000
        print(f"✅ 추출 완료: {actual_duration:.1f}초\n")
        
        # 6. 대화 스크립트 텍스트 추출 (한국어 전사 사용)
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

        print(f"📝 대화 스크립트 저장: {script_path}\n")

        # 7. 원어민 대화 전용 영어 전사 (웹 플레이어용)
        print(f"🔄 7단계: 원어민 대화 고품질 영어 전사 중...")
        result_en = self.model.transcribe(
            output_path,
            language='en',
            word_timestamps=False,
            verbose=False
        )
        
        # 8. 웹 플레이어용 JSON 데이터 저장 (영어 전사 결과 사용, 0초 기준)
        player_data = self.extract_player_data(result_en, 0, actual_duration)
        player_json_path = f"player_{base_name}.json"
        with open(player_json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "audio": output_path,
                "script": player_data
            }, f, ensure_ascii=False, indent=2)
        print(f"📱 웹 플레이어 데이터 저장(영어): {player_json_path}\n")
        
        return True, anchor_end_time, output_path
    
    def _extract_fixed(self, audio_path, anchor_end_time, base_name, transcription):
        """고정 시간 추출 (fallback)"""
        start_offset = 46
        duration = 50
        
        actual_start = anchor_end_time + start_offset
        actual_end = actual_start + duration
        
        print(f"\n✂️  고정 구간 추출:")
        print(f"   시작: {actual_start:.2f}초")
        print(f"   길이: {duration}초\n")
        
        audio = AudioSegment.from_mp3(audio_path)
        start_ms = int(actual_start * 1000)
        end_ms = min(start_ms + (duration * 1000), len(audio))
        
        extracted = audio[start_ms:end_ms]
        
        output_path = f"extracted_{base_name}.mp3"
        print(f"💾 저장 중: {output_path}")
        extracted.export(
            output_path,
            format='mp3',
            bitrate='320k',
            parameters=["-q:a", "0"]
        )
        
        print(f"✅ 추출 완료: {len(extracted)/1000:.1f}초\n")
        
        # 대화 스크립트 추출
        script_text = self.extract_script_text(transcription, actual_start, actual_end)
        script_path = f"script_{base_name}.txt"
        
        with open(script_path, 'w', encoding='utf-8') as f:
            f.write(f"{'='*80}\n")
            f.write(f"대화 스크립트: {os.path.basename(audio_path)}\n")
            f.write(f"{'='*80}\n")
            f.write(f"구간: {actual_start:.2f}초 ~ {actual_end:.2f}초 ({duration:.2f}초)\n")
            f.write(f"{'='*80}\n\n")
            f.write(script_text)
        
        print(f"📝 대화 스크립트 저장: {script_path}\n")

        # 원어민 대화 전용 영어 전사 (웹 플레이어용)
        print(f"🔄 원어민 대화 고품질 영어 전사 중 (고정 구간)...")
        result_en = self.model.transcribe(
            output_path,
            language='en',
            word_timestamps=False,
            verbose=False
        )

        # 웹 플레이어용 JSON 데이터 저장 (영어 전사 결과 사용, 0초 기준)
        player_data = self.extract_player_data(result_en, 0, duration)
        player_json_path = f"player_{base_name}.json"
        with open(player_json_path, 'w', encoding='utf-8') as f:
            json.dump({
                "audio": output_path,
                "script": player_data
            }, f, ensure_ascii=False, indent=2)
        print(f"📱 웹 플레이어 데이터 저장 (영어/고정 구간): {player_json_path}\n")
        
        return True, anchor_end_time, output_path
    
    def process_folder(self, folder_path='.',
                      pattern='*.mp3',
                      exclude_patterns=['extracted_', 'transcription_', '왕초보영어_']):
        """폴더 내 MP3 파일 배치 처리"""
        self.load_models()
        
        search_path = os.path.join(folder_path, pattern)
        all_files = glob.glob(search_path)
        
        mp3_files = []
        for f in all_files:
            basename = os.path.basename(f)
            should_exclude = False
            for exclude_pattern in exclude_patterns:
                if basename.startswith(exclude_pattern):
                    should_exclude = True
                    break
            if not should_exclude:
                mp3_files.append(f)
        
        if not mp3_files:
            print(f"⚠️  처리할 MP3 파일을 찾지 못했습니다")
            return
        
        print(f"\n{'='*80}")
        print(f"📁 폴더: {os.path.abspath(folder_path)}")
        print(f"🎵 발견된 파일: {len(mp3_files)}개")
        print(f"{'='*80}\n")
        
        results = []
        
        for i, file_path in enumerate(mp3_files, 1):
            print(f"[{i}/{len(mp3_files)}] 처리 중...\n")
            
            success, anchor_time, output_path = self.find_anchor_and_extract_smart(file_path)
            
            results.append({
                'file': os.path.basename(file_path),
                'success': success,
                'anchor_time': anchor_time,
                'output': os.path.basename(output_path) if output_path else None
            })
            
            print()
        
        # 결과 요약
        print(f"\n{'='*80}")
        print(f"📊 처리 결과 요약")
        print(f"{'='*80}\n")
        
        success_count = sum(1 for r in results if r['success'])
        print(f"✅ 성공: {success_count}/{len(results)}개\n")
        
        for r in results:
            status = "✅" if r['success'] else "❌"
            print(f"{status} {r['file']}")
            if r['success']:
                print(f"   → {r['output']} (앵커: {r['anchor_time']:.1f}초)")
        
        print(f"\n{'='*80}")
        print(f"🎉 배치 처리 완료!")
        print(f"{'='*80}\n")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(description='EBS 영어 강의 대화 구간 자동 추출')
    parser.add_argument('--file', '-f', type=str, help='처리할 특정 MP3 파일 경로')
    parser.add_argument('--folder', type=str, default='.', help='처리할 폴더 (기본: 현재 폴더)')
    parser.add_argument('--model', type=str, default='tiny', choices=['tiny', 'base', 'small', 'medium', 'large'],
                       help='Whisper 모델 크기 (기본: tiny)')
    
    args = parser.parse_args()
    
    if not HAS_INA:
        print("="*80)
        print("⚠️  inaSpeechSegmenter가 설치되지 않았습니다")
        print("="*80)
        print("\n다음 명령으로 설치하세요:")
        print("  pip install inaSpeechSegmenter tensorflow\n")
        print("설치 없이 계속하려면 fast_extract.py를 사용하세요.")
        print("="*80)
        return
    
    extractor = SmartConversationExtractor(model_size=args.model)
    
    # 단일 파일 처리
    if args.file:
        if not os.path.exists(args.file):
            print(f"❌ 파일을 찾을 수 없습니다: {args.file}")
            return
        
        extractor.load_models()
        success, anchor_time, output_path = extractor.find_anchor_and_extract_smart(args.file)
        
        if success:
            print(f"\n✅ 처리 완료!")
            print(f"   출력 파일: {output_path}")
        else:
            print("\n❌ 처리 실패")
    
    # 폴더 전체 처리
    else:
        extractor.process_folder(
            folder_path=args.folder,
            pattern='*.mp3',
            exclude_patterns=['extracted_', 'transcription_', '왕초보영어_', 'script_']
        )


if __name__ == "__main__":
    main()
