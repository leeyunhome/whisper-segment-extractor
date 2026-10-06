"""
영어 -> 한국어 번역.

우선순위:
  1. Gemini API (GEMINI_API_KEY 설정 시): 한 회차의 문장들을 한 번의 요청으로 묶어 번역
  2. deep-translator GoogleTranslator (비공식 무료 엔드포인트): 문장별 호출, IP 차단될 수 있음

키는 .env 의 GEMINI_API_KEY, 모델은 GEMINI_MODEL (기본 gemini-pro-latest) 로 지정하며, 사용 불가(404/403)면 gemini-flash-latest 로 대체한다.
"""

import json
import os
import time
import urllib.error
import urllib.request
from typing import List, Optional

DEFAULT_GEMINI_MODEL = "gemini-pro-latest"   # 최신 Pro (번역 품질 우선)
FALLBACK_GEMINI_MODEL = "gemini-flash-latest"  # 기본 모델이 막혔을 때(404/403) 사용
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
PLACEHOLDER_KEY = "your_gemini_api_key_here"

_PROMPT = (
    "다음은 영어 학습 방송의 짧은 대화 문장들이다(순서대로 이어지는 대화). "
    "각 문장을 자연스러운 구어체 한국어로 번역하라. 대화 문맥을 반영하고, "
    "문장 수와 순서를 그대로 유지하며, 번역문만 JSON 문자열 배열로 반환하라.\n\n"
)


def _gemini_key() -> Optional[str]:
    """.env 의 GEMINI_API_KEY 를 우선 사용한다.

    load_dotenv() 는 기본적으로 이미 설정된 OS 환경변수를 덮어쓰지 않아,
    다른 도구가 사용자 환경변수에 넣어 둔 오래된 키가 .env 보다 먼저 적용될 수 있다.
    """
    from dotenv import dotenv_values
    from src.config import ENV_FILE

    key = (dotenv_values(ENV_FILE).get("GEMINI_API_KEY") or "").strip()
    if not key or key == PLACEHOLDER_KEY:
        key = os.getenv("GEMINI_API_KEY", "").strip()
    return key if key and key != PLACEHOLDER_KEY else None


def translate_with_gemini(texts: List[str], retries: int = 3) -> Optional[List[str]]:
    """문장 목록을 Gemini 로 번역. 실패하면 None (개수가 다르면 실패로 간주).

    기본 모델이 없거나 권한이 없으면(404/403) 대체 모델로 한 번 더 시도한다.
    """
    key = _gemini_key()
    if not key or not texts:
        return None

    primary = os.getenv("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
    models = [primary] + ([FALLBACK_GEMINI_MODEL] if primary != FALLBACK_GEMINI_MODEL else [])
    for model in models:
        result, model_unavailable = _gemini_request(key, model, texts, retries)
        if result is not None or not model_unavailable:
            return result
        print(f"  [Gemini] 모델 {model} 사용 불가 - 대체 모델 시도")
    return None


def _gemini_request(key: str, model: str, texts: List[str], retries: int):
    """(번역 결과 또는 None, 모델 사용 불가 여부) 반환"""
    body = {
        "contents": [{"parts": [{"text": _PROMPT + json.dumps(texts, ensure_ascii=False)}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": {"type": "ARRAY", "items": {"type": "STRING"}},
            "temperature": 0.2,
        },
    }
    data = json.dumps(body).encode("utf-8")

    for attempt in range(retries + 1):
        req = urllib.request.Request(
            GEMINI_URL.format(model=model), data=data, method="POST",
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
        )
        try:
            resp = json.load(urllib.request.urlopen(req, timeout=60))
            out = json.loads(resp["candidates"][0]["content"]["parts"][0]["text"])
            if isinstance(out, list) and len(out) == len(texts) and all(isinstance(x, str) for x in out):
                return [x.strip() for x in out], False
            print(f"  [Gemini] 응답 형식 불일치 (요청 {len(texts)}개, 응답 {len(out) if isinstance(out, list) else '?'})")
            return None, False
        except urllib.error.HTTPError as e:
            retryable = e.code in (429, 500, 502, 503, 504)
            print(f"  [Gemini] HTTP {e.code}" + (" - 재시도" if retryable and attempt < retries else ""))
            if e.code in (403, 404):
                return None, True
            if not retryable or attempt >= retries:
                return None, False
            time.sleep(2 ** (attempt + 1))
        except Exception as e:
            print(f"  [Gemini] 오류: {e}")
            if attempt >= retries:
                return None, False
            time.sleep(2 ** attempt)
    return None, False


def translate_with_retry(translator, text: str, retries: int = 3,
                         delay: float = 0.35) -> Optional[str]:
    """Google 번역(deep-translator) 호출 (요청 간 지연 + 지수 백오프 재시도).

    무료 엔드포인트는 초당 5회 한도라 429 가 나므로, 호출 전 delay 초 대기하고
    실패 시 1s, 2s, 4s 간격으로 재시도한다. 끝내 실패하면 None.
    """
    for attempt in range(retries + 1):
        time.sleep(delay)
        try:
            return translator.translate(text)
        except Exception as e:
            if attempt >= retries:
                print(f"  [번역 오류] {text} - {e}")
                return None
            time.sleep(2 ** attempt)
    return None


def translate_texts(texts: List[str]) -> List[Optional[str]]:
    """문장 목록 번역. Gemini 우선, 실패한 부분은 GoogleTranslator 로 대체. 실패 문장은 None."""
    if not texts:
        return []

    result = translate_with_gemini(texts)
    if result is not None:
        return list(result)

    try:
        from deep_translator import GoogleTranslator
    except ImportError:
        print("  [경고] deep_translator 패키지가 설치되지 않아 번역을 추가할 수 없습니다.")
        return [None] * len(texts)

    translator = GoogleTranslator(source="en", target="ko")
    return [translate_with_retry(translator, t) for t in texts]
