"""전사 결과에서 앵커 문구 검색"""
import json

files = [
    "transcription_20251218_173000_f47b47fc_mp3.json",
    "transcription_20251219_173000_0476451b_mp3.json",
    "transcription_20251224_173000_b21928fa_mp3.json"
]

anchor_phrases = ["전체대화 주세요", "전체대화", "전체 대화"]

output_lines = []

for file in files:
    line1 = f"\n{'='*80}"
    line2 = f"파일: {file}"
    line3 = f"{'='*80}"
    
    print(line1)
    print(line2)
    print(line3)
    output_lines.extend([line1, line2, line3])
    
    with open(file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # 23분(1380초) 이후 세그먼트만
    segments_after_23min = [s for s in data['segments'] if s['start'] >= 1380]
    msg = f"\n23분 이후 세그먼트 개수: {len(segments_after_23min)}"
    print(msg)
    output_lines.append(msg)
    
    # 앵커 검색
    found = False
    for segment in segments_after_23min:
        text = segment['text'].strip()
        for anchor in anchor_phrases:
            if anchor in text:
                msgs = [
                    f"\n✅ 앵커 발견!",
                    f"   시간: {segment['start']:.1f}초 ({segment['start']/60:.2f}분)",
                    f"   텍스트: '{text}'"
                ]
                for m in msgs:
                    print(m)
                    output_lines.append(m)
                found = True
                break
        if found:
            break
    
    if not found:
        msg = f"\n❌ 앵커를 찾지 못했습니다"
        print(msg)
        output_lines.append(msg)
        
        msg2 = f"\n23분 이후 처음 10개 세그먼트:"
        print(msg2)
        output_lines.append(msg2)
        
        for i, s in enumerate(segments_after_23min[:10], 1):
            msg = f"  {i}. {s['start']:.1f}초 ({s['start']/60:.2f}분): {s['text']}"
            print(msg)
            output_lines.append(msg)

# 파일로 저장
with open("anchor_check_result.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(output_lines))

print("\n✅ 결과가 anchor_check_result.txt에 저장되었습니다")
