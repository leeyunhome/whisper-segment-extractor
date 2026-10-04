import sys
import json
from pathlib import Path
from src.uploader import process_and_upload
from src.config import OUTPUT_MP3_DIR, EPISODE_INFO_DIR

def test_manual_upload():
    # 테스트할 파일들
    basename = "2707_여행_여행_가이드가_추천한_포토존_20260501"
    info_file = EPISODE_INFO_DIR / "60714983.json"
    
    if not info_file.exists():
        print(f"[!] Info 파일 없음: {info_file}")
        return
        
    with open(info_file, "r", encoding="utf-8") as f:
        episode_info = json.load(f)
        
    print(f"[START] 테스트 업로드 시작: {basename}")
    success = process_and_upload(basename, OUTPUT_MP3_DIR, episode_info)
    
    if success:
        print("[OK] 테스트 업로드 성공!")
    else:
        print("[!] 테스트 업로드 실패")

if __name__ == "__main__":
    test_manual_upload()
