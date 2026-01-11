
import json
import sys

def search_text(json_path, query):
    print(f"Searching {json_path} for '{query}'...")
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        found = False
        for seg in data['segments']:
            if query in seg['text']:
                print(f"[{seg['start']:.2f}-{seg['end']:.2f}] {seg['text']}")
                found = True
        
        if not found:
            print("No matches found.")
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    search_text("transcription_20260108_173000_24c0ec4f_mp3.json", "전체")
