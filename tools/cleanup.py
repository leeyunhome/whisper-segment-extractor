"""
전체 데이터 초기화 스크립트.

1. Supabase DB (episodes 테이블) 데이터 삭제
2. Supabase Storage (episodes 버킷) 파일 삭제
3. 로컬 output_mp3/ 파일 삭제
4. GitHub Pages (temp_repo) 파일 삭제 및 Push

주의: 이 작업은 되돌릴 수 없습니다.
"""

import os
import shutil
import sys
import subprocess
from pathlib import Path
from dotenv import load_dotenv

# 프로젝트 루트 경로 추가
PROJECT_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(PROJECT_DIR))

from src.config import (
    SUPABASE_URL, 
    SUPABASE_SERVICE_ROLE_KEY, 
    SUPABASE_BUCKET_NAME,
    OUTPUT_MP3_DIR
)

def confirm_action(message):
    print(f"\n⚠️  {message}")
    ans = input("정말 진행하시겠습니까? (yes/no): ").lower()
    return ans == "yes"

def cleanup_supabase():
    print("\n[1/4] Supabase 데이터 삭제 중...")
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        print("❌ Supabase 설정이 없습니다. 건너뜁니다.")
        return

    try:
        from supabase import create_client
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

        # 1. DB 삭제
        print("   - DB 레코드 삭제 중 (episodes 테이블)...")
        # 모든 행 삭제 (id 가 0이 아닌 것들 - 사실상 전부)
        res = supabase.table("episodes").delete().neq("id", 0).execute()
        print(f"   ✅ DB 레코드 삭제 완료")

        # 2. Storage 삭제
        print(f"   - Storage 파일 삭제 중 ({SUPABASE_BUCKET_NAME}/episodes)...")
        # 파일 목록 가져오기
        files = supabase.storage.from_(SUPABASE_BUCKET_NAME).list("episodes")
        if files:
            file_names = [f"episodes/{f['name']}" for f in files if f['name'] != '.emptyKeep']
            if file_names:
                supabase.storage.from_(SUPABASE_BUCKET_NAME).remove(file_names)
                print(f"   ✅ Storage 파일 {len(file_names)}개 삭제 완료")
            else:
                print("   - 삭제할 파일이 없습니다.")
        else:
            print("   - 삭제할 파일이 없습니다.")

    except Exception as e:
        print(f"   ❌ Supabase 삭제 중 오류 발생: {e}")

def cleanup_local():
    print("\n[2/4] 로컬 출력 파일 삭제 중...")
    if OUTPUT_MP3_DIR.exists():
        count = 0
        # mp3, json, txt, html 등 삭제
        extensions = ["*.mp3", "*.json", "*.txt", "*.html"]
        for ext in extensions:
            for f in OUTPUT_MP3_DIR.glob(ext):
                f.unlink()
                count += 1
        print(f"   ✅ {count}개 로컬 파일 삭제 완료")
    else:
        print("   - output_mp3 폴더가 없습니다.")

def cleanup_github():
    print("\n[3/4] GitHub Pages (temp_repo) 동기화 중...")
    temp_repo = PROJECT_DIR / "temp_repo"
    if not temp_repo.exists():
        print("   - temp_repo 폴더가 없어 건너뜁니다.")
        return

    try:
        # 1. 파일 삭제 (README.md, .git 제외)
        count = 0
        for f in temp_repo.iterdir():
            if f.name in [".git", "README.md"]:
                continue
            if f.is_file():
                f.unlink()
                count += 1
            elif f.is_dir():
                shutil.rmtree(f)
                count += 1
        
        print(f"   - {count}개 파일 삭제됨. Git Push 시도 중...")

        # 2. Push
        subprocess.run(["git", "add", "."], cwd=temp_repo, check=True, capture_output=True)
        # 변경사항 확인
        status = subprocess.run(["git", "status", "--porcelain"], cwd=temp_repo, check=True, capture_output=True, text=True)
        if not status.stdout.strip():
            print("   - 변경 사항이 없어 Push를 건너뜁니다.")
            return

        subprocess.run(["git", "commit", "-m", "Reset: Clear all episodes for testing"], cwd=temp_repo, check=True, capture_output=True)
        subprocess.run(["git", "push", "origin", "main"], cwd=temp_repo, check=True, capture_output=True)
        print("   ✅ GitHub Pages 초기화 완료")

    except Exception as e:
        print(f"   ❌ GitHub 초기화 중 오류 발생: {e}")

def main():
    print("="*60)
    print("🚀 EBS 오디오 학습 데이터 전체 초기화")
    print("="*60)
    print("대상:")
    print("1. Supabase Database (episodes)")
    print("2. Supabase Storage (episodes/episodes/*)")
    print("3. Local Output (output_mp3/*)")
    print("4. GitHub Pages (temp_repo/*)")
    
    if not confirm_action("모든 데이터가 영구적으로 삭제됩니다."):
        print("\n취소되었습니다.")
        return

    cleanup_supabase()
    cleanup_local()
    cleanup_github()

    print("\n" + "="*60)
    print("✨ 모든 데이터 초기화가 완료되었습니다.")
    print("="*60)

if __name__ == "__main__":
    main()
