
import json
import sys

def analyze():
    # checking the new file based on user report
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
    print(f"Anchor End Time: {anchor_end_time:.2f}")

    def is_mostly_korean(text):
        korean_count = 0
        total_count = 0
        for char in text:
            if char.isspace():
                continue
            total_count += 1
            if '가' <= char <= '힣':
                korean_count += 1
        
        if total_count == 0:
            return False
        return (korean_count / total_count) > 0.5

    print("\nScanning segments after anchor (+5s):")
    korean_segments = []
    
    stop_phrase_found = False

    for i in range(anchor_idx + 1, len(segments)):
        seg = segments[i]
        if seg['start'] > anchor_end_time + 5:
            # Check for the user's specific hint "입으로 하는 영작"
            if "입으로 하는 영작" in seg['text']:
                print(f"!!! SPECIFIC PHRASE FOUND !!! [{seg['start']:.1f}-{seg['end']:.1f}] {seg['text']}")
                stop_phrase_found = True

            is_k = is_mostly_korean(seg['text'])
            
            # Print potentially missed stop points
            if is_k:
                korean_segments.append(seg)
                if len(korean_segments) <= 5: # Just print first few Korean ones to see start
                     print(f"KO SEG: [{seg['start']:.1f}-{seg['end']:.1f}] {seg['text']}")
            else:
                 pass 

    # Check trigger logic that IS CURRENTLY RUNNING
    print("\nChecking CURRENT trigger logic (is_mostly_korean):")
    for i in range(len(korean_segments) - 2):
        seg1 = korean_segments[i]
        seg2 = korean_segments[i+1]
        seg3 = korean_segments[i+2]
        
        gap1 = seg2['start'] - seg1['start']
        gap2 = seg3['start'] - seg2['start']
        
        if gap1 <= 5.0 and gap2 <= 5.0:
            print(f"!!! WOULD TRIGGER HERE at {seg1['start']:.2f} !!!")
            print(f"1. {seg1['text']}")
            print(f"2. {seg2['text']}")
            print(f"3. {seg3['text']}")
            break

if __name__ == "__main__":
    analyze()
