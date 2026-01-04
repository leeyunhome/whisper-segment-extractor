
import json

def analyze():
    file_path = 'transcription_20260102_173000_80902ef1_mp3.json'
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"File not found: {file_path}")
        return

    segments = data['segments']
    anchor_phrases = ["전체대화 주세요", "전체대화", "전체 대화", "전체되어", "전체 되어"]
    
    anchor_found = None
    anchor_idx = -1
    for i, seg in enumerate(segments):
        text = seg['text'].strip()
        for anchor in anchor_phrases:
            if anchor in text:
                anchor_found = seg
                anchor_idx = i
                break
        if anchor_found:
            break
            
    if not anchor_found:
        print("Anchor not found!")
        return
    
    anchor_end_time = anchor_found['end']
    
    def is_mostly_korean(text):
        korean_count = 0
        total_count = 0
        for char in text:
            if char.isspace():
                continue
            total_count += 1
            if '가' <= char <= '힣':
                korean_count += 1
        return (total_count > 0) and ((korean_count / total_count) > 0.5)

    print("\nScanning segments after anchor (+5s):")
    korean_segments = []
    
    stop_phrases = ["입으로 하는 영작", "입영작"]
    
    for i in range(anchor_idx + 1, len(segments)):
        seg = segments[i]
        if seg['start'] > anchor_end_time + 5:
            # Check explicit phrasing first
            for phrase in stop_phrases:
                if phrase in seg['text']:
                     print(f"!!! EXPLICIT STOP FOUND !!! [{seg['start']:.1f}-{seg['end']:.1f}] {seg['text']}")
                     return # Simulate stopping here

            if is_mostly_korean(seg['text']):
                korean_segments.append(seg)

    print("\nExplicit phrases NOT found (if you see this).")
    
if __name__ == "__main__":
    analyze()
