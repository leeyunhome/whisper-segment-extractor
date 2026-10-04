import os
import shutil
import time
from pathlib import Path
import sys

# 프로젝트 루트를 경로에 추가
sys.path.append(os.getcwd())

from src.config import (
    SOURCE_MP3_DIR, OUTPUT_MP3_DIR, EPISODE_INFO_DIR,
    SUPABASE_BUCKET_NAME, PROJECT_DIR
)
from src.supabase_util import get_supabase_manager

def reset_local_data():
    print("[LOCAL] 데이터 삭제 중...")
    
    dirs_to_clear = [
        SOURCE_MP3_DIR,
        OUTPUT_MP3_DIR,
        EPISODE_INFO_DIR,
        PROJECT_DIR / "extracted_mp3",
        PROJECT_DIR / "archive"
    ]
    
    for d in dirs_to_clear:
        if d.exists():
            print(f"   - {d.relative_to(PROJECT_DIR)} 비우는 중...")
            for item in d.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item)
        else:
            d.mkdir(parents=True, exist_ok=True)

    # 루트 폴더의 부산물 삭제
    patterns = ["transcription_*.json", "player_*.json", "script_*.txt", "extracted_*.mp3"]
    for pattern in patterns:
        for f in PROJECT_DIR.glob(pattern):
            f.unlink()
            print(f"   - {f.name} 삭제됨")

    print("[LOCAL] 초기화 완료\n")

def reset_supabase_data():
    print("[SUPABASE] 데이터 삭제 중...")
    manager = get_supabase_manager()
    
    # 1. DB 삭제 (scripts 는 CASCADE 삭제됨)
    print("   - DB 테이블 (episodes, scripts) 비우는 중...")
    try:
        # 모든 행 삭제 (id > 0)
        manager.client.table("episodes").delete().neq("id", -1).execute()
        print("   - DB 삭제 완료")
    except Exception as e:
        print(f"   [WARN] DB 삭제 실패: {e}")

    # 2. Storage 삭제 (재귀적 삭제)
    print(f"   - Storage 버킷 ({SUPABASE_BUCKET_NAME}) 비우는 중...")
    
    def delete_recursive(path=""):
        try:
            items = manager.client.storage.from_(SUPABASE_BUCKET_NAME).list(path)
            if not items:
                return
            
            files_to_remove = []
            for item in items:
                item_name = item['name']
                if item_name == '.emptyKeep':
                    continue
                
                full_path = f"{path}/{item_name}" if path else item_name
                
                # id가 있으면 파일, 없으면 폴더 (Supabase API 특성상 metadata가 있으면 파일)
                if item.get('id'):
                    files_to_remove.append(full_path)
                else:
                    # 폴더인 경우 재귀 호출
                    delete_recursive(full_path)
            
            if files_to_remove:
                manager.client.storage.from_(SUPABASE_BUCKET_NAME).remove(files_to_remove)
                print(f"   - {len(files_to_remove)}개 파일 삭제됨 ({path or 'root'})")
        except Exception as e:
            print(f"   [WARN] {path} 삭제 중 오류: {e}")

    delete_recursive()
    print("[SUPABASE] 초기화 완료\n")

def main():
    start_time = time.time()
    start_str = time.strftime("%Y-%m-%d %H:%M:%S")
    print(f"[RESET] 작업을 시작합니다. (시작: {start_str})")
    print("=" * 60)

    try:
        reset_local_data()
        reset_supabase_data()
    except Exception as e:
        print(f"\n[ERROR] 중단됨: {e}")
    
    end_time = time.time()
    duration = end_time - start_time
    end_str = time.strftime("%Y-%m-%d %H:%M:%S")
    
    print("=" * 60)
    print(f"[DONE] 모든 데이터가 삭제되었습니다.")
    print(f"   - 시작 시간: {start_str}")
    print(f"   - 종료 시간: {end_str}")
    print(f"   - 소요 시간: {duration:.2f}초")
    print("=" * 60)

if __name__ == "__main__":
    main()
