"""
Analyze MP3 file patterns to understand extraction timing
"""
import json
import os
from pathlib import Path

# Files to analyze
files = [
    "20260107_173000_fca95311_mp3.mp3",
    "20260105_173000_36debe60_mp3.mp3",
    "20260106_173000_a495f72c_mp3.mp3",
    "20260102_173000_80902ef1_mp3.mp3",
    "20251230_173000_59b81a3e_mp3.mp3",
]

print("=" * 80)
print("MP3 FILE PATTERN ANALYSIS")
print("=" * 80)

for filename in files:
    base = filename.replace(".mp3", "")
    transcription_file = f"transcription_{base}.json"
    script_file = f"script_{base}.txt"
    
    print(f"\n{'='*80}")
    print(f"FILE: {filename}")
    print(f"{'='*80}")
    
    # Read transcription
    if os.path.exists(transcription_file):
        with open(transcription_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            segments = data.get('segments', [])
            
            print(f"\nTotal segments: {len(segments)}")
            
            # Find anchor phrase
            anchor_found = False
            anchor_time = None
            for seg in segments:
                text = seg.get('text', '').strip()
                if '전체' in text and '대화' in text:
                    anchor_found = True
                    anchor_time = seg.get('start', 0)
                    print(f"\n✓ Anchor phrase found at {anchor_time:.2f}s: '{text}'")
                    break
            
            if not anchor_found:
                print("\n✗ Anchor phrase NOT found")
                continue
            
            # Find segments after anchor
            print(f"\n--- Segments after anchor ({anchor_time:.2f}s) ---")
            after_anchor = [s for s in segments if s.get('start', 0) > anchor_time]
            
            # Show first 20 segments after anchor
            for i, seg in enumerate(after_anchor[:20]):
                start = seg.get('start', 0)
                end = seg.get('end', 0)
                text = seg.get('text', '').strip()
                duration = end - start
                print(f"{i+1:2d}. [{start:6.2f}s - {end:6.2f}s] ({duration:4.1f}s) {text[:60]}")
    
    # Read script
    if os.path.exists(script_file):
        with open(script_file, 'r', encoding='utf-8') as f:
            script_content = f.read()
            print(f"\n--- Current Script Output ---")
            print(script_content)
    
    print()

print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)
