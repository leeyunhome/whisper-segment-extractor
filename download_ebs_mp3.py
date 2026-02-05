import os
import time
import re
from playwright.sync_api import Playwright, sync_playwright, expect

# 설정
BASE_URL = "https://home.ebse.co.kr/beginnerenglish/main"
NAVER_ID = "mszeta"
NAVER_PW = "!starscream0"
SAVE_DIR = "source_mp3"

def run(playwright: Playwright) -> None:
    # 1. 브라우저 실행 (headless=False)
    browser = playwright.chromium.launch(headless=False)
    context = browser.new_context()
    page = context.new_page()

    print(f"[{time.strftime('%H:%M:%S')}] EBSe 메인 페이지로 이동 중...")
    page.goto(BASE_URL)

    # 2. 로그인 버튼 클릭
    print(f"[{time.strftime('%H:%M:%S')}] 로그인 페이지로 이동 중...")
    page.get_by_role("link", name="로그인").click()
    
    # 3. 네이버 로그인 선택
    print(f"[{time.strftime('%H:%M:%S')}] 네이버 로그인 선택 중...")
    page.get_by_role("link", name="네이버").click()

    # 4. 네이버 아이디/비밀번호 입력
    print(f"[{time.strftime('%H:%M:%S')}] 네이버 로그인 정보 입력 중...")
    page.wait_for_selector("#id")
    page.fill("#id", NAVER_ID)
    page.fill("#pw", NAVER_PW)
    page.click(".btn_login")

    # 캡차/보안 확인 대기
    print(f"[{time.strftime('%H:%M:%S')}] 로그인을 확인합니다. 캡차나 보안 확인이 뜨면 직접 처리해주세요 (60초 대기)...")
    try:
        # EBSe 메인으로 돌아올 때까지 대기
        page.wait_for_url(re.compile(r"ebse\.co\.kr"), timeout=60000)
        print(f"[{time.strftime('%H:%M:%S')}] EBSe 로그인 성공!")
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] 로그인 대기 시간 초과 또는 이미 로그인됨: {e}")

    # 3. 다운로드 폴더 생성
    if not os.path.exists(SAVE_DIR):
        os.makedirs(SAVE_DIR)

    # 4. 강의 상세 페이지로 직접 이동 (사용자 codegen 참고)
    # 이 URL로 이동하면 해당 강의의 MP3 버튼이 활성화된 상태가 됩니다.
    target_url = "https://home.ebse.co.kr/beginnerenglish/replay/3/list?courseId=ER2016G0BEG01ZZ&stepId=ET2016G0BEG0101&lectId=60684830"
    print(f"[{time.strftime('%H:%M:%S')}] 강의 상세 페이지로 이동 중...")
    page.goto(target_url)
    page.wait_for_load_state("networkidle")

    # 5. MP3 버튼 클릭 및 다운로드
    print(f"[{time.strftime('%H:%M:%S')}] MP3 다운로드 버튼 클릭 시도...")
    
    # 팝업 차단 해제
    page.on("dialog", lambda dialog: dialog.dismiss())

    try:
        # 사이드바 제외, 본문(.bbsList) 내의 첫 번째 MP3 버튼을 찾습니다.
        # 이게 가장 정확하게 리스트의 첫 번째 버튼을 잡는 방법입니다.
        mp3_btn = page.locator(".bbsList").get_by_role("link", name="MP3").first
        
        print(f"[{time.strftime('%H:%M:%S')}] 실제 버튼을 클릭하여 다운로드를 시작합니다.")
        
        with page.expect_download(timeout=60000) as download_info:
            mp3_btn.click()
            
        download = download_info.value
        save_path = os.path.join(SAVE_DIR, download.suggested_filename)
        download.save_as(save_path)
        print(f"[{time.strftime('%H:%M:%S')}] 다운로드 완료: {save_path}")
        
    except Exception as e:
        print(f"[{time.strftime('%H:%M:%S')}] 클릭 시도 중 오류 발생: {e}")
        # 만약 실패할 경우, codegen의 방식(URL 재진입)으로 2차 시도
        print(f"[{time.strftime('%H:%M:%S')}] 2차 시도 (URL 재진입 방식)...")
        try:
            with page.expect_download(timeout=60000) as download_info:
                page.goto(target_url)
            download = download_info.value
            save_path = os.path.join(SAVE_DIR, download.suggested_filename)
            download.save_as(save_path)
            print(f"[{time.strftime('%H:%M:%S')}] 2차 시도 성공: {save_path}")
        except Exception as e2:
            print(f"[{time.strftime('%H:%M:%S')}] 2차 시도도 실패했습니다: {e2}")

    # ---------------------
    time.sleep(2)
    context.close()
    browser.close()

if __name__ == "__main__":
    with sync_playwright() as playwright:
        run(playwright)
