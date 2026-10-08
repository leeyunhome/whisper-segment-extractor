"""
중앙 설정 파일.

앵커 검색이 실패할 때 첫 번째로 봐야 할 곳입니다.
새로운 회차 패턴이 발견되면 여기에 추가하세요.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ==============================================================================
# 경로
# ==============================================================================

PROJECT_DIR = Path(__file__).parent.parent.resolve()  # src/ 의 부모

SOURCE_MP3_DIR = PROJECT_DIR / "source_mp3"
OUTPUT_MP3_DIR = PROJECT_DIR / "output_mp3"
EPISODE_INFO_DIR = PROJECT_DIR / ".episode_info"
PLAYWRIGHT_PROFILE_DIR = PROJECT_DIR / ".playwright_profile"
ENV_FILE = PROJECT_DIR / ".env"

# .env 파일 로드
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)

# EBS Downloader 가 받는 폴더 (Windows 기준)
DEFAULT_WATCH_DIR = os.getenv("EBS_DOWNLOAD_DIR", r"C:\EBSe")


# ==============================================================================
# EBS 사이트 URL
# ==============================================================================

EBS_MAIN_URL = "https://home.ebse.co.kr/beginnerenglish/main"
EBS_REPLAY_URL = (
    "https://home.ebse.co.kr/beginnerenglish/replay/3/list"
    "?courseId=ER2016G0BEG01ZZ&stepId=ET2016G0BEG0101"
)


# ==============================================================================
# 앵커 (영어 대화 구간 시작 지점)
#
# Whisper 한국어 전사 결과에서 이 문구들 중 하나가 나오면 그 직후를
# 영어 대화 시작점으로 본다.
#
# 못 찾는 회차가 생기면:
#   1. tools/find_anchor.py 로 transcription 파일을 직접 확인
#   2. 실제 진행자가 쓴 표현을 발견하면 여기에 추가
# ==============================================================================

ANCHOR_PHRASES = [
    # 가장 흔한 표현들
    "전체대화 주세요",
    "전체대화",
    "전체 대화",
    "전체대화 들어볼게요",
    "전체대화 들어보세요",
    "전체대화 드릴게요",
    "전체 대화 들어",
    "빈칸 채워진 전체대화",

    # Whisper 가 가끔 잘못 전사하는 변형들
    "전체되어",
    "전체 되어",
]

# 보조 앵커: 위 ANCHOR_PHRASES 를 하나도 못 찾았을 때만 쓴다 (오탐 방지를 위해 완전 일치만).
# 2820회처럼 "전체 대화" 안내 없이 "미션 해결!" 직후에 전체 대화가 나오는 진행 방식 대응.
ANCHOR_FALLBACK_PHRASES = [
    "미션 해결",
]

# 앵커가 나타날 시간 범위 (초)
# 30분 방송 기준, 영어 대화는 보통 21분 ~ 28분 사이에 나옴
# (2716화처럼 21분대에 전체대화가 시작되는 에피소드 대응)
ANCHOR_TIME_MIN = 21 * 60  # 1260초 (= TRANSCRIBE_START_SEC 와 동일)
ANCHOR_TIME_MAX = 28 * 60  # 1680초

# 앵커를 찾기 위해 Whisper 전사를 어디서부터 시작할지
# (앞부분 다 전사하면 시간만 낭비)
TRANSCRIBE_START_SEC = 21 * 60  # 1260초


# ==============================================================================
# 종료 지점 (영어 대화 끝나고 한국어 설명 시작)
# ==============================================================================

# 영어 대화가 끝나면 진행자가 "입영작 타임" 으로 넘어감
END_PHRASES = [
    "입영작",
    "입으로 하는 영작",
    # Whisper 오인식 대응 (음운 유사 오기)
    "입으로 하는 영자",   # 영작 → 영자
    "이병작",             # 입영작 → 이병작
    "이병자",             # 입영작 → 이병자
    "이병자 타임",
    "입병작",
    "입영자",
    "입 영작",
]

# EBS Beginner English 진행자/선생님 영어 메타 문구
# 실제 대화가 아닌 선생님 진행 멘트 (드릴/미션 전환 신호)
TEACHER_EN_PHRASES = [
    "shall we solve the mission",
    "let's solve the mission",
    "mission, i'll solve",
    "i'll solve the mission",
    "let's wrap it up",
    "great job, you guys",
    "everyone, don't forget",
    "don't forget this pattern",
    "time for the word",
    "all right, shall we",
]

# 추출 길이 검증
EXTRACT_MIN_DURATION = 20  # 초 미만이면 경고
EXTRACT_MAX_DURATION = 90  # 초 초과면 경고

# 앵커 이후 최소 대기 시간 (이 시간 안에 한국어 나와도 무시)
# extract_start 기준으로 계산 (anchor_end_time 이 아닌 실제 대화 시작점)
MIN_ENGLISH_DURATION_AFTER_ANCHOR = 15


# ==============================================================================
# Whisper 모델
# ==============================================================================

DEFAULT_MODEL = "large-v3-turbo"
NGRAM_N = 3
AVAILABLE_MODELS = [
    "tiny", "base", "small", "medium",
    "large-v2", "large-v3", "large-v3-turbo",
]


# ==============================================================================
# 다운로드 감시
# ==============================================================================

EBS_FILENAME_PATTERN = r"^\d{8}_\d{6}_[0-9a-fA-F]+_mp3\.mp3$"
SIZE_STABLE_CHECKS = 3
SIZE_CHECK_INTERVAL = 2.0  # 초
POLL_INTERVAL = 3.0  # 초

# N-gram 유사도 임계값 (0.6 이상이면 매칭으로 간주)
SIMILARITY_THRESHOLD = 0.6



# ==============================================================================
# Playwright
# ==============================================================================

DEFAULT_TIMEOUT_MS = 15000

# 회차 검색 시 페이지네이션 fallback 최대 페이지 수
MAX_PAGES_FALLBACK = 30


# ==============================================================================
# Supabase (사용 중단 - 프로젝트 일시 정지)
# ==============================================================================

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

SUPABASE_BUCKET_NAME = "episodes"


# ==============================================================================
# Cloudflare R2
# ==============================================================================

R2_ACCOUNT_ID = os.getenv("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "ebs-learning")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL", "").rstrip("/")
MAX_EPISODES_LIMIT = 200

# ==============================================================================
# EBS Downloader 설정
# ==============================================================================

# 다운로드 완료 후 창 자동 닫기 체크박스 클릭 여부
CLOSE_DOWNLOADER_AFTER_FINISH = True
