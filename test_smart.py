"""
smart_extract.py 테스트 - 한 파일만
"""

import sys
sys.path.insert(0, '.')
from smart_extract import SmartConversationExtractor

# 한 파일만 테스트
extractor = SmartConversationExtractor(model_size='tiny')
extractor.load_models()

success, anchor_time, output = extractor.find_anchor_and_extract_smart(
    '20251224_173000_b21928fa_mp3.mp3'
)

if success:
    print(f"\n✅ 성공!")
    print(f"   앵커: {anchor_time:.1f}초")
    print(f"   출력: {output}")
else:
    print("\n❌ 실패")
