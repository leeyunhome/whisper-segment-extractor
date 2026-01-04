
import json
import sys

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
    
    print("\n--- Context Analysis ---")
    
    stop_phrases = ["입으로 하는 영작", "입영작"]
    
    # Find the explicit stop phrase index first
    stop_idx = -1
    stop_seg = None
    
    for i in range(anchor_idx + 1, len(segments)):
        seg = segments[i]
        text = seg['text']
        for phrase in stop_phrases:
            if phrase in text:
                stop_idx = i
                stop_seg = seg
                print(f"STOP PHRASE FOUND at IDX {i}: [{seg['start']:.2f}-{seg['end']:.2f}] {text}")
                break
        if stop_idx != -1:
            break
            
    if stop_idx != -1:
        # Print 5 segments BEFORE the stop phrase to see what we are cutting off
        print("\nSegments BEFORE stop phrase:")
        for i in range(max(anchor_idx, stop_idx - 10), stop_idx + 1):
            s = segments[i]
            mark = ">>>" if i == stop_idx else "   "
            print(f"{mark} IDX {i}: [{s['start']:.2f}-{s['end']:.2f}] {s['text']}")
            
    else:
        print("Stop phrase NOT found in the window investigated.")

if __name__ == "__main__":
    analyze()
