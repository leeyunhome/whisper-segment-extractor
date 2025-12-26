import json

# transcription JSON 로드
with open('transcription_20251225_173000_c4bd9276_mp3.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 80)
print("앵커 주변 세그먼트 확인")
print("=" * 80)

# 24분~26분 사이의 세그먼트 출력
target_start = 24 * 60  # 24분
target_end = 26 * 60    # 26분

print(f"\n{target_start}초 ~ {target_end}초 사이의 세그먼트:\n")

for seg in data['segments']:
    start = seg['start']
    end = seg['end']
    text = seg['text'].strip()
    
    if target_start <= start <= target_end:
        print(f"[{start/60:.2f}분 ({start:.1f}초)] {text}")

# "전체대화" 포함된 세그먼트 찾기
print("\n" + "=" * 80)
print("'전체대화' 문구를 포함한 세그먼트:")
print("=" * 80 + "\n")

anchor_phrases = ["전체대화 주세요", "전체대화", "전체 대화", "전체되어", "전체 되어"]

for seg in data['segments']:
    text = seg['text'].strip()
    for anchor in anchor_phrases:
        if anchor in text:
            print(f"✅ 발견!")
            print(f"   시간: {seg['start']:.2f}초 ({seg['start']/60:.2f}분) ~ {seg['end']:.2f}초 ({seg['end']/60:.2f}분)")
            print(f"   텍스트: '{text}'\n")
