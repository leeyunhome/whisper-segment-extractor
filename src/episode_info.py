"""
EBS 회차 정보 처리.

- 회차 텍스트 파싱 → 회차번호/카테고리/부제목/방영일
- 안전한 파일명 생성
- EBS 사이트의 회차 목록 추출용 JS 스니펫
"""

import re
from typing import Optional


def parse_episode_info(text: str) -> Optional[dict]:
    """
    EBS 회차 텍스트 파싱.

    예시 입력:
        "2708 제2708회 가정 – 너 정도면 청소년 아니니? 방영일 : 2026.05.04 ..."

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

    # 회차 번호: "제2708회"
    m = re.search(r'제(\d+)회', text)
    if not m:
        m = re.match(r'^\s*(\d+)\s', text)
    if m:
        info['episode'] = int(m.group(1))

    # 카테고리 + 부제목: "제XXXX회 카테고리 – 부제목"
    m = re.search(r'제\d+회\s+([^–\-—ㅡ]+?)\s*[–\-—ㅡ]\s*([^방]+?)\s+방영일', text)
    if m:
        info['category'] = m.group(1).strip()
        info['subtitle'] = m.group(2).strip()
    else:
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
    회차 정보로 Windows 안전 파일명 생성.

    예: '2708_가정_너_정도면_청소년_아니니_20260504'
    """
    parts = []

    if 'episode' in info:
        parts.append(str(info['episode']))

    if 'category' in info:
        parts.append(_sanitize(info['category']))

    if 'subtitle' in info:
        subtitle = _sanitize(info['subtitle'])
        if len(subtitle) > 40:
            subtitle = subtitle[:40]
        parts.append(subtitle)

    if 'air_date_compact' in info:
        parts.append(info['air_date_compact'])

    if not parts and lect_id:
        parts.append(lect_id)

    name = '_'.join(p for p in parts if p)
    name = re.sub(r'_+', '_', name).strip('_')

    return name or 'unknown'


def _sanitize(s: str) -> str:
    """파일명 안전 변환 (한글/영숫자만 남김)"""
    if not s:
        return ''
    # Windows 금지 문자 제거
    s = re.sub(r'[\\/:*?"<>|]', '', s)
    # 공백/특수문자 → _
    s = re.sub(r'[\s,.!?～~]+', '_', s)
    # 한글, 영숫자, _, - 만 남김
    s = re.sub(r'[^\w가-힣ㄱ-ㅎㅏ-ㅣ_-]', '', s)
    return s.strip('_')


# ==============================================================================
# JS 스크립트 (Playwright 에서 사용)
# ==============================================================================

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


# ==============================================================================
# 단독 실행: 파싱 테스트
# ==============================================================================

if __name__ == "__main__":
    samples = [
        "2708 제2708회 가정 – 너 정도면 청소년 아니니? 방영일 : 2026.05.04 학습일 : 2026.05.04",
        "2707 제2707회 여행 – 여행 가이드가 추천한 포토존 방영일 : 2026.05.01",
        "2658 제2658회 일상 – 너무 늦게 일어났어 방영일 : 2026.02.10",
    ]

    for s in samples:
        info = parse_episode_info(s)
        fname = make_safe_filename(info) if info else "(파싱 실패)"
        print(f"입력: {s[:50]}...")
        print(f"  → {info}")
        print(f"  → 파일명: {fname}")
        print()
