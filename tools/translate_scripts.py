import os
import json
import glob
from deep_translator import GoogleTranslator
import time
import re

OUTPUT_DIR = "output_mp3"

def main():
    player_files = glob.glob(os.path.join(OUTPUT_DIR, "*_player.json"))
    translator = GoogleTranslator(source='en', target='ko')
    
    count = 0
    for pf in player_files:
        with open(pf, "r", encoding="utf-8") as f:
            player_data = json.load(f)
            
        script = player_data.get("script", [])
        modified = False
        
        for p_seg in script:
            eng_text = p_seg["text"]
            
            # Remove existing Korean text (the bad hack from previous step)
            eng_text_clean = re.sub(r'[가-힣].*$', '', eng_text).strip()
            
            # If the text was changed, or if there was no Korean
            if eng_text_clean != eng_text or not re.search(r'[가-힣]', eng_text):
                try:
                    # Deep-translator has rate limits, let's add a small sleep
                    time.sleep(0.1)
                    ko_text = translator.translate(eng_text_clean)
                    p_seg["text"] = f"{eng_text_clean} {ko_text}"
                    modified = True
                except Exception as e:
                    print(f"Error translating: {eng_text_clean} - {e}")
                    # Revert to original if failed
                    p_seg["text"] = eng_text_clean
                    modified = True
                    
        if modified:
            with open(pf, "w", encoding="utf-8") as f:
                json.dump(player_data, f, ensure_ascii=False, indent=2)
            print(f"Translated: {os.path.basename(pf)}")
            count += 1
            
    print(f"\nDone! Translated {count} files.")

if __name__ == "__main__":
    main()
