"""
EBS 회차 정보 처리 모듈

- 다시보기 페이지에서 회차 목록 수집
- 회차 번호로 lectId 찾기
- 파일명에 안전한 형식으로 제목 변환
"""

import re
from typing import Optional


def parse_episode_info(text: str) -> Optional[dict]:
    """
    회차 텍스트를 파싱해서 구조화된 정보 추출.

    예시 입력:
        "2708 제2708회 가정 – 너 정도면 청소년 아니니? 방영일 : 2026.05.04 학습일 : ..."

    반환:
        {
            'episode': 2708,
            'category': '가정',
            'subtitle': '너 정도면 청소년 아니니?',
            'air_date': '2026.05.04',
            'air_date_compact': '20260504',
        }
    """
    if not text:
        return None

    info = {}

    # 회차 번호: "제2708회" 또는 텍스트 시작 부분의 숫자
    m = re.search(r'제(\d+)회', text)
    if not m:
        m = re.match(r'^\s*(\d+)\s', text)
    if m:
        info['episode'] = int(m.group(1))

    # 카테고리 + 부제목: "제XXXX회 카테고리 – 부제목"
    # 'ㅡ', '–', '-' 모두 가능
    m = re.search(r'제\d+회\s+([^–\-—ㅡ]+?)\s*[–\-—ㅡ]\s*([^방]+?)\s+방영일', text)
    if m:
        info['category'] = m.group(1).strip()
        info['subtitle'] = m.group(2).strip()
    else:
        # fallback: 카테고리만
        m = re.search(r'제\d+회\s+([^\s]+)', text)
        if m:
            info['category'] = m.group(1).strip()

    # 방영일: "방영일 : 2026.05.04"
    m = re.search(r'방영일\s*:\s*(\d{4})\.(\d{2})\.(\d{2})', text)
    if m:
        y, mo, d = m.group(1), m.group(2), m.group(3)
        info['air_date'] = f"{y}.{mo}.{d}"
        info['air_date_compact'] = f"{y}{mo}{d}"

    return info if info else None


def make_safe_filename(info: dict, lect_id: str = "") -> str:
    """
    회차 정보로 파일명에 안전한 문자열 생성.

    예: '2708_가정_너_정도면_청소년_아니니_20260504'

    Windows 파일명 금지 문자 제거: \\ / : * ? " < > |
    공백, 특수문자는 _ 로 대체.
    """
    parts = []

    if 'episode' in info:
        parts.append(str(info['episode']))

    if 'category' in info:
        parts.append(_sanitize(info['category']))

    if 'subtitle' in info:
        # 너무 길면 자름 (Windows 경로 길이 제한 고려)
        subtitle = _sanitize(info['subtitle'])
        if len(subtitle) > 40:
            subtitle = subtitle[:40]
        parts.append(subtitle)

    if 'air_date_compact' in info:
        parts.append(info['air_date_compact'])

    if not parts and lect_id:
        parts.append(lect_id)

    name = '_'.join(p for p in parts if p)

    # 연속된 _ 정리
    name = re.sub(r'_+', '_', name).strip('_')

    return name or 'unknown'


def _sanitize(s: str) -> str:
    """파일명에 안전한 문자열로 변환"""
    if not s:
        return ''
    # Windows 금지 문자 제거
    s = re.sub(r'[\\/:*?"<>|]', '', s)
    # 공백/특수문자를 _ 로
    s = re.sub(r'[\s,.!?～~]+', '_', s)
    # 한글, 영숫자, _, - 만 남김
    s = re.sub(r'[^\w가-힣ㄱ-ㅎㅏ-ㅣ_-]', '', s)
    return s.strip('_')


# ==============================================================================
# JS 스크립트들 (브라우저에서 실행)
# ==============================================================================

# 현재 페이지의 회차 목록 추출
SCRIPT_LIST_EPISODES = """
(() => {
    const items = Array.from(document.querySelectorAll('.icon_mp3 > a[onclick*="downloadMultiFile"]'));
    return items.map(link => {
        const onclick = link.getAttribute('onclick') || '';
        const m = onclick.match(/downloadMultiFile\\(['"]([^'"]+)['"]/);
        const lectId = m ? m[1] : null;
        const row = link.closest('li');
        const titleText = row?.innerText?.replace(/\\s+/g, ' ').substring(0, 200) || '';
        return { lectId, titleText };
    });
})()
"""

# 페이지 이동 (회차 목록의 N번째 페이지로)
SCRIPT_GO_PAGE = "goPage({page})"

# downloadMultiFile 호출
SCRIPT_DOWNLOAD = "downloadMultiFile('{lect_id}', 'MP3', '')"


# ==============================================================================
# 단독 실행: 테스트
# ==============================================================================

if __name__ == "__main__":
    # 파싱 테스트
    samples = [
        "2708 제2708회 가정 – 너 정도면 청소년 아니니? 방영일 : 2026.05.04 학습일 : 2026.05.04 강의시간 : 28:22",
        "2707 제2707회 여행 – 여행 가이드가 추천한 포토존 방영일 : 2026.05.01 학습일 :",
        "2658 제2658회 일상 – 너무 늦게 일어났어 방영일 : 2026.02.10",
    ]

    for s in samples:
        info = parse_episode_info(s)
        fname = make_safe_filename(info) if info else "(파싱 실패)"
        print(f"입력: {s[:50]}...")
        print(f"  → {info}")
        print(f"  → 파일명: {fname}")
        print()
