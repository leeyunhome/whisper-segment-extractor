"""
MP3 파일 분석 스크립트

원본 파일(20251xxx_xxx.mp3)과 잘라낸 파일(왕초보영어_xxx.mp3)을 
비교하여 추출 패턴을 찾습니다.
"""

from pydub import AudioSegment
import os
from pathlib import Path

def analyze_mp3_files():
    """폴더 내 모든 MP3 파일 분석"""
    
    # 파일 목록
    files = [
        "20251218_173000_f47b47fc_mp3.mp3",
        "20251219_173000_0476451b_mp3.mp3",
        "20251224_173000_b21928fa_mp3.mp3",
        "왕초보영어_뉴욕의_로맨틱한밤_20251219.mp3",
        "왕초보영어_딸의_남자친구와_첫만남_20251218.mp3",
        "왕초보영어_직업_막판_크리스마스_쇼핑_20251224.mp3",
    ]
    
    output_lines = []
    output_lines.append("="*80)
    output_lines.append("MP3 파일 분석 결과")
    output_lines.append("="*80)
    output_lines.append("")
    
    file_info = {}
    
    for filename in files:
        if not os.path.exists(filename):
            msg = f"⚠️  파일 없음: {filename}"
            print(msg)
            output_lines.append(msg)
            continue
        
        try:
            audio = AudioSegment.from_mp3(filename)
            duration_sec = len(audio) / 1000
            duration_min = duration_sec / 60
            
            file_info[filename] = {
                'duration_sec': duration_sec,
                'duration_min': duration_min,
                'size_mb': os.path.getsize(filename) / (1024*1024)
            }
            
            lines = [
                f"📄 {filename}",
                f"   ⏱️  길이: {duration_min:.2f}분 ({duration_sec:.1f}초)",
                f"   💾 크기: {file_info[filename]['size_mb']:.2f}MB",
                ""
            ]
            
            for line in lines:
                print(line)
                output_lines.append(line)
            
        except Exception as e:
            msg = f"❌ 오류: {filename} - {e}"
            print(msg)
            output_lines.append(msg)
            output_lines.append("")
    
    # 패턴 분석
    header = ["="*80, "파일 쌍 비교 (원본 vs 잘라낸 파일)", "="*80, ""]
    for line in header:
        print(line)
        output_lines.append(line)
    
    pairs = [
        ("20251218_173000_f47b47fc_mp3.mp3", "왕초보영어_딸의_남자친구와_첫만남_20251218.mp3"),
        ("20251219_173000_0476451b_mp3.mp3", "왕초보영어_뉴욕의_로맨틱한밤_20251219.mp3"),
        ("20251224_173000_b21928fa_mp3.mp3", "왕초보영어_직업_막판_크리스마스_쇼핑_20251224.mp3"),
    ]
    
    for original, extracted in pairs:
        if original in file_info and extracted in file_info:
            orig_dur = file_info[original]['duration_sec']
            extr_dur = file_info[extracted]['duration_sec']
            diff = orig_dur - extr_dur
            
            lines = [
                f"📊 {original.split('_')[0][-8:]} 날짜",
                f"   원본: {orig_dur:.1f}초 ({orig_dur/60:.2f}분)",
                f"   추출: {extr_dur:.1f}초 ({extr_dur/60:.2f}분)",
                f"   차이: {diff:.1f}초 ({diff/60:.2f}분)",
                f"   추출율: {(extr_dur/orig_dur)*100:.1f}%",
                ""
            ]
            
            for line in lines:
                print(line)
                output_lines.append(line)
    
    # 파일로 저장
    with open("analysis_result.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(output_lines))
    
    print("\n✅ 분석 결과가 analysis_result.txt에 저장되었습니다")

if __name__ == "__main__":
    analyze_mp3_files()
