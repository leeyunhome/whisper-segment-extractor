import whisper
import os
from pydub import AudioSegment

def debug_end():
    file_path = "source_mp3/20260108_173000_24c0ec4f_mp3.mp3"
    
    print(f"Loading Whisper model (base)...")
    model = whisper.load_model('base')
    
    # Analyze window around expected end (23:00 approx range)
    # 1390s to 1420s
    print("Extracting window (1390s - 1420s)...")
    audio = AudioSegment.from_mp3(file_path)
    window_start = 1390 * 1000
    window_end = 1420 * 1000
    
    clip = audio[window_start:window_end]
    clip.export("temp_debug_end.mp3", format="mp3")
    
    print("Transcribing with language='ko' (to catch actual segmentation)...")
    result = model.transcribe("temp_debug_end.mp3", language='ko')
    
    print("\nTranscription Result (Relative to 0s of clip, Absolute = +1390s):")
    print("-" * 50)
    
    with open("debug_end_result.txt", "w", encoding="utf-8") as f:
        for seg in result['segments']:
            start = seg['start'] + 1390
            end = seg['end'] + 1390
            text = seg['text'].strip()
            line = f"[{start:.2f}s - {end:.2f}s] {text}"
            print(line)
            f.write(line + "\n")
        
    os.remove("temp_debug_end.mp3")

if __name__ == "__main__":
    debug_end()
