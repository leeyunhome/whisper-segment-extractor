"""
EBS 공지사항 게시판 강의안(PDF) 자동 다운로더.
"""

import os
import re
import sys
import time
from pathlib import Path
from typing import Optional, Tuple

try:
    from playwright.sync_api import sync_playwright, Page, BrowserContext
except ImportError:
    print("[ERROR] playwright 미설치: pip install playwright")
    sys.exit(1)

from src.config import PLAYWRIGHT_PROFILE_DIR, DEFAULT_TIMEOUT_MS

BOARD_LIST_URL = "https://home.ebse.co.kr/beginnerenglish/board/2/82000633/list?hmpMnuId=100"
LECTURE_PLANS_DIR = Path(__file__).parent.parent.resolve() / ".lecture_plans"


def download_lecture_plan(target_episode: int, headless: bool = True) -> Optional[Path]:
    """
    공지사항 게시판에서 대상 회차가 포함된 강의안 PDF를 찾아서 다운로드합니다.
    """
    print(f"\n[NOTICE] {target_episode}회 공식 강의안 탐색 시작...")
    LECTURE_PLANS_DIR.mkdir(parents=True, exist_ok=True)
    
    with sync_playwright() as p:
        try:
            chromium_args = [
                "--disable-blink-features=AutomationControlled",
                "--disable-features=ExternalProtocolDialog",
                "--disable-infobars",
            ]
            context: BrowserContext = p.chromium.launch_persistent_context(
                user_data_dir=str(PLAYWRIGHT_PROFILE_DIR),
                headless=headless,
                args=chromium_args,
                ignore_default_args=["--enable-automation"],
            )
        except Exception as e:
            print(f"[ERROR] 브라우저 실행 실패: {e}")
            return None

        context.set_default_timeout(DEFAULT_TIMEOUT_MS)
        page = context.pages[0] if context.pages else context.new_page()

        try:
            # 1. 공지사항 리스트 접속
            print(f"   [NAV] 공지글 목록 접속: {BOARD_LIST_URL}")
            page.goto(BOARD_LIST_URL, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)

            # 3. 회차 범위 매칭 글 찾기 (tr 기반 견고한 탐색)
            rows = page.locator("tr").all()
            target_link = None
            target_title = ""
            
            for row in rows:
                try:
                    text = row.inner_text() or ""
                except Exception:
                    continue

                # '강의안' 이나 '교안'이 제목에 들어가 있는지 확인 (한글 깨짐 감안하여 숫자로도 체크)
                # 한국어 인코딩 깨짐을 대비하여 유연하게 체크
                has_lecture_keyword = any(kw in text for kw in ["강의안", "교안", "강의", "강의계획"])
                # 만약 깨져서 안 잡힐 수도 있으므로, 숫자 패턴이 있고 target_episode를 포함하는지 확인
                match = re.findall(r'(\d+)\s*[-~–—\u2013\u2014]\s*(\d+)', text)
                if match:
                    for start_str, end_str in match:
                        start, end = int(start_str), int(end_str)
                        if start <= target_episode <= end:
                            # 이 tr 안에 있는 a 태그를 찾는다
                            links = row.locator("a").all()
                            if links:
                                target_link = links[0]
                                target_title = text.strip().replace("\n", " | ")
                                break
                if target_link:
                    break

            if not target_link:
                # Fallback: 일반 a 태그 전체 검색
                print("   [WARN] tr 기반 탐색 실패, 전체 a 태그 Fallback 검색 시도...")
                links = page.locator("a").all()
                for link in links:
                    try:
                        text = link.inner_text() or ""
                    except Exception:
                        continue
                    match = re.findall(r'(\d+)\s*[-~–—\u2013\u2014]\s*(\d+)', text)
                    if match:
                        for start_str, end_str in match:
                            start, end = int(start_str), int(end_str)
                            if start <= target_episode <= end:
                                target_link = link
                                target_title = text.strip()
                                break
                    if target_link:
                        break

            if not target_link:
                print(f"   [WARN] {target_episode}회가 포함된 강의안 공지글을 찾지 못했습니다.")
                context.close()
                return None

            print(f"   [FOUND] 매칭 공지글 발견: '{target_title}'")
            
            # 4. 글 클릭 및 상세 진입
            target_link.click()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(3000)

            # 5. 상세 페이지 내 PDF 첨부파일 다운로드
            pdf_links = page.locator("a[href*='.pdf'], a[onclick*='.pdf']").all()
            if not pdf_links:
                # 텍스트 기준으로 찾기 (.pdf 텍스트가 포함된 모든 링크)
                all_links = page.locator("a").all()
                for btn in all_links:
                    try:
                        btn_txt = (btn.inner_text() or "").lower()
                        btn_href = (btn.get_attribute("href") or "").lower()
                        if ".pdf" in btn_txt or ".pdf" in btn_href:
                            pdf_links.append(btn)
                    except Exception:
                        pass

            if not pdf_links:
                print("   [ERROR] PDF 첨부파일 다운로드 링크를 찾지 못했습니다.")
                context.close()
                return None

            pdf_btn = pdf_links[0]
            try:
                btn_text = pdf_btn.inner_text().strip().replace("\n", " ")
            except Exception:
                btn_text = "PDF 다운로드 링크"
            print(f"   [CLICK] PDF 다운로드 링크 클릭: '{btn_text}'")

            # 파일명 범위 파싱
            match_range = re.search(r'(\d+)\s*[-~]\s*(\d+)', target_title)
            if match_range:
                range_str = f"{match_range.group(1)}-{match_range.group(2)}"
            else:
                range_str = str(target_episode)
                
            save_path = LECTURE_PLANS_DIR / f"{range_str}_강의안.pdf"

            try:
                with page.expect_download(timeout=20000) as download_info:
                    pdf_btn.click(force=True)
                download = download_info.value
                download.save_as(str(save_path))
                print(f"   [SUCCESS] 다운로드 완료: {save_path.name}")
                context.close()
                return save_path
            except Exception as download_err:
                print(f"   [ERROR] 다운로드 캡처 실패: {download_err}")
                context.close()
                return None

        except Exception as e:
            print(f"   [ERROR] 크롤링 도중 오류 발생: {e}")
            try:
                context.close()
            except Exception:
                pass
            return None



if __name__ == "__main__":
    # 단독 테스트용
    if len(sys.argv) > 1:
        try:
            ep = int(sys.argv[1])
        except ValueError:
            ep = 2723
    else:
        ep = 2723

    res = download_lecture_plan(ep, headless=False)
    if res:
        print(f"\n[OK] 테스트 성공: {res}")
    else:
        print(f"\n[FAIL] 테스트 실패")
