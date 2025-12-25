"""
간단한 테스트 스크립트 - 한 파일만 처리
"""

import sys
sys.path.insert(0, '.')
from fast_extract import FastConversationExtractor

# 한 파일만 테스트
extractor = FastConversationExtractor(model_size='tiny')
extractor.load_model()

success, anchor_time, output = extractor.find_anchor_and_extract(
    '20251224_173000_b21928fa_mp3.mp3',
    extraction_duration=50,  # 음악 끝나는 시점 (평균 50초)
    start_offset=46
)

if success:
    print(f"\n✅ 성공!")
    print(f"   앵커: {anchor_time:.1f}초")
    print(f"   출력: {output}")
else:
    print("\n❌ 실패")
