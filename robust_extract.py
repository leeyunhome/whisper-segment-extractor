import whisper
import os
import argparse
import re
from pydub import AudioSegment
import json

class RobustExtractor:
    def __init__(self, model_size='base'):
        self.model_size = model_size
        self.model = None

    def load_model(self):
        if self.model is None:
            print(f"Loading Whisper model ({self.model_size})...")
            self.model = whisper.load_model(self.model_size)

    def extract(self, file_path, output_dir="extracted_mp3"):
        self.load_model()
        
        print(f"Processing {file_path}...")
        
        # Optimize: Only transcribe the relevant window (21m to 27m)
        audio = AudioSegment.from_mp3(file_path)
        
        window_start_sec = 1260
        window_end_sec = 1620
        
        if len(audio) < window_start_sec * 1000:
            print("Audio too short for window.")
            return 0, 0
            
        window_audio = audio[window_start_sec*1000 : window_end_sec*1000]
        temp_path = "temp_window.mp3"
        window_audio.export(temp_path, format="mp3")
        
        print(f"Transcribing window ({window_start_sec}s ~ {window_end_sec}s)...")
        result = self.model.transcribe(temp_path, language='ko', verbose=False)
        
        segments = result['segments']
        for seg in segments:
            seg['start'] += window_start_sec
            seg['end'] += window_start_sec
            
        os.remove(temp_path)
        
        # 1. Find START
        start_time = 0.0
        start_found = False
        
        start_anchors = ["전체대화", "전체 대화"]
        start_confirmation = ["주세요", "들어볼게요", "들어 볼게요"]
        fallback_anchors = ["미션 정리하겠습니다", "미션 정리"]
        
        for i, seg in enumerate(segments):
            text = seg['text']
            
            # Priority 1: Main Anchor
            if any(a in text for a in start_anchors):
                if any(c in text for c in start_confirmation):
                    start_time = seg['end']
                    start_found = True
                    print(f"Found START anchor: '{text}' at {seg['end']:.2f}s")
                    break
                if i + 1 < len(segments):
                    next_text = segments[i+1]['text']
                    if any(c in next_text for c in start_confirmation):
                        start_time = segments[i+1]['end']
                        start_found = True
                        print(f"Found START anchor sequence: '{text}' -> '{next_text}' at {segments[i+1]['end']:.2f}s")
                        break
        
        # Priority 2: Fallback + English Block
        if not start_found:
            for i, seg in enumerate(segments):
                if any(fb in seg['text'] for fb in fallback_anchors):
                    print(f"Found FALLBACK anchor: '{seg['text']}' at {seg['end']:.2f}s")
                    
                    # Look for 2 consecutive English segments
                    for j in range(i + 1, min(i + 30, len(segments) - 1)):
                        curr_seg = segments[j]
                        next_seg = segments[j+1]
                        
                        is_curr_eng = not any('가' <= c <= '힣' for c in curr_seg['text'])
                        is_next_eng = not any('가' <= c <= '힣' for c in next_seg['text'])
                        
                        if is_curr_eng and is_next_eng:
                            start_time = curr_seg['start']
                            start_found = True
                            print(f"Found Conversation Start (English Block) after fallback: '{curr_seg['text']}' at {curr_seg['start']:.2f}s")
                            break
                    if start_found: break
            
            # Relaxed single check
            if not start_found:
                 for i, seg in enumerate(segments):
                    if any(fb in seg['text'] for fb in fallback_anchors):
                         for j in range(i + 1, min(i + 30, len(segments))):
                            if not any('가' <= c <= '힣' for c in segments[j]['text']):
                                start_time = segments[j]['start']
                                start_found = True
                                print(f"Found Conversation Start (Single English) after fallback: '{segments[j]['text']}' at {segments[j]['start']:.2f}s")
                                break
                         if start_found: break
            
        if not start_found:
            for seg in segments:
                if "전체대화 주세요" in seg['text'].replace(" ",""):
                    start_time = seg['end']
                    start_found = True
                    print(f"Found START anchor (last resort): '{seg['text']}' at {seg['end']:.2f}s")
                    break

        if start_found:
             start_time = max(0, start_time - 0.1)
        else:
            print("WARNING: Could not find clear START anchor. Defaulting to 1350s.")
            start_time = 1350.0

        # 2. Find END
        end_time = 0.0
        end_found = False
        end_markers = ["입으로", "영작", "이병작", "입영작", "타임", "만들어보는", "직접"]
        
        for i, seg in enumerate(segments):
            if seg['start'] < start_time + 20: 
                continue
                
            text = seg['text']
            if any(marker in text for marker in end_markers):
                target_idx = i
                if i > 0:
                    prev = segments[i-1]
                    if prev['text'].strip() in ["네,", "네.", "자,", "자."]:
                        target_idx = i - 1
                        print(f"Found transition marker '{prev['text']}' before explanation.")
                
                end_time = segments[target_idx]['start']
                end_found = True
                print(f"Found END anchor: Explanation starts at '{segments[target_idx]['text']}' ({segments[target_idx]['start']:.2f}s)")
                break
        
        if end_found:
            # Cut EXACTLY at the start of the explanation sound. No buffer.
            end_time -= 0.0
        else:
            print("WARNING: Could not find END anchor. Defaulting to Start + 45s.")
            end_time = start_time + 45.0

        print(f"Proposed Cut: {start_time:.2f}s ~ {end_time:.2f}s (Duration: {end_time - start_time:.2f}s)")
        
        # 3. Export & Script
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
            
            start_ms = int(start_time * 1000)
            end_ms = int(end_time * 1000)
            
            extract = audio[start_ms:end_ms]
            
            filename = os.path.basename(file_path)
            base_name_no_ext = os.path.splitext(filename)[0]
            save_path = os.path.join(output_dir, f"robust_{filename}")
            
            extract.export(save_path, format="mp3")
            print(f"Saved audio to {save_path}")
            
            # 4. Generate Script
            self.generate_script(save_path, output_dir, f"robust_{base_name_no_ext}.txt")
            
        return start_time, end_time

    def generate_script(self, audio_path, output_dir, text_filename):
        print(f"Generating script for {os.path.basename(audio_path)}...")
        
        result = self.model.transcribe(audio_path, language='en', verbose=False)
        
        full_text = ""
        for seg in result['segments']:
            full_text += " " + seg['text'].strip()
            
        full_text = re.sub(r'\s+', ' ', full_text).strip()
        sentences = re.split(r'(?<=[.?!])\s+', full_text)
        
        unique_lines = []
        seen_lines_norm = set()
        
        for line in sentences:
            text = line.strip()
            if len(text) < 5: continue 
            
            text_norm = re.sub(r'[^\w\s]', '', text.lower())
            
            if text_norm in seen_lines_norm:
                continue
            
            is_duplicate = False
            for seen in seen_lines_norm:
                len_ratio = min(len(text_norm), len(seen)) / max(len(text_norm), len(seen))
                if len_ratio > 0.8 and (text_norm in seen or seen in text_norm):
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_lines.append(text)
                seen_lines_norm.add(text_norm)
        
        script_path = os.path.join(output_dir, text_filename)
        with open(script_path, 'w', encoding='utf-8') as f:
            for line in unique_lines:
                f.write(line + "\n")
                
        print(f"Script saved to {script_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs='+', help="MP3 files to process")
    args = parser.parse_args()
    
    extractor = RobustExtractor()
    for f in args.files:
        extractor.extract(f)
