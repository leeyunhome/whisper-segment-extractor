"""
EBS 영어 강의 대화 구간 추출 스크립트 (빠른 버전)

분석 결과 기반:
- "전체대화" 앵커 이후 약 45-60초 구간 추출
- 23분 이후 검색 시작
- Whisper tiny 모델 사용으로 속도 향상

Requirements:
    pip install openai-whisper pydub
"""

import whisper
import os
import glob
from pydub import AudioSegment
import json
from pathlib import Path


class FastConversationExtractor:
    def __init__(self, model_size='tiny'):
        """
        Args:
            model_size: Whisper 모델 크기 (tiny 권장 - 빠르고 앵커 감지에 충분)
        """
        self.model_size = model_size
        self.model = None
        
    def load_model(self):
        """Whisper 모델 로딩"""
        if self.model is None:
            print(f"🔄 Whisper 모델 로딩 중... (모델: {self.model_size})")
            self.model = whisper.load_model(self.model_size)
            print("✅ 모델 로딩 완료\n")
    
    def find_anchor_and_extract(self, audio_path, 
                                search_start_time=1380,  # 23분
                                extraction_duration=50,   # 50초 추출 (분석 결과 평균)
                                start_offset=46,          # 앵커 이후 음악 시작까지 대기 (초)
                                anchor_phrases=["전체대화 주세요", "전체대화", "전체 대화", "전체되어", "전체 되어"]):
        """
        앵커를 찾아 대화 구간 추출
        
        Args:
            audio_path: MP3 파일 경로
            search_start_time: 검색 시작 시간 (초)
            extraction_duration: 추출 길이 (초)
            start_offset: 앵커 종료 후 실제 추출까지 대기 시간 (초) - 음악 시작까지 대기
            anchor_phrases: 검색할 앵커 문구들
            
        Returns:
            (성공 여부, 앵커 시간, 추출 파일 경로)
        """
        print(f"{'='*80}")
        print(f"🎵 파일: {os.path.basename(audio_path)}")
        print(f"{'='*80}\n")
        
        # 1. 전사
        print(f"🔄 전사 중 (검색 시작: {search_start_time/60:.1f}분부터)...")
        result = self.model.transcribe(
            audio_path,
            language='ko',
            word_timestamps=False,
            verbose=False
        )
        
        # 전사 결과 저장 (디버깅용)
        base_name = Path(audio_path).stem
        transcription_path = f"transcription_{base_name}.json"
        with open(transcription_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"💾 전사 결과 저장: {transcription_path}\n")
        
        # 2. 앵커 검색
        print(f"🔍 앵커 문구 검색 중...")
        anchor_end_time = None
        segments = result['segments']
        
        # 먼저 단일 세그먼트에서 검색
        for segment in segments:
            if segment['start'] >= search_start_time:
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
        
        # 단일 세그먼트에서 못 찾으면 연속 세그먼트 병합 검색
        if anchor_end_time is None:
            print(f"🔍 연속 세그먼트 병합 검색 중...")
            for i, segment in enumerate(segments):
                if segment['start'] >= search_start_time and i < len(segments) - 2:
                    # 현재 + 다음 2개 세그먼트 병합
                    combined_text = (
                        segment['text'] + 
                        segments[i+1]['text'] + 
                        segments[i+2]['text']
                    ).strip()
                    
                    for anchor in anchor_phrases:
                        if anchor in combined_text:
                            anchor_end_time = segments[i+2]['end']
                            print(f"✅ 앵커 발견 (병합)!")
                            print(f"   텍스트: '{combined_text}'")
                            print(f"   시간: {anchor_end_time:.2f}초 ({anchor_end_time/60:.2f}분)\n")
                            break
                    
                    if anchor_end_time:
                        break
        
        if anchor_end_time is None:
            print(f"❌ 앵커를 찾지 못했습니다\n")
            return False, None, None
        
        # 3. 오디오 추출
        actual_start_time = anchor_end_time + start_offset
        print(f"✂️  구간 추출:")
        print(f"   앵커 종료: {anchor_end_time:.2f}초 ({anchor_end_time/60:.2f}분)")
        print(f"   음악 시작 대기: +{start_offset}초")
        print(f"   추출 시작: {actual_start_time:.2f}초 ({actual_start_time/60:.2f}분)")
        print(f"   추출 종료: {actual_start_time + extraction_duration:.2f}초")
        print(f"   길이: {extraction_duration}초\n")
        
        audio = AudioSegment.from_mp3(audio_path)
        start_ms = int(actual_start_time * 1000)
        end_ms = min(start_ms + (extraction_duration * 1000), len(audio))
        
        extracted = audio[start_ms:end_ms]
        
        # 4. 저장
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
        
        return True, anchor_end_time, output_path
    
    def process_folder(self, folder_path='.', 
                      pattern='*.mp3', 
                      exclude_patterns=['extracted_', 'transcription_', '왕초보영어_'],
                      extraction_duration=50,
                      start_offset=46):
        """
        폴더 내 MP3 파일 배치 처리
        
        Args:
            folder_path: 검색할 폴더
            pattern: 파일 패턴
            exclude_patterns: 제외할 파일명 패턴들
            extraction_duration: 추출 길이 (초)
            start_offset: 앵커 종료 후 추출 시작까지 대기 시간 (초)
        """
        # 모델 로딩
        self.load_model()
        
        # 파일 검색
        search_path = os.path.join(folder_path, pattern)
        all_files = glob.glob(search_path)
        
        # 제외 패턴 필터링
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
            
            success, anchor_time, output_path = self.find_anchor_and_extract(
                file_path,
                extraction_duration=extraction_duration,
                start_offset=start_offset
            )
            
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
    
    extractor = FastConversationExtractor(model_size='tiny')
    
    # 현재 폴더의 MP3 파일 처리
    extractor.process_folder(
        folder_path='.',
        pattern='*.mp3',
        exclude_patterns=['extracted_', 'transcription_', '왕초보영어_'],
        extraction_duration=50,  # 50초 추출 (분석 결과: 평균 50초, 범위 46-57초)
        start_offset=46          # 앵커 이후 46초 대기 (음악 시작까지)
    )


if __name__ == "__main__":
    main()
