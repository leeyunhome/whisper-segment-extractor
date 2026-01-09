"""
샘플 파일 분석 스크립트
원본과 추출본을 비교하여 정확한 추출 패턴 파악
"""
import os
from pydub import AudioSegment
import json

# 샘플 파일 쌍
samples = [
    {
        "original": "20251230_173000_59b81a3e_mp3.mp3",
        "extracted": "일상_어떤_일이_후회되나요_20251230.mp3",
        "name": "20251230 - 후회"
    },
    {
        "original": "20260102_173000_80902ef1_mp3.mp3",
        "extracted": "여행_학생_할인은_무조건_이득_20260102.mp3",
        "name": "20260102 - 학생할인"
    },
    {
        "original": "20260105_173000_36debe60_mp3.mp3",
        "extracted": "가정_애매한_새해_다짐_20260105.mp3",
        "name": "20260105 - 새해다짐"
    }
]

print("="*80)
print("샘플 파일 분석")
print("="*80)

for sample in samples:
    print(f"\n{'='*80}")
    print(f"📁 {sample['name']}")
    print(f"{'='*80}")
    
    original_path = sample['original']
    extracted_path = sample['extracted']
    
    # 파일 존재 확인
    if not os.path.exists(original_path):
        print(f"❌ 원본 파일 없음: {original_path}")
        continue
    
    if not os.path.exists(extracted_path):
        print(f"❌ 추출 파일 없음: {extracted_path}")
        continue
    
    # 오디오 로드
    original = AudioSegment.from_mp3(original_path)
    extracted = AudioSegment.from_mp3(extracted_path)
    
    original_duration = len(original) / 1000  # 초
    extracted_duration = len(extracted) / 1000  # 초
    
    print(f"\n📊 파일 정보:")
    print(f"  원본 길이: {original_duration:.1f}초 ({original_duration/60:.2f}분)")
    print(f"  추출 길이: {extracted_duration:.1f}초")
    
    # 전사 파일 확인
    base_name = original_path.replace(".mp3", "")
    transcription_file = f"transcription_{base_name}.json"
    
    if os.path.exists(transcription_file):
        with open(transcription_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            segments = data.get('segments', [])
            
            print(f"\n📝 전사 정보:")
            print(f"  총 세그먼트: {len(segments)}개")
            
            # 22-24분 사이 세그먼트 찾기
            anchor_candidates = []
            for seg in segments:
                start = seg['start']
                text = seg['text'].strip()
                
                # 22분(1320초) ~ 24분(1440초)
                if 1320 <= start <= 1440:
                    if '주세요' in text or '전체' in text and '대화' in text:
                        anchor_candidates.append({
                            'time': start,
                            'text': text
                        })
            
            if anchor_candidates:
                print(f"\n  🎯 앵커 후보 (22-24분):")
                for i, candidate in enumerate(anchor_candidates, 1):
                    print(f"    {i}. [{candidate['time']:.1f}s / {candidate['time']/60:.2f}분] {candidate['text']}")
            else:
                print(f"\n  ⚠️  22-24분 사이에 앵커 후보 없음")
    else:
        print(f"\n  ⚠️  전사 파일 없음: {transcription_file}")
    
    print()

print("\n" + "="*80)
print("분석 완료")
print("="*80)
