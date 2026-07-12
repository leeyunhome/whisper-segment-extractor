import os
from typing import List, Dict, Any, Optional
from pathlib import Path
from supabase import create_client, Client
from src.config import (
    SUPABASE_URL,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_BUCKET_NAME
)

class SupabaseManager:
    """Supabase DB 및 Storage 연동 관리자."""

    def __init__(self):
        if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
            raise ValueError("SUPABASE_URL 및 SUPABASE_SERVICE_ROLE_KEY 가 설정되지 않았습니다.")
        
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)

    def upload_mp3(self, file_path: Path, storage_path: str) -> str:
        """MP3 파일을 Storage 에 업로드하고 경로를 반환합니다."""
        with open(file_path, "rb") as f:
            # upsert=True 를 사용하여 기존 파일이 있으면 덮어씁니다.
            self.client.storage.from_(SUPABASE_BUCKET_NAME).upload(
                path=storage_path,
                file=f,
                file_options={
                    "cache-control": "3600",
                    "upsert": "true",
                    "content-type": "audio/mpeg"
                }
            )
        return storage_path

    def upsert_episode(self, episode_data: Dict[str, Any]) -> int:
        """회차 정보를 DB 에 저장하거나 업데이트합니다."""
        # episode_num 을 기준으로 중복 체크
        result = self.client.table("episodes").upsert(
            episode_data,
            on_conflict="episode_num"
        ).execute()
        
        if result.data:
            return result.data[0]["id"]
        return -1

    def insert_scripts(self, episode_id: int, scripts: List[Dict[str, Any]]):
        """회차의 대화 세그먼트들을 DB 에 저장합니다."""
        # 기존 스크립트 삭제 (재업로드 대비)
        self.client.table("scripts").delete().eq("episode_id", episode_id).execute()
        
        # episode_id 추가
        for s in scripts:
            s["episode_id"] = episode_id
            
        # 벌크 인서트
        if scripts:
            self.client.table("scripts").insert(scripts).execute()

    def get_episode_count(self) -> int:
        """현재 등록된 총 회차 수를 반환합니다."""
        result = self.client.table("episodes").select("id", count="exact").execute()
        return result.count if hasattr(result, "count") else len(result.data)

    def delete_oldest_episodes(self, limit: int = 200):
        """가장 오래된 회차들을 삭제하여 개수를 유지합니다."""
        current_count = self.get_episode_count()
        if current_count <= limit:
            return

        to_delete_count = current_count - limit
        
        # uploaded_at 기준 가장 오래된 것들 조회
        old_episodes = self.client.table("episodes") \
            .select("id", "mp3_path") \
            .order("uploaded_at", desc=False) \
            .limit(to_delete_count) \
            .execute()

        for ep in old_episodes.data:
            # 1. DB 삭제 (scripts, play_history 는 CASCADE 에 의해 삭제됨)
            self.client.table("episodes").delete().eq("id", ep["id"]).execute()
            
            # 2. Storage 삭제
            try:
                self.client.storage.from_(SUPABASE_BUCKET_NAME).remove([ep["mp3_path"]])
            except Exception as e:
                print(f"⚠️ Storage 파일 삭제 실패 ({ep['mp3_path']}): {e}")

# 싱글톤 인스턴스 (옵션)
_instance = None

def get_supabase_manager() -> SupabaseManager:
    global _instance
    if _instance is None:
        _instance = SupabaseManager()
    return _instance
