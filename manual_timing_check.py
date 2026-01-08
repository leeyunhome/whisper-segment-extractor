"""
Manual timing analysis for 20260107 file
User says native conversation is at 22:53 - 23:38 (1373s - 1418s)
"""
import json

# Load the transcription
with open("transcription_20260107_173000_fca95311_mp3.json", 'r', encoding='utf-8') as f:
    data = json.load(f)

segments = data.get('segments', [])

print("="*80)
print("TIMING ANALYSIS: 20260107_173000_fca95311_mp3.mp3")
print("="*80)
print(f"\nUser says native conversation: 22:53 - 23:38 (1373s - 1418s)")
print(f"Total segments: {len(segments)}\n")

# Find anchor
print("="*80)
print("1. FINDING ANCHOR PHRASE")
print("="*80)
for seg in segments:
    text = seg.get('text', '').strip()
    if '전체' in text and '대화' in text:
        print(f"\n✓ Anchor found at {seg['start']:.2f}s ({seg['start']/60:.2f}min)")
        print(f"  Text: '{text}'")
        print(f"  End: {seg['end']:.2f}s")
        anchor_time = seg['end']
        break

# Show segments around the expected time (22:53 = 1373s)
print("\n" + "="*80)
print("2. SEGMENTS AROUND EXPECTED START TIME (22:53 = 1373s)")
print("="*80)
for seg in segments:
    start = seg['start']
    end = seg['end']
    if 1360 <= start <= 1390:  # 10 seconds before and after
        text = seg['text'].strip()
        print(f"[{start:7.2f}s - {end:7.2f}s] ({start/60:.2f}min) {text}")

# Show segments around expected end time (23:38 = 1418s)
print("\n" + "="*80)
print("3. SEGMENTS AROUND EXPECTED END TIME (23:38 = 1418s)")
print("="*80)
for seg in segments:
    start = seg['start']
    end = seg['end']
    if 1400 <= start <= 1430:
        text = seg['text'].strip()
        print(f"[{start:7.2f}s - {end:7.2f}s] ({start/60:.2f}min) {text}")

# Show what was actually extracted
print("\n" + "="*80)
print("4. CURRENT SCRIPT OUTPUT")
print("="*80)
with open("script_20260107_173000_fca95311_mp3.txt", 'r', encoding='utf-8') as f:
    print(f.read())

print("\n" + "="*80)
print("ANALYSIS COMPLETE")
print("="*80)
