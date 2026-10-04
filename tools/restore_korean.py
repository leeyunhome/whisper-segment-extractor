import os
import json
import glob
import re

OUTPUT_DIR = "output_mp3"

def get_extract_start(stem):
    script_path = os.path.join(OUTPUT_DIR, f"{stem}.txt")
    if not os.path.exists(script_path):
        # Try with script_ prefix just in case
        script_path = os.path.join(OUTPUT_DIR, f"script_{stem}.txt")
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

def main():
    player_files = glob.glob(os.path.join(OUTPUT_DIR, "*_player.json"))
    count = 0
    for pf in player_files:
        stem = os.path.basename(pf).replace("_player.json", "")
        extract_start = get_extract_start(stem)
        if extract_start is None:
            print(f"Skipping {stem} (no extract_start found)")
            continue
        
        trans_path = os.path.join(OUTPUT_DIR, f"{stem}_transcription.json")
        if not os.path.exists(trans_path):
            print(f"Skipping {stem} (no transcription found)")
            continue
            
        with open(trans_path, "r", encoding="utf-8") as f:
            trans_data = json.load(f)
            trans_segments = trans_data.get("segments", [])
            
        with open(pf, "r", encoding="utf-8") as f:
            player_data = json.load(f)
            
        script = player_data.get("script", [])
        modified = False
        
        added_ko = set()
        
        for p_seg in script:
            if re.search(r'[가-힣]', p_seg["text"]):
                continue
                
            p_start = p_seg["start"] + extract_start
            p_end = p_seg["end"] + extract_start
            
            overlapping_ko = []
            for t_seg in trans_segments:
                if t_seg["start"] > p_end + 1.5:
                    continue
                if t_seg["end"] < p_start - 1.5:
                    continue
                    
                text = t_seg["text"].strip()
                if is_mostly_korean(text):
                    if "전체대화" in text or "입영작" in text or "알겠습니다" in text:
                        continue
                    if text not in added_ko:
                        overlapping_ko.append(text)
                        added_ko.add(text)
            
            if overlapping_ko:
                ko_text = " ".join(overlapping_ko)
                p_seg["text"] = p_seg["text"] + " " + ko_text
                modified = True
                    
        if modified:
            with open(pf, "w", encoding="utf-8") as f:
                json.dump(player_data, f, ensure_ascii=False, indent=2)
            print(f"Restored Korean for {stem}")
            count += 1
            
    print(f"\nDone! Updated {count} files.")

if __name__ == "__main__":
    main()
