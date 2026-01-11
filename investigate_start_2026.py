import whisper
import os
from pydub import AudioSegment

def debug_file():
    file_path = "source_mp3/20260102_173000_80902ef1_mp3.mp3"
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return

    print(f"Loading Whisper model (base)...")
    model = whisper.load_model('base')
    
    # Analyze window around expected start (21:00 - 24:00)
    print("Extracting window (21:00 - 24:00)...")
    audio = AudioSegment.from_mp3(file_path)
    window_start = 1260 * 1000
    window_end = 1440 * 1000
    
    clip = audio[window_start:window_end]
    clip.export("temp_debug_start.mp3", format="mp3")
    
    print("Transcribing with language='ko'...")
    result = model.transcribe("temp_debug_start.mp3", language='ko')
    
    print("\nTranscription Result (Relative to 21:00):")
    print("-" * 50)
    
    with open("investigation_start_result.txt", "w", encoding="utf-8") as f:
        for seg in result['segments']:
            start = seg['start'] + 1260
            text = seg['text'].strip()
            line = f"[{start:.2f}s] {text}"
            print(line)
            f.write(line + "\n")
        
    os.remove("temp_debug_start.mp3")

if __name__ == "__main__":
    debug_file()
