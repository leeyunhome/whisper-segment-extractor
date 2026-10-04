import os
import json
import re

OUTPUT_DIR = "output_mp3"
STEM = "2722_여행_공항과_유모차_I_20260522"

def get_extract_start(stem):
    script_path = os.path.join(OUTPUT_DIR, f"{stem}.txt")
    if not os.path.exists(script_path):
        return None
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()
    m = re.search(r"구간:\s*([0-9.]+)초", content)
    if m:
        return float(m.group(1))
    return None

def is_mostly_korean(text):
    korean = sum(1 for c in text if '가' <= c <= '힣')
    total = sum(1 for c in text if not c.isspace())
    return total > 0 and korean / total > 0.3

def clean_text(text):
    return re.sub(r'[^a-zA-Z0-9가-힣]', '', text).lower()

def main():
    extract_start = get_extract_start(STEM)
    trans_path = os.path.join(OUTPUT_DIR, f"{STEM}_transcription.json")
    with open(trans_path, "r", encoding="utf-8") as f:
        trans_segments = json.load(f).get("segments", [])
        
    player_path = os.path.join(OUTPUT_DIR, f"{STEM}_player.json")
    with open(player_path, "r", encoding="utf-8") as f:
        script = json.load(f).get("script", [])
        
    for p_seg in script:
        eng_text = p_seg["text"]
        # Remove any Korean that might have been accidentally appended
        eng_text_clean = re.sub(r'[가-힣].*$', '', eng_text).strip()
        
        print(f"\n--- Target: {eng_text_clean} ---")
        
        target_clean = clean_text(eng_text_clean)
        if not target_clean:
            continue
            
        best_match_idx = -1
        # Find this English sentence earlier in the transcription
        for i, t_seg in enumerate(trans_segments):
            if t_seg["start"] >= extract_start - 10:
                # Stop looking when we reach the '전체 대화' section
                break
                
            t_clean = clean_text(t_seg["text"])
            if t_clean and (target_clean in t_clean or t_clean in target_clean):
                if len(t_clean) > len(target_clean) * 0.5:
                    best_match_idx = i
                    print(f"  Found Eng match at {t_seg['start']}: {t_seg['text']}")
        
        if best_match_idx != -1:
            # Look backwards for the Korean translation (up to 3 segments)
            for j in range(best_match_idx - 1, max(-1, best_match_idx - 4), -1):
                prev_text = trans_segments[j]["text"].strip()
                if is_mostly_korean(prev_text):
                    if "미션" in prev_text or "번째" in prev_text:
                        continue # Skip meta phrases
                    print(f"  => Found Kor: {prev_text}")
                    break

if __name__ == "__main__":
    main()
