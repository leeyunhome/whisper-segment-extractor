
import json
import sys

# Force UTF-8 for stdout
sys.stdout.reconfigure(encoding='utf-8')

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
    
    print("\nText segments after anchor (+5s):")
    # Just dump the next 100 segments with Korean
    count = 0
    for i in range(anchor_idx + 1, len(segments)):
        seg = segments[i]
        if seg['start'] > anchor_end_time + 5:
           # Print everything to see context
           print(f"IDX {i}: [{seg['start']:.1f}-{seg['end']:.1f}] {seg['text']}")
           count += 1
           if count > 100:
               break

if __name__ == "__main__":
    analyze()
