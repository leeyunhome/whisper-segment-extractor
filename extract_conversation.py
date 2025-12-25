"""
EBS 영어 강의 MP3에서 "전체대화" 앵커를 찾아 영어 대화 구간을 자동 추출하는 스크립트

Requirements:
    pip install openai-whisper pydub inaSpeechSegmenter
    
    # FFmpeg 설치 필요 (pydub 의존성)
    # Windows: https://www.ffmpeg.org/download.html
"""

import whisper
import os
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
import json

# Optional: inaSpeechSegmenter를 사용하려면 아래 주석 해제
# from inaSpeechSegmenter import Segmenter


class ConversationExtractor:
    def __init__(self, audio_path, model_size='base'):
        """
        Args:
            audio_path: MP3 파일 경로
            model_size: Whisper 모델 크기 ('tiny', 'base', 'small', 'medium', 'large')
        """
        self.audio_path = audio_path
        self.model_size = model_size
        self.model = None
        self.transcription = None
        self.anchor_end_time = None
        
    def load_whisper_model(self):
        """Whisper 모델 로딩"""
        print(f"🔄 Whisper 모델 로딩 중... (모델: {self.model_size})")
        self.model = whisper.load_model(self.model_size)
        print("✅ 모델 로딩 완료")
        
    def transcribe_audio(self):
        """오디오를 텍스트로 변환 (타임스탬프 포함)"""
        if self.model is None:
            self.load_whisper_model()
            
        print(f"🔄 오디오 전사(transcription) 시작: {self.audio_path}")
        
        # word_timestamps=True로 설정하면 더 정확한 타임스탬프 확보 가능
        self.transcription = self.model.transcribe(
            self.audio_path,
            language='ko',  # 한국어 강의이므로
            word_timestamps=True,
            verbose=True
        )
        
        print("✅ 전사 완료")
        return self.transcription
    
    def find_anchor_phrase(self, anchor_phrases=["전체대화 주세요", "전체대화", "전체 대화"]):
        """앵커 문구를 찾아 종료 시점 반환"""
        if self.transcription is None:
            print("⚠️  먼저 transcribe_audio()를 실행하세요")
            return None
            
        print(f"🔍 앵커 문구 검색 중: {anchor_phrases}")
        
        # Segments 단위로 검색
        for segment in self.transcription['segments']:
            text = segment['text'].strip()
            
            # 앵커 문구가 포함되어 있는지 확인
            for anchor in anchor_phrases:
                if anchor in text:
                    self.anchor_end_time = segment['end']
                    print(f"✅ 앵커 발견: '{text}'")
                    print(f"📍 종료 시점: {self.anchor_end_time:.2f}초")
                    return self.anchor_end_time
        
        print("⚠️  앵커 문구를 찾지 못했습니다")
        return None
    
    def extract_segment_simple(self, duration_seconds=180, output_path='extracted_conversation.mp3'):
        """
        앵커 이후 고정 시간만큼 추출 (간단한 방법)
        
        Args:
            duration_seconds: 추출할 길이 (초), 기본 3분
            output_path: 출력 파일 경로
        """
        if self.anchor_end_time is None:
            print("⚠️  먼저 find_anchor_phrase()를 실행하세요")
            return None
            
        print(f"🔄 오디오 로딩 중: {self.audio_path}")
        audio = AudioSegment.from_mp3(self.audio_path)
        
        # 시작/종료 시점 계산 (밀리초 단위)
        start_ms = int(self.anchor_end_time * 1000)
        end_ms = start_ms + (duration_seconds * 1000)
        
        # 오디오 파일 길이를 넘지 않도록
        end_ms = min(end_ms, len(audio))
        
        print(f"✂️  구간 추출: {start_ms/1000:.2f}초 ~ {end_ms/1000:.2f}초")
        extracted = audio[start_ms:end_ms]
        
        # 고음질로 저장
        print(f"💾 저장 중: {output_path}")
        extracted.export(
            output_path,
            format='mp3',
            bitrate='320k',  # 고음질
            parameters=["-q:a", "0"]  # 최고 품질
        )
        
        print(f"✅ 추출 완료: {output_path} ({len(extracted)/1000:.2f}초)")
        return output_path
    
    def extract_segment_smart(self, output_path='extracted_conversation.mp3'):
        """
        inaSpeechSegmenter를 사용한 지능형 추출
        음악 및 음성 구간을 자동 감지
        """
        try:
            from inaSpeechSegmenter import Segmenter
        except ImportError:
            print("⚠️  inaSpeechSegmenter가 설치되지 않았습니다")
            print("   pip install inaSpeechSegmenter 로 설치하세요")
            print("   대신 extract_segment_simple()을 사용하세요")
            return None
            
        if self.anchor_end_time is None:
            print("⚠️  먼저 find_anchor_phrase()를 실행하세요")
            return None
            
        print("🔄 음성/음악 세그멘테이션 시작...")
        seg = Segmenter()
        segments = seg(self.audio_path)
        
        # 앵커 이후 구간만 필터링
        target_segments = []
        for label, start, end in segments:
            if start >= self.anchor_end_time:
                target_segments.append((label, start, end))
                print(f"  - {label}: {start:.2f}초 ~ {end:.2f}초")
        
        # 음악이나 영어 음성 구간 찾기
        extract_end = self.anchor_end_time
        for label, start, end in target_segments:
            # 'music' 또는 'female/male' (영어) 라벨이면 포함
            if label in ['music', 'female', 'male']:
                extract_end = end
            else:
                # 한국어 해설이 나오면 종료
                break
        
        print(f"✂️  최종 구간: {self.anchor_end_time:.2f}초 ~ {extract_end:.2f}초")
        
        # 오디오 추출
        audio = AudioSegment.from_mp3(self.audio_path)
        start_ms = int(self.anchor_end_time * 1000)
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
        
        print(f"✅ 추출 완료: {output_path} ({len(extracted)/1000:.2f}초)")
        return output_path
    
    def save_transcription(self, output_path='transcription.json'):
        """전사 결과를 JSON으로 저장"""
        if self.transcription is None:
            print("⚠️  전사 결과가 없습니다")
            return None
            
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.transcription, f, ensure_ascii=False, indent=2)
        
        print(f"💾 전사 결과 저장: {output_path}")
        return output_path


# ============= 사용 예시 =============

def main():
    # 1. MP3 파일 경로 설정
    audio_file = "20251224_173000_b21928fa_mp3.mp3"  # 여기에 실제 파일 경로 입력
    
    # 파일 존재 확인
    if not os.path.exists(audio_file):
        print(f"❌ 파일을 찾을 수 없습니다: {audio_file}")
        print("   audio_file 변수에 올바른 경로를 입력하세요")
        return
    
    # 2. Extractor 초기화
    extractor = ConversationExtractor(
        audio_path=audio_file,
        model_size='base'  # 'tiny', 'base', 'small', 'medium', 'large' 중 선택
    )
    
    # 3. 오디오 전사
    extractor.transcribe_audio()
    
    # 4. 앵커 문구 찾기
    anchor_time = extractor.find_anchor_phrase()
    
    if anchor_time is None:
        print("앵커를 찾지 못했습니다. 프로그램을 종료합니다.")
        return
    
    # 5-A. 간단한 방법: 앵커 이후 3분 추출
    print("\n" + "="*50)
    print("방법 1: 고정 시간(3분) 추출")
    print("="*50)
    extractor.extract_segment_simple(
        duration_seconds=180,
        output_path='extracted_conversation_simple.mp3'
    )
    
    # 5-B. 지능형 방법: 음성/음악 세그멘테이션 사용 (선택사항)
    # 주석을 해제하고 inaSpeechSegmenter 설치 후 사용
    # print("\n" + "="*50)
    # print("방법 2: 지능형 세그멘테이션")
    # print("="*50)
    # extractor.extract_segment_smart(
    #     output_path='extracted_conversation_smart.mp3'
    # )
    
    # 6. 전사 결과 저장 (디버깅용)
    extractor.save_transcription('transcription.json')
    
    print("\n✅ 모든 작업 완료!")


if __name__ == "__main__":
    main()
