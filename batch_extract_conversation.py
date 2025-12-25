"""
EBS 영어 강의 MP3 배치 처리 스크립트 (음악 기반 세그멘테이션)

폴더 내 모든 MP3 파일에서 "전체대화" 앵커를 찾아 
음악으로 둘러싸인 영어 대화 구간을 자동으로 추출합니다.

Requirements:
    pip install openai-whisper pydub inaSpeechSegmenter tensorflow
    
    # FFmpeg 설치 필요
    # Windows: choco install ffmpeg
"""

import whisper
import os
import glob
from pydub import AudioSegment
import json
from pathlib import Path

try:
    from inaSpeechSegmenter import Segmenter
    HAS_INA = True
except ImportError:
    HAS_INA = False
    print("⚠️  inaSpeechSegmenter가 설치되지 않았습니다")
    print("   pip install inaSpeechSegmenter 로 설치하세요")


class BatchConversationExtractor:
    def __init__(self, model_size='base', start_time_hint=1380):
        """
        Args:
            model_size: Whisper 모델 크기
            start_time_hint: 앵커 검색 시작 시간 (초), 기본 23분 = 1380초
        """
        self.model_size = model_size
        self.start_time_hint = start_time_hint
        self.model = None
        self.segmenter = None
        
    def load_models(self):
        """Whisper 및 inaSpeechSegmenter 모델 로딩"""
        if self.model is None:
            print(f"🔄 Whisper 모델 로딩 중... (모델: {self.model_size})")
            self.model = whisper.load_model(self.model_size)
            print("✅ Whisper 모델 로딩 완료")
        
        if HAS_INA and self.segmenter is None:
            print("🔄 inaSpeechSegmenter 모델 로딩 중...")
            self.segmenter = Segmenter()
            print("✅ inaSpeechSegmenter 모델 로딩 완료")
    
    def find_anchor_optimized(self, audio_path, anchor_phrases=["전체대화 주세요", "전체대화", "전체 대화"]):
        """
        23분 이후부터 앵커 문구 검색 (최적화)
        
        Returns:
            앵커 종료 시간 (초) 또는 None
        """
        print(f"\n{'='*60}")
        print(f"🎵 파일: {os.path.basename(audio_path)}")
        print(f"{'='*60}")
        
        print(f"🔄 오디오 전사 중... (시작 시점: {self.start_time_hint/60:.1f}분부터)")
        
        # Whisper 전사
        result = self.model.transcribe(
            audio_path,
            language='ko',
            word_timestamps=True,
            verbose=False
        )
        
        # 23분 이후 세그먼트만 검색
        anchor_end_time = None
        for segment in result['segments']:
            # start_time_hint 이후 세그먼트만 확인
            if segment['start'] >= self.start_time_hint:
                text = segment['text'].strip()
                
                for anchor in anchor_phrases:
                    if anchor in text:
                        anchor_end_time = segment['end']
                        print(f"✅ 앵커 발견: '{text}'")
                        print(f"📍 종료 시점: {anchor_end_time:.2f}초 ({anchor_end_time/60:.2f}분)")
                        return anchor_end_time, result
        
        print(f"⚠️  {self.start_time_hint/60:.1f}분 이후에서 앵커를 찾지 못했습니다")
        return None, result
    
    def extract_music_segment(self, audio_path, anchor_end_time, output_path):
        """
        inaSpeechSegmenter로 음악으로 둘러싸인 구간 추출
        
        Args:
            audio_path: 원본 MP3 파일
            anchor_end_time: 앵커 종료 시간
            output_path: 출력 파일 경로
        """
        if not HAS_INA or self.segmenter is None:
            print("⚠️  inaSpeechSegmenter를 사용할 수 없습니다")
            print("   고정 시간(3분) 추출로 대체합니다")
            return self._extract_simple(audio_path, anchor_end_time, output_path, 180)
        
        print("🔄 음성/음악 세그멘테이션 분석 중...")
        segments = self.segmenter(audio_path)
        
        # 앵커 이후 구간만 필터링
        target_segments = []
        for label, start, end in segments:
            if start >= anchor_end_time:
                target_segments.append((label, start, end))
        
        if not target_segments:
            print("⚠️  세그먼트를 찾지 못했습니다. 고정 시간(3분) 추출로 대체합니다")
            return self._extract_simple(audio_path, anchor_end_time, output_path, 180)
        
        print(f"\n📊 앵커 이후 세그먼트 분석:")
        for label, start, end in target_segments[:10]:  # 처음 10개만 출력
            print(f"  {label:12s} {start:7.2f}초 ~ {end:7.2f}초 (길이: {end-start:.2f}초)")
        if len(target_segments) > 10:
            print(f"  ... 외 {len(target_segments)-10}개 세그먼트")
        
        # 음악/영어 구간 찾기
        # 전략: music으로 시작하거나, male/female 음성이 포함된 연속 구간
        extract_start = anchor_end_time
        extract_end = anchor_end_time
        
        # 음악이나 영어 음성이 연속되는 구간 찾기
        looking_for_content = True
        silence_threshold = 2.0  # 2초 이상 공백이면 종료
        
        for i, (label, start, end) in enumerate(target_segments):
            # music, male, female은 콘텐츠로 간주
            if label in ['music', 'male', 'female']:
                if looking_for_content:
                    extract_start = start
                    looking_for_content = False
                extract_end = end
            elif label == 'noEnergy':
                # 침묵 구간: 너무 길면 종료
                if not looking_for_content and (end - start) > silence_threshold:
                    print(f"  ⏹️  긴 침묵 감지 ({end-start:.2f}초), 추출 종료")
                    break
            else:
                # 기타 (한국어 등): 종료
                if not looking_for_content:
                    print(f"  ⏹️  기타 음성 감지 (라벨: {label}), 추출 종료")
                    break
        
        duration = extract_end - extract_start
        print(f"\n✂️  추출 구간: {extract_start:.2f}초 ~ {extract_end:.2f}초 (길이: {duration:.2f}초 = {duration/60:.2f}분)")
        
        # 오디오 추출
        print("🔄 오디오 로딩 및 추출 중...")
        audio = AudioSegment.from_mp3(audio_path)
        
        start_ms = int(extract_start * 1000)
        end_ms = int(extract_end * 1000)
        
        extracted = audio[start_ms:end_ms]
        
        # 저장
        print(f"💾 저장 중: {output_path}")
        extracted.export(
            output_path,
            format='mp3',
            bitrate='320k',
            parameters=["-q:a", "0"]
        )
        
        print(f"✅ 추출 완료: {len(extracted)/1000:.2f}초")
        return True
    
    def _extract_simple(self, audio_path, anchor_end_time, output_path, duration=180):
        """고정 시간 추출 (fallback)"""
        print(f"✂️  고정 구간 추출: {anchor_end_time:.2f}초 ~ {anchor_end_time+duration:.2f}초")
        
        audio = AudioSegment.from_mp3(audio_path)
        start_ms = int(anchor_end_time * 1000)
        end_ms = min(start_ms + (duration * 1000), len(audio))
        
        extracted = audio[start_ms:end_ms]
        
        print(f"💾 저장 중: {output_path}")
        extracted.export(
            output_path,
            format='mp3',
            bitrate='320k',
            parameters=["-q:a", "0"]
        )
        
        print(f"✅ 추출 완료: {len(extracted)/1000:.2f}초")
        return True
    
    def process_file(self, audio_path, output_dir=None):
        """
        단일 파일 처리
        
        Returns:
            (성공 여부, 출력 파일 경로)
        """
        try:
            # 앵커 찾기
            anchor_time, transcription = self.find_anchor_optimized(audio_path)
            
            if anchor_time is None:
                print("❌ 앵커를 찾지 못했습니다. 건너뜁니다.\n")
                return False, None
            
            # 출력 경로 결정
            if output_dir is None:
                output_dir = os.path.dirname(audio_path)
            
            base_name = Path(audio_path).stem
            output_path = os.path.join(output_dir, f"extracted_conversation_{base_name}.mp3")
            
            # 음악 구간 추출
            success = self.extract_music_segment(audio_path, anchor_time, output_path)
            
            # 전사 결과 저장 (디버깅용)
            transcription_path = os.path.join(output_dir, f"transcription_{base_name}.json")
            with open(transcription_path, 'w', encoding='utf-8') as f:
                json.dump(transcription, f, ensure_ascii=False, indent=2)
            print(f"💾 전사 결과 저장: {transcription_path}")
            
            return success, output_path
            
        except Exception as e:
            print(f"❌ 오류 발생: {e}\n")
            import traceback
            traceback.print_exc()
            return False, None
    
    def process_folder(self, folder_path='.', pattern='*.mp3', exclude_pattern='extracted_*'):
        """
        폴더 내 모든 MP3 파일 배치 처리
        
        Args:
            folder_path: 검색할 폴더
            pattern: MP3 파일 패턴
            exclude_pattern: 제외할 파일 패턴
        """
        # 모델 로딩
        self.load_models()
        
        # MP3 파일 검색
        search_path = os.path.join(folder_path, pattern)
        all_files = glob.glob(search_path)
        
        # 제외 패턴 필터링
        mp3_files = [f for f in all_files if not os.path.basename(f).startswith('extracted_')]
        
        if not mp3_files:
            print(f"⚠️  {folder_path}에서 MP3 파일을 찾지 못했습니다")
            return
        
        print(f"\n{'='*60}")
        print(f"📁 폴더: {os.path.abspath(folder_path)}")
        print(f"🎵 발견된 파일: {len(mp3_files)}개")
        print(f"{'='*60}\n")
        
        for i, file_path in enumerate(mp3_files, 1):
            print(f"\n[{i}/{len(mp3_files)}] 처리 중...")
            success, output_path = self.process_file(file_path)
            
            if success:
                print(f"✅ 성공: {os.path.basename(output_path)}\n")
            else:
                print(f"❌ 실패: {os.path.basename(file_path)}\n")
        
        print(f"\n{'='*60}")
        print(f"🎉 배치 처리 완료!")
        print(f"{'='*60}\n")


def main():
    """메인 함수"""
    
    # 배치 추출기 초기화
    extractor = BatchConversationExtractor(
        model_size='base',      # tiny, base, small, medium, large
        start_time_hint=1380    # 23분 = 1380초부터 검색 시작
    )
    
    # 현재 폴더의 모든 MP3 파일 처리
    extractor.process_folder(
        folder_path='.',
        pattern='*.mp3',
        exclude_pattern='extracted_*'
    )


if __name__ == "__main__":
    main()
