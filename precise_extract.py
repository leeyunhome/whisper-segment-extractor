
import os
import json
import argparse
from pydub import AudioSegment

class PreciseExtractor:
    def __init__(self, model_size='tiny'):
        self.model_size = model_size
        self.model = None
        self.start_anchors = [
            "전체대화", "전체 대화", "전체되어", "전체 되어", "전체대화 주세요", "전체대화주세요",
            "전체대와", "전체 대와", "전체대와들", "전체 대와들", "전체대화들", "전체 대화들"
        ]

    def load_model(self):
        if self.model is None:
            import whisper
            print(f"Loading Whisper model ({self.model_size})...")
            self.model = whisper.load_model(self.model_size)

    def get_transcription(self, audio_path):
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        json_path = f"transcription_{base_name}.json"
        
        if os.path.exists(json_path):
            print(f"Loading existing transcription: {json_path}")
            with open(json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        print("Transcribing (this may take a while)...")
        self.load_model()
        result = self.model.transcribe(audio_path, language='ko', verbose=False)
        
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
            
        return result

    def is_korean(self, text):
        return any('가' <= c <= '힣' for c in text)

    def find_cut_points(self, transcription):
        segments = transcription['segments']
        start_time = None
        end_time = None
        
        # 1. Find Start
        start_anchor_idx = -1
        for i, seg in enumerate(segments):
            text = seg['text'].replace(" ", "")
            for anchor in self.start_anchors:
                if anchor.replace(" ", "") in text:
                    start_anchor_idx = i
                    print(f"Found START anchor at [{seg['start']:.2f}]: {seg['text']}")
                    break
            if start_anchor_idx != -1:
                break
        
        if start_anchor_idx != -1:
            start_time = segments[start_anchor_idx]['end']
            
            # 2. Find End: Scan forward until Korean explanation starts
            # Robustness: Ignore "Korean" segments if conversation duration is short (<10s).
            # This handles cases where "Thank you" (KO) appears at start or noise.
            
            english_start_time = None
            
            for i in range(start_anchor_idx + 1, len(segments)):
                seg = segments[i]
                start = seg['start']
                end = seg['end']
                
                if self.is_korean(seg['text']):
                    current_duration = start - start_time
                    
                    # If very short duration so far (<10s), likely intro noise, skip.
                    if current_duration <= 10.0:
                        print(f"  Skipping short Korean segment at [{start:.2f}-{end:.2f}]: {seg['text']}")
                        continue
                        
                    # If duration > 10s, potential end. Check Lookahead.
                    # If next 2 segments contain English, this might be an interpolation.
                    is_real_end = True
                    lookahead_count = 0
                    for j in range(i + 1, min(i + 3, len(segments))):
                         if not self.is_korean(segments[j]['text']):
                             # Found validation that conversation continues
                             is_real_end = False
                             print(f"  Ignoring Korean segment at [{start:.2f}] because English follows at [{segments[j]['start']:.2f}]")
                             break
                    
                    if is_real_end:
                        print(f"Found END trigger (Korean) at [{start:.2f}]: {seg['text']}")
                        end_time = start
                        break
                    
                else:
                    # English segment
                    pass
                
                if seg['start'] - start_time > 300:
                    print("Warning: No end found within 5 minutes.")
                    end_time = seg['end']
                    break

        return start_time, end_time

    def process(self, audio_path, dry_run=False):
        print(f"Processing: {audio_path}")
        transcription = self.get_transcription(audio_path)
        
        start, end = self.find_cut_points(transcription)
        
        if start and end:
            print(f"Proposed Cut: {start:.2f}s ~ {end:.2f}s (Duration: {end-start:.2f}s)")
            
            if not dry_run:
                self.extract_audio(audio_path, start, end)
        else:
            print("Could not find start/end points.")

    def extract_audio(self, audio_path, start, end):
        print("Exporting audio...")
        audio = AudioSegment.from_mp3(audio_path)
        start_ms = int(start * 1000)
        end_ms = int(end * 1000)
        
        extract = audio[start_ms:end_ms]
        
        base_name = os.path.splitext(os.path.basename(audio_path))[0]
        output_path = f"precise_{base_name}.mp3"
        
        extract.export(output_path, format="mp3", bitrate="320k")
        print(f"Saved to {output_path}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs='+', help="MP3 files to process")
    parser.add_argument("--dry-run", action="store_true", help="Don't save, just print times")
    args = parser.parse_args()
    
    extractor = PreciseExtractor()
    for f in args.files:
        extractor.process(f, dry_run=args.dry_run)
