"""
output_mp3/ 의 모든 MP3를 Cloudflare R2에 업로드하고
player.json의 mp3_url을 R2 URL로 교체한다.

사용법:
  python tools/upload_to_r2.py              # 업로드 + JSON 교체
  python tools/upload_to_r2.py --dry-run    # 실제 업로드 없이 확인만
"""

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_DIR = Path(__file__).parent.parent.resolve()
OUTPUT_MP3_DIR = PROJECT_DIR / "output_mp3"

load_dotenv(PROJECT_DIR / ".env")

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "ebs-learning")


def get_r2_client():
    import boto3
    return boto3.client(
        "s3",
        endpoint_url=f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


def get_public_url(filename: str, public_base_url: str) -> str:
    return f"{public_base_url.rstrip('/')}/{filename}"


def upload_mp3s(dry_run: bool, public_base_url: str):
    mp3_files = sorted(OUTPUT_MP3_DIR.glob("*.mp3"))
    print(f"\n[R2 UPLOAD] MP3 파일 {len(mp3_files)}개 업로드 시작")
    print(f"  버킷: {R2_BUCKET_NAME}")
    print(f"  Public URL: {public_base_url}\n")

    if not dry_run:
        client = get_r2_client()

    uploaded = []
    skipped = []

    for i, mp3 in enumerate(mp3_files, 1):
        r2_key = mp3.name
        public_url = get_public_url(r2_key, public_base_url)

        if dry_run:
            print(f"  [DRY] {i}/{len(mp3_files)} {mp3.name}")
            uploaded.append((mp3, r2_key, public_url))
            continue

        try:
            # 이미 존재하는지 확인
            try:
                client.head_object(Bucket=R2_BUCKET_NAME, Key=r2_key)
                print(f"  [SKIP] {i}/{len(mp3_files)} {mp3.name} (이미 존재)")
                skipped.append(mp3)
                uploaded.append((mp3, r2_key, public_url))
                continue
            except Exception:
                pass

            size_kb = mp3.stat().st_size // 1024
            print(f"  [UP]   {i}/{len(mp3_files)} {mp3.name} ({size_kb}KB)...", end=" ", flush=True)
            client.upload_file(
                str(mp3),
                R2_BUCKET_NAME,
                r2_key,
                ExtraArgs={"ContentType": "audio/mpeg"},
            )
            print("OK")
            uploaded.append((mp3, r2_key, public_url))
        except Exception as e:
            print(f"FAIL: {e}")

    print(f"\n[R2 UPLOAD] 완료: {len(uploaded)}개 업로드 / {len(skipped)}개 스킵")
    return uploaded


def update_player_jsons(uploaded: list, dry_run: bool):
    json_files = sorted(OUTPUT_MP3_DIR.glob("*_player.json"))
    print(f"\n[JSON UPDATE] player.json {len(json_files)}개 URL 교체 시작")

    mp3_to_url = {mp3.name: public_url for mp3, _, public_url in uploaded}
    updated = 0

    for jf in json_files:
        with open(jf, "r", encoding="utf-8") as f:
            data = json.load(f)

        old_url = data.get("mp3_url", "")
        audio_field = data.get("audio", "")

        # audio 필드(파일명)로 R2 URL 결정
        new_url = mp3_to_url.get(audio_field)
        if not new_url:
            # 회차번호로 매칭 시도
            ep_num = data.get("episode_num")
            for mp3_name, url in mp3_to_url.items():
                if ep_num and str(ep_num) in mp3_name:
                    new_url = url
                    break

        if not new_url:
            print(f"  [WARN] {jf.name}: 매칭되는 MP3 없음 (audio={audio_field})")
            continue

        if old_url == new_url:
            continue

        data["mp3_url"] = new_url
        print(f"  [OK] {jf.name}")
        print(f"       {old_url}")
        print(f"    -> {new_url}")

        if not dry_run:
            with open(jf, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        updated += 1

    print(f"\n[JSON UPDATE] {updated}개 파일 URL 교체 완료")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--public-url",
        type=str,
        default=None,
        help="R2 Public Development URL (예: https://pub-xxx.r2.dev/ebs-learning)",
    )
    args = parser.parse_args()

    if not all([R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY]):
        print("[ERROR] .env에 R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY 필요")
        sys.exit(1)

    if not args.public_url:
        print("[ERROR] --public-url 옵션 필요")
        print("  예: python tools/upload_to_r2.py --public-url https://pub-XXXX.r2.dev/ebs-learning")
        print("\n  Public URL 확인 방법:")
        print("  Cloudflare 대시보드 → R2 → ebs-learning 버킷 → Settings → Public Development URL")
        sys.exit(1)

    if not args.dry_run:
        try:
            import boto3
        except ImportError:
            print("[ERROR] boto3 미설치: pip install boto3")
            sys.exit(1)

    uploaded = upload_mp3s(args.dry_run, args.public_url)
    update_player_jsons(uploaded, args.dry_run)


if __name__ == "__main__":
    main()
