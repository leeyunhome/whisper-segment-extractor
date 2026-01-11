
import os
import subprocess
import numpy as np
import scipy.signal

def load_audio_pcm(file_path, sample_rate=16000):
    """
    Decodes audio to raw PCM (s16le, mono) using ffmpeg and loads into numpy array.
    """
    cmd = [
        'ffmpeg',
        '-i', file_path,
        '-f', 's16le',
        '-ac', '1',
        '-ar', str(sample_rate),
        '-acodec', 'pcm_s16le',
        '-'
    ]
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, bufsize=10**8)
        raw_data, _ = process.communicate()
        audio_data = np.frombuffer(raw_data, dtype=np.int16)
        return audio_data, sample_rate
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        return None, None

def find_subsegment(original, extracted, sample_rate):
    """
    Finds the extracted AUDIO within the original audio.
    Returns start_seconds, end_seconds.
    Optimization: Sync on the first 30 seconds of the extracted audio.
    """
    if len(extracted) > len(original):
        print("Extracted file is longer than original!")
        return None, None

    # Sync using first 30s (or less)
    sync_duration = 30
    sync_samples = min(len(extracted), sync_duration * sample_rate)
    query = extracted[:sync_samples]

    # Convert to float for correlation
    query_f = query.astype(np.float32)
    original_f = original.astype(np.float32)
    
    # Standard valid correlation
    # For large arrays, FFT convolution is much faster.
    # scipy.signal.correlate calls fftconvolve if method='fft'.
    cross_corr = scipy.signal.correlate(original_f, query_f, mode='valid', method='fft')
    
    max_idx = np.argmax(cross_corr)
    
    # Timestamp
    start_seconds = max_idx / sample_rate
    duration = len(extracted) / sample_rate
    end_seconds = start_seconds + duration
    
    return start_seconds, end_seconds

def format_time(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    return f"{int(h):02d}:{int(m):02d}:{s:06.3f}"

def analyze_pair(orig_path, ext_path):
    print(f"Analyzing pair:\n  Original: {orig_path}\n  Extracted: {ext_path}")
    
    if not os.path.exists(orig_path) or not os.path.exists(ext_path):
        print("  Files not found.")
        return

    orig_pcm, sr = load_audio_pcm(orig_path)
    ext_pcm, _ = load_audio_pcm(ext_path)
    
    if orig_pcm is None or ext_pcm is None:
        return

    print(f"  Orig Duration: {format_time(len(orig_pcm)/sr)}")
    print(f"  Ext Duration:  {format_time(len(ext_pcm)/sr)}")
    
    start, end = find_subsegment(orig_pcm, ext_pcm, sr)
    
    if start is not None:
        print(f"  Found Match:")
        print(f"    Start: {format_time(start)} ({start:.3f}s)")
        print(f"    End:   {format_time(end)} ({end:.3f}s)")
    else:
        print("  No match found.")
    print("-" * 40)

if __name__ == "__main__":
    pairs = [
        ("20251226_173000_03fab520_mp3.mp3", "여행_연말_세일은_못_참지_20251226.mp3"),
        ("20251231_173000_fe521601_mp3.mp3", "직업_2026년에_만나요_여러분_20251231.mp3")
    ]
    
    for orig, ext in pairs:
        analyze_pair(orig, ext)
