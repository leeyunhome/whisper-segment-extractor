import re
import os
import whisper
from pydub import AudioSegment
import datetime

def log_to_file(message, filepath="investigation_result.txt"):
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(message + "\n")

def parse_history(history_path):
    with open(history_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    blocks = content.split('######')
    data = []
    
    for block in blocks:
        path_match = re.search(r'file_path\s*=\s*["\'](.+?)["\']', block)
        if not path_match: continue
        
        path = path_match.group(1)
        
        start_match = re.search(r'start_time\s*=\s*\((.+?)\)\s*\*\s*1000', block)
        end_match = re.search(r'end_time\s*=\s*\((.+?)\)\s*\*\s*1000', block)
        
        if start_match and end_match:
            start_expr = start_match.group(1)
            end_expr = end_match.group(1)
            start_seconds = eval(start_expr)
            end_seconds = eval(end_expr)
            
            data.append({
                'path': path,
                'start_sec': start_seconds,
                'end_sec': end_seconds
            })
            
    return data

def analyze_cuts(data_list, model_size='base'):
    # Clear previous log
    with open("investigation_result.txt", "w", encoding="utf-8") as f:
        f.write("Analysis Started\n")

    msg = f"Loading Whisper model ({model_size})..."
    print(msg)
    log_to_file(msg)
    
    model = whisper.load_model(model_size)
    
    for item in data_list:
        path = item['path'].replace("./", "")
        full_path = os.path.abspath(path)
        
        if not os.path.exists(full_path):
             if os.path.exists(os.path.join("source_mp3", os.path.basename(path))):
                 full_path = os.path.abspath(os.path.join("source_mp3", os.path.basename(path)))
             else:
                 msg = f"File not found: {path}"
                 print(msg)
                 log_to_file(msg)
                 continue
        
        header = f"\n{'='*60}\nAnalyzing: {os.path.basename(full_path)}\nManual Cut: {item['start_sec']}s ~ {item['end_sec']}s\n{'='*60}"
        print(header)
        log_to_file(header)
        
        audio = AudioSegment.from_mp3(full_path)
        
        analyze_boundary(model, audio, item['start_sec'], "START")
        analyze_boundary(model, audio, item['end_sec'], "END")

def analyze_boundary(model, audio, pivot_sec, label):
    start_window = max(0, pivot_sec - 5)
    end_window = pivot_sec + 5
    
    start_ms = int(start_window * 1000)
    end_ms = int(end_window * 1000)
    
    clip = audio[start_ms : end_ms]
    temp_filename = "temp_analysis.mp3"
    clip.export(temp_filename, format="mp3")
    
    result = model.transcribe(temp_filename, word_timestamps=True, language='ko') 
    
    header = f"\n🔍 {label} Boundary Analysis (Window: {start_window:.1f}s ~ {end_window:.1f}s)\n   Target Cut Point (Relative): 5.0s (Absolute: {pivot_sec:.2f}s)"
    print(header)
    log_to_file(header)
    
    for seg in result['segments']:
        if 'words' in seg:
            for word in seg['words']:
                w_start = word['start']
                w_end = word['end']
                
                marker = ""
                dist = w_start - 5.0
                
                if abs(dist) < 0.5:
                    marker = f" <--- [{dist:+.2f}s]"
                
                line = f"     [{start_window + w_start:.2f} - {start_window + w_end:.2f}] {word['word']}{marker}"
                print(line)
                log_to_file(line)
        else:
            line = f"   [{start_window + seg['start']:.2f} - {start_window + seg['end']:.2f}] {seg['text']}"
            print(line)
            log_to_file(line)

    if os.path.exists(temp_filename):
        os.remove(temp_filename)

if __name__ == "__main__":
    history_file = "extract_history.txt"
    if os.path.exists(history_file):
        data = parse_history(history_file)
        if data:
            analyze_cuts(data)
        else:
            print("No valid data found in history file.")
    else:
        print(f"{history_file} not found.")
