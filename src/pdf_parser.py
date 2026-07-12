import json
import re
from pathlib import Path
from typing import Dict, List, Optional
from pypdf import PdfReader

LECTURE_PLANS_DIR = Path(__file__).parent.parent.resolve() / ".lecture_plans"


def parse_pdf_lectures() -> Dict[str, List[dict]]:
    """
    .lecture_plans 폴더 내의 모든 강의안 PDF를 읽어 에피소드별로 대화 데이터와 공식 번역을 구조화합니다.
    구조화된 데이터는 개별 JSON 파일(예: 2723_parsed.json)로 저장됩니다.
    """
    LECTURE_PLANS_DIR.mkdir(parents=True, exist_ok=True)
    pdf_files = list(LECTURE_PLANS_DIR.glob("*.pdf"))
    
    parsed_results: Dict[str, List[dict]] = {}
    
    for pdf_path in pdf_files:
        print(f"[PDF] 파싱 시작: {pdf_path.name}")
        try:
            reader = PdfReader(pdf_path)
        except Exception as e:
            print(f"[PDF_ERROR] PDF 로드 실패 {pdf_path.name}: {e}")
            continue
            
        # 모든 페이지 텍스트를 하나의 문자열로 결합
        full_text = ""
        for page in reader.pages:
            full_text += (page.extract_text() or "") + "\n"
            
        # 1. 에피소드 헤더 찾기 (부 제 : (2723) ...)
        ep_matches = list(re.finditer(r'부\s*제\s*:\s*\(\s*(\d+)\s*\)', full_text))
        print(f"   [PDF] 감지된 에피소드 수: {len(ep_matches)}개")
        
        for i, match in enumerate(ep_matches):
            ep_num = match.group(1)
            start_pos = match.end()
            end_pos = ep_matches[i+1].start() if i + 1 < len(ep_matches) else len(full_text)
            
            ep_body = full_text[start_pos:end_pos]
            parsed_results[ep_num] = []
            
            # 2. 에피소드 바디에서 대화 항목 글로벌 추출
            # [★ A: or A: or B:] + (영어 대사) + ( (한국어 번역) )
            dialogues = re.findall(r'(?:★\s*)?([A-B])\s*:\s*([^(\n]+?)\s*\(([^)]+?)\)', ep_body)
            
            for speaker, english, korean in dialogues:
                # 영어 텍스트 내의 연속된 언더바(_____ 등)를 정규화
                english_normalized = re.sub(r'_{2,}', '____', english.strip())
                
                dialogue_item = {
                    "speaker": speaker,
                    "english_raw": english_normalized,
                    "korean_official": korean.strip()
                }
                parsed_results[ep_num].append(dialogue_item)
                print(f"      [{ep_num}회] [{speaker}] {english_normalized} -> {korean.strip()}")
                
        # 파싱 완료된 에피소드들 개별 파일로 보관
        for ep_num, items in parsed_results.items():
            if not items:
                continue
            save_path = LECTURE_PLANS_DIR / f"{ep_num}_parsed.json"
            try:
                with open(save_path, "w", encoding="utf-8") as f:
                    json.dump(items, f, ensure_ascii=False, indent=2)
                print(f"   [SAVE] 공식 번역 데이터셋 저장 완료: {save_path.name}")
            except Exception as save_err:
                print(f"   [ERROR] JSON 저장 실패 {save_path.name}: {save_err}")
                
    return parsed_results


def get_parsed_lecture(episode_num: str) -> Optional[List[dict]]:
    """
    특정 에피소드의 파싱된 공식 교안 번역 정보를 가져옵니다.
    로컬 JSON이 없으면 실시간으로 파싱을 시도합니다.
    """
    json_path = LECTURE_PLANS_DIR / f"{episode_num}_parsed.json"
    if json_path.exists():
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
            
    # 없으면 전체 파싱 재가동
    parsed = parse_pdf_lectures()
    if episode_num in parsed:
        return parsed[episode_num]
        
    return None


if __name__ == "__main__":
    # 단독 파싱 테스트
    print("--- PDF 파서 테스트 시작 ---")
    results = parse_pdf_lectures()
    print(f"--- 파싱 완료. 감지된 에피소드 총 {len(results)}개 ---")

