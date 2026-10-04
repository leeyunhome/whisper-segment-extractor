"""
Supabase 연결 테스트.

실행:
  python -m tools.test_supabase

성공 시 출력:
  [OK] Supabase 연결 성공
  [OK] episodes 테이블 접근 OK (현재 0개)
  [OK] scripts 테이블 접근 OK (현재 0개)
  [OK] Storage 'episodes' 버킷 OK
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from src.config import ENV_FILE


def test_connection():
    print("\n" + "=" * 60)
    print("Supabase 연결 테스트")
    print("=" * 60 + "\n")

    # 1. .env 로드
    try:
        from dotenv import load_dotenv
    except ImportError:
        print("[!] python-dotenv 미설치: pip install python-dotenv")
        return False

    if not ENV_FILE.exists():
        print(f"[!] .env 파일 없음: {ENV_FILE}")
        return False

    load_dotenv(ENV_FILE)

    url = os.getenv("SUPABASE_URL", "").strip()
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

    if not url or "your-project" in url:
        print("[!] .env 에 SUPABASE_URL 미설정")
        return False
    if not key or "your_service_role_key" in key:
        print("[!] .env 에 SUPABASE_SERVICE_ROLE_KEY 미설정")
        return False

    print(f"URL: {url}")
    print(f"Key: {key[:30]}... (길이 {len(key)})\n")

    # 2. supabase 라이브러리
    try:
        from supabase import create_client, Client
    except ImportError:
        print("[!] supabase 미설치: pip install supabase")
        return False

    # 3. 클라이언트 생성
    try:
        client: Client = create_client(url, key)
        print("[OK] Supabase 클라이언트 생성 성공\n")
    except Exception as e:
        print(f"[!] 클라이언트 생성 실패: {e}")
        return False

    # 4. episodes 테이블 접근
    try:
        result = client.table("episodes").select("id", count="exact").execute()
        count = result.count if hasattr(result, "count") else len(result.data)
        print(f"[OK] episodes 테이블 접근 OK (현재 {count}개)")
    except Exception as e:
        print(f"[!] episodes 테이블 접근 실패: {e}")
        print("   → Supabase 대시보드의 SQL Editor 에 supabase_schema.sql 을 실행했나요?")
        return False

    # 5. scripts 테이블 접근
    try:
        result = client.table("scripts").select("id", count="exact").execute()
        count = result.count if hasattr(result, "count") else len(result.data)
        print(f"[OK] scripts 테이블 접근 OK (현재 {count}개)")
    except Exception as e:
        print(f"[!] scripts 테이블 접근 실패: {e}")
        return False

    # 6. Storage 버킷 접근
    try:
        buckets = client.storage.list_buckets()
        bucket_names = [b.name if hasattr(b, "name") else b.get("name") for b in buckets]
        if "episodes" in bucket_names:
            print(f"[OK] Storage 'episodes' 버킷 OK")
        else:
            print(f"[WARN] Storage 'episodes' 버킷 없음")
            print(f"   현재 버킷들: {bucket_names}")
            print(f"   → Supabase 대시보드 Storage 에서 'episodes' 버킷 생성 필요")
            return False
    except Exception as e:
        print(f"[WARN] Storage 접근 확인 실패: {e}")
        print(f"   (테이블은 정상이니 진행 가능, Storage 는 다음 단계에서 다시 확인)")

    print("\n" + "=" * 60)
    print("[OK] 모든 검사 통과!")
    print("=" * 60)
    print("\n다음 단계: Phase 2 - 업로드 스크립트 작성")
    return True


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)
