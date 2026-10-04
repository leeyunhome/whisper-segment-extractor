import sys, os
sys.path.insert(0, r"C:\coding\github-repository\whisper-segment-extractor")
os.chdir(r"C:\coding\github-repository\whisper-segment-extractor")

# Windows CUDA DLL 경로 등록 (extractor.py 수정과 동일한 로직)
import torch
_torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
if os.path.isdir(_torch_lib):
    os.add_dll_directory(_torch_lib)

from faster_whisper import WhisperModel
from pydub import AudioSegment

audio_path = r"source_mp3\20260525_090000_c4e47613_mp3.mp3"
print(f"파일 크기: {os.path.getsize(audio_path)/1024/1024:.1f} MB")

audio_full = AudioSegment.from_mp3(audio_path)
start_ms = 21 * 60 * 1000
audio_segment = audio_full[start_ms:]
audio_segment.export("temp_segment.mp3", format="mp3")
print("temp_segment.mp3 생성 완료")

print("Whisper 로딩...")
model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
print("Whisper 전사 시작...")
segments, info = model.transcribe("temp_segment.mp3", language="ko", beam_size=5)
segs = list(segments)
print(f"전사 완료: {len(segs)}개 세그먼트")
for s in segs[:5]:
    print(f"  [{s.start+1260:.1f}s] {s.text}")
print("OK")
