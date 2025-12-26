import json

# 영어 전사 결과 확인
with open('transcription_en_20251224_173000_b21928fa_mp3.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

print("=" * 80)
print("앵커 이후 영어 전사 결과 (앵커: 1434.52초)")
print("=" * 80)

# 앵커 + 120초 범위 (2분간)
target_start = 1434
target_end = 1434 + 120

print(f"\n{target_start}초 ~ {target_end}초 사이의 세그먼트:\n")

for i, seg in enumerate(data['segments']):
    start = seg['start']
    end = seg['end']
    text = seg['text'].strip()
    
    if target_start <= start <= target_end:
        duration = end - start
        print(f"{i+1:3d}. [{start:7.1f}s - {end:7.1f}s] ({duration:4.1f}s) {text}")

print(f"\n총 {len(data['segments'])}개 세그먼트")
