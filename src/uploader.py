from pathlib import Path
from typing import Dict, Any

from src.config import R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, R2_BUCKET_NAME


def process_and_upload(output_basename: str, output_dir: Path, episode_info: Dict[str, Any]) -> bool:  # noqa: ARG001
    """추출된 MP3를 Cloudflare R2에 업로드합니다."""

    mp3_file = output_dir / f"{output_basename}.mp3"
    if not mp3_file.exists():
        print(f"   [UPLOAD] 오류: MP3 파일 없음 ({mp3_file})")
        return False

    if not R2_ACCOUNT_ID or not R2_ACCESS_KEY_ID or not R2_SECRET_ACCESS_KEY:
        print("   [UPLOAD] R2 환경변수 미설정 (.env 확인)")
        return False

    try:
        import boto3
        client = boto3.client(
            "s3",
            endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_ACCESS_KEY,
            region_name="auto",
        )

        r2_key = mp3_file.name

        # 이미 존재하면 스킵
        try:
            client.head_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
            print(f"   [UPLOAD] 이미 R2에 존재, 스킵: {r2_key}")
            return True
        except Exception:
            pass

        size_kb = mp3_file.stat().st_size // 1024
        print(f"   [UPLOAD] R2 업로드 중... ({r2_key}, {size_kb}KB)")
        client.upload_file(
            str(mp3_file), R2_BUCKET_NAME, r2_key,
            ExtraArgs={"ContentType": "audio/mpeg"},
        )
        print(f"   [UPLOAD] 성공: {output_basename}")
        return True

    except Exception as e:
        print(f"   [UPLOAD] 예외 발생: {e}")
        return False
