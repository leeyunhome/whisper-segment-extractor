# 시스템 아키텍처 (whisper-segment-extractor)

다른 앱을 만들 때 참고할 수 있는 형태로 정리한 시스템 요약. 구체 파일 경로는 이 프로젝트 기준이지만, **패턴 / 트레이드오프 / 함정** 섹션은 유사한 자동화 파이프라인 (외부 앱 제어 → 파일 감시 → AI 추론 → 산출물 가공 → 클라우드 + 정적 배포) 만들 때 그대로 응용 가능.

---

## 1. 한 줄 요약

EBS 라디오 회차를 자동 다운로드 → Whisper로 한국어/영어 전사 → 음악 구간 기반으로 영어 대화만 정밀 추출 → 모바일 친화 웹 플레이어로 배포하는 **end-to-end 자동화 파이프라인**.

---

## 2. 시스템 한눈에

```
   [사용자]                                                    [최종 산출물]
   run.bat --episode N                                          ┌──────────────────┐
       │                                                        │ extracted MP3    │
       ▼                                                        │ script .txt      │
   ┌────────────────────────────────────────────────────┐       │ player .json     │
   │           src/runner.py  (오케스트레이터)           │       │ 웹 플레이어 HTML │
   │  ┌──────────────────────┐  ┌─────────────────────┐ │       └──────────────────┘
   │  │ Thread A             │  │ Thread B (main)     │ │                ▲
   │  │ src/watcher.py       │  │ src/auto_download.py│ │                │
   │  │ (파일 감시 + 추출)   │  │ (Playwright + UI)   │ │                │
   │  └────────┬─────────────┘  └─────────┬───────────┘ │                │
   └───────────┼─────────────────────────┼──────────────┘                │
               │                          │                              │
               │ polls                    │ controls                     │
               ▼                          ▼                              │
       ┌────────────────┐         ┌──────────────────┐                   │
       │  C:\EBSe       │ ◀────── │  EBS 웹사이트    │                   │
       │  (watch dir)   │  drops  │  + EBS Downloader│                   │
       └────────────────┘   MP3   │  데스크탑 앱     │                   │
               │                  └──────────────────┘                   │
               │ new MP3 detected                                        │
               ▼                                                         │
       ┌──────────────────────────────────────────────────────┐          │
       │       src/extractor.py  (추출 엔진, 5단계)           │          │
       │  ① 한국어 Whisper 전사 (앵커 검색용)                 │          │
       │  ② inaSpeechSegmenter (음악/음성 구간 분석)          │          │
       │  ③ 시작점/종료점 결정                                │          │
       │  ④ MP3 잘라내기                                      │          │
       │  ⑤ 영어 Whisper 재전사 + 스크립트/플레이어 JSON 생성 │──────────┘
       └──────────────────────────────────────────────────────┘
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │ src/uploader.py          │ ──▶ Supabase (DB + Storage)
                    └──────────────────────────┘
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │ tools/build_player.py    │ ──▶ temp_repo/ ──▶ git push ──▶ GitHub Pages
                    │ (play.html + index.html) │
                    └──────────────────────────┘
```

---

## 3. 파이프라인 단계

각 단계의 **신호 (입력) → 책임 (처리) → 산출 (출력)** 으로 보면 새 앱 설계할 때 모듈 경계 잡기 쉬움.

| # | 단계 | 모듈 | 입력 | 처리 | 출력 |
|---|---|---|---|---|---|
| 1 | 사용자 트리거 | `run.bat` → `src/runner.py` | 회차 번호 (CLI) | conda env activate, 워커 fork | watcher + downloader 둘 다 가동 |
| 2 | UI 자동화 (다운로드) | `src/auto_download.py` (Playwright) + `src/downloader_clicker.py` (pyautogui) | 회차 ID | EBS 웹 로그인 → 회차 검색 → 다운로드 큐 추가 → 데스크탑 앱 클릭 | MP3 파일이 `C:\EBSe` 에 떨어짐 |
| 3 | 파일 감시 | `src/watcher.py` | watch dir | 신규 MP3 발견 → 크기 안정화 대기 → 회차 정보 매칭 → 추출 호출 | `source_mp3/` 로 이동 |
| 4 | 한국어 전사 (앵커 탐지) | `src/extractor._transcribe_korean` | MP3 (21분~끝) | faster-whisper Korean | `transcription_*.json` (디버그 보관) |
| 5 | 앵커 검색 | `src/extractor._find_anchor` | KO segments | 완전 일치 → N-gram fuzzy → 병합 검색 (3-pass) | 앵커 종료 시각 (초) |
| 6 | 음악/음성 분석 | `src/extractor._analyze_audio_segments` | MP3 전체 | inaSpeechSegmenter (TF 기반) | `(label, start, end)` 리스트 |
| 7 | 시작/종료점 결정 | `src/extractor._find_extract_start/end` | 음악 세그먼트 + KO segments | 앵커 후 첫 음악 → 연속 한국어 또는 명시적 종료 문구 탐지 | `(extract_start, extract_end)` 초 |
| 8 | 오디오 추출 | `src/extractor._extract_and_save` | MP3 + 구간 | pydub로 자르기 → 모노 변환 → 64kbps | `extracted_*.mp3` |
| 9 | 영어 재전사 | `src/extractor._extract_and_save` (재호출) | 잘린 MP3 | faster-whisper English | EN segments |
| 10 | 후처리 (스크립트 정제) | `src/extractor._clean_english_segments` | EN segments | 한국어 제거 / 내부 중복 / 경계 겹침 / 종료 문구 필터 | clean segments |
| 11 | 메타 문구 재트리밍 | `src/extractor._apply_teacher_phrase_trim` | clean segments | "shall we solve the mission" 등 진행자 멘트 탐지 → MP3 다시 자르기 | 최종 MP3 + segments |
| 12 | 산출물 저장 | `src/extractor._save_*` + `src/watcher.move_outputs_to_output_dir` | 산출물 | `output_mp3/` 로 이동, 회차 기반 파일명 | `.mp3`, `.txt`, `_player.json`, `_transcription.json` |
| 13 | 클라우드 업로드 | `src/uploader.process_and_upload` | 산출물 | Supabase Storage (MP3) + DB (메타) | URL이 박힌 `_player.json` |
| 14 | 정적 배포 빌드 | `tools/build_player.py` | `output_mp3/*` | `play.html` (단일 플레이어) + `index.html` (대시보드) 생성 | `temp_repo/` 안에 복사 |
| 15 | GitHub Pages 푸시 | `src/runner.sync_to_github_pages` | `temp_repo/` | `git add/commit/push` | 라이브 사이트 갱신 |

---

## 4. 모듈 맵

### `src/`
| 파일 | 역할 | 의존 외부 |
|---|---|---|
| `config.py` | **모든 튜닝 노브 중앙화** — 앵커 문구, 종료 문구, 시간 범위, 임계값, URL, env 변수 로드 | `dotenv` |
| `runner.py` | 오케스트레이터. 워커 thread 실행, 다운로더 트리거, 배포 동기화 | stdlib |
| `auto_download.py` | EBS 웹 자동화 (로그인 + 회차 검색 + 큐 추가) | `playwright` |
| `downloader_clicker.py` | EBS 데스크탑 다운로더 PC 앱 윈도우 제어 (button 클릭) | `pyautogui`, `pygetwindow` |
| `watcher.py` | 폴더 폴링 + 다운로드 완료 대기 + 추출 호출 + 산출물 이동 + 업로드 트리거 | `pathlib` |
| `extractor.py` | **추출 엔진의 핵심.** Whisper backend shim + 5단계 추출 로직 + 정제 후처리 | `faster-whisper`, `inaSpeechSegmenter`, `pydub` |
| `episode_info.py` | 회차 메타데이터 (날짜, 제목) 매핑, 안전 파일명 생성 | stdlib |
| `uploader.py` | Supabase Storage(파일) + DB(메타) 업로드 | `supabase` |
| `supabase_util.py` | Supabase client 싱글톤 | `supabase` |

### `tools/`
| 파일 | 역할 |
|---|---|
| `build_player.py` | `play.html`, `index.html`, `_player.json` 등 정적 자산 빌더 |
| `find_anchor.py` | 앵커 못 찾을 때 수동 진단용 — 한국어 전사를 따로 돌려보기 |
| `check_gpu.py` | torch / TF / faster-whisper GPU 인식 확인 |
| `check_mapping.py` | 회차 정보 매핑 디버깅 |
| `cleanup.py`, `reset_data.py` | 산출물 정리 / 초기화 |
| `test_supabase.py`, `test_upload.py` | Supabase 연결 검증 |

### 디렉토리 레이아웃
```
whisper-segment-extractor/
├── src/                       # 코드
├── tools/                     # 디버깅 + 빌드 스크립트
├── .episode_info/             # 회차별 메타데이터 JSON (lectId → 회차, 제목, 날짜)
├── source_mp3/                # 다운로드된 원본 30분 MP3 (gitignore)
├── output_mp3/                # 추출된 클립 + 스크립트 + JSON (gitignore)
├── temp_repo/                 # GitHub Pages 배포 저장소 (별도 git repo, submodule 아님)
│   ├── play.html              # 단일 플레이어 (모든 회차 공용)
│   ├── index.html             # 대시보드
│   └── *_player.json          # 회차별 데이터
├── .playwright_profile/       # Playwright 세션 (로그인 유지)
├── .env                       # 시크릿 (Supabase keys 등, gitignore)
├── run.bat                    # 메인 진입점
└── requirements.txt
```

---

## 5. 외부 의존성

| 외부 시스템 | 인터페이스 | 용도 |
|---|---|---|
| EBS 웹사이트 | Playwright (headed) | 로그인 + 회차 검색 + 다운로드 큐 |
| EBS Downloader (PC 앱) | pyautogui / pygetwindow | 큐에 추가된 회차 실제 다운로드 트리거 (앱 UI 클릭) |
| HuggingFace Hub | faster-whisper 내장 | 모델 가중치 다운로드 (캐싱) |
| CUDA + cuDNN | DLL (Windows) | GPU 추론 |
| Supabase | Python SDK | Storage (MP3) + Postgres (메타) |
| GitHub Pages | git push | 정적 사이트 호스팅 |

---

## 6. 다른 앱에 옮길 수 있는 패턴

### 6.1 오케스트레이터 + 워커 thread 패턴
[`src/runner.py`](src/runner.py) 가 두 개 워커를 띄움:
- **Producer**: `auto_download` (외부 시스템에 작업 의뢰)
- **Consumer**: `watcher` (결과를 감시하며 처리)

워커는 둘 다 **별도 `subprocess`** 로 실행, 메인은 thread로 `subprocess.run` 호출 → 각 워커는 자체 stdout을 그대로 가짐. 한쪽이 죽어도 다른 쪽에 영향 없음. **각 워커가 독립 프로세스라 import 충돌, 라이브러리 init 실패의 격리가 됨**.

→ 다른 앱에 응용: 외부 시스템과 비동기로 상호작용해야 하는 경우 (e.g., 파일 업로드 후 처리 결과 폴링) 이 모양 그대로 쓸 수 있음.

### 6.2 파일 시스템을 통한 디커플링
다운로더는 watch dir에 파일을 "떨어뜨릴 뿐", watcher는 그걸 본다. **양쪽이 서로의 API를 모름**. 이는:
- 다운로더를 바꿔도 (수동, 다른 사이트, 다른 도구) watcher는 그대로
- 다운로더가 죽어도 watcher는 다음 파일을 기다림
- 디버깅 시 dir에 파일만 떨어뜨려도 watcher 테스트 가능

→ 다른 앱에 응용: 파이프라인 단계를 결합도 낮추고 싶을 때 메시지 큐까지 갈 필요 없이 "공유 폴더"로 충분한 경우가 많다.

### 6.3 외부 백엔드를 shim으로 감싸기
[`src/extractor.FasterWhisperBackend`](src/extractor.py) — faster-whisper를 openai-whisper와 같은 dict 형태 (`{'segments': [{'start','end','text'}, ...]}`) 로 변환해서 노출. 호출부는 backend 교체를 모름.

→ 다른 앱에 응용: 외부 ML/SaaS API를 직접 호출하지 말고 항상 얇은 shim으로 감싸라. 모델/제공자 교체 비용이 한 파일로 격리됨.

### 6.4 Cheap-pass → expensive-pass 다단 추론
- **1차 (싼 패스)**: 전체 오디오 (~30분) 를 Korean으로 한 번 전사 → 앵커 위치 찾기 (영어 안 됨)
- **2차 (비싼 패스)**: 앵커 기반으로 자른 **~30~60초만** English로 고품질 재전사

전체를 좋은 모델로 두 언어로 돌리는 것보다 훨씬 빠르고 정확함. **"먼저 위치를 찾고, 그 다음 정밀하게 추론"** 은 비디오 분석, OCR, 긴 문서 검색 등 어디나 적용됨.

### 6.5 Config-as-data + Fail-loudly 진단
[`src/config.py`](src/config.py) 에 **모든 도메인 노브** (앵커 문구, 종료 문구, 시간 범위, 임계값) 가 모여 있음. 코드 안 건드리고 새 회차 패턴 추가 가능. + 앵커 검색 실패 시 [`_print_anchor_diagnosis`](src/extractor.py) 가 **무엇을 추가하면 되는지 단서까지 자동 출력** — 사용자가 next action을 알 수 있음.

→ 다른 앱에 응용: ML/규칙 기반 분류가 실패하면 그냥 "실패"로 끝내지 말고 **다음에 무엇을 추가해야 동작할지 진단을 같이 출력**. 운영자 친화적.

### 6.6 ASR 오타에 강한 매칭 (N-gram fuzzy)
완전 일치 → N-gram (trigram) Sørensen-Dice 유사도 → 연속 세그먼트 병합 → 3중 검색. 단일 세그먼트가 깨졌어도 인접 세그먼트와 합쳐서 회수.

→ 다른 앱에 응용: ASR/OCR 결과로 키워드 찾을 때 항상 fuzzy + 인접 윈도우 병합 패턴 같이 둘 것.

### 6.7 두 저장소 분리 + git push로 배포
코드 저장소(`whisper-segment-extractor/`) 와 GitHub Pages 배포 저장소(`temp_repo/`, 별도 repo) 가 같은 디렉토리 트리에 공존. 빌드 스크립트가 `temp_repo/` 에 정적 자산 복사 후 `git add/commit/push` → Pages 자동 배포.

→ 다른 앱에 응용: 정적 배포가 필요한데 CI 설정이 부담스러우면 이 모양이 가장 단순. 다만 빌드 실패 시 부분 푸시 위험이 있으니 `--porcelain` 으로 변경 사항 확인 후 푸시.

### 6.8 파이프라인 순서 강제 (race 방지)
배포 파이프라인은 **`Supabase Upload → Dashboard Rebuild → GitHub Push`** 순서. 순서 어기면 신규 회차가 대시보드에서 누락됨 (README의 "파이프라인 정합성" 항목). 워크플로에서 순서가 의미 있는 경우 코드에 그 순서를 명시적으로 강제.

### 6.9 캐시 무력화 (브라우저 + 빌드)
- 파일명 변경 (`player.html` → `play.html`) 으로 강제 갱신
- JSON 호출 시 `?v=Date.now()` 쿼리 파라미터 추가

→ 다른 앱에 응용: PWA/정적 사이트에서 변경이 즉시 안 보이는 문제는 거의 캐시. URL 자체에 cache-bust 토큰 박는 게 가장 단순.

---

## 7. 환경 / 빌드의 함정 (현장에서 밟은 지뢰들)

이 프로젝트가 실제로 겪은 환경 문제들. **유사 ML 파이프라인 만들 때 처음부터 피하면 좋음**.

| 증상 | 원인 | 처방 |
|---|---|---|
| Python 프로세스가 traceback 없이 종료 (PowerShell `$LASTEXITCODE = -1073741819`) | Windows ACCESS_VIOLATION — C++ 확장 init이 native crash | `$LASTEXITCODE` 부터 확인. native 크래시면 라이브러리 버전 충돌이 거의 100% |
| `ctranslate2` 4.7.x + Python 3.9 Windows | 일부 환경에서 무음 native crash | `ctranslate2==4.4.0` 로 다운그레이드 |
| `ModuleNotFoundError: pkg_resources` | setuptools 81+ 가 `pkg_resources` 제거 | `setuptools<81` 핀 |
| `Could not locate cudnn_ops_infer64_8.dll` | ctranslate2 4.4가 cuDNN **8** 요구, 시스템엔 9 또는 없음 | `pip install nvidia-cudnn-cu12==8.9.*` + DLL 디렉토리 PATH 추가 |
| `--force-reinstall` 후 numpy / tensorflow 깨짐 | pip이 deps를 같이 업그레이드 | `--no-deps` 쓰거나, 같이 깨진 패키지 함께 핀 |
| Whisper 한국어 오인식 (예: "전체대화" → "전체되어") | ASR 한계 | 오인식 변형을 [config.py:65 `ANCHOR_PHRASES`](src/config.py#L65) 에 미리 등록 + N-gram fuzzy 매칭 |
| 추출 구간 이상 (단어 중간 잘림) | 인접 세그먼트 겹침 제거 시 word boundary 무시 | `is_word_split` 검사 후 자르지 말 것 ([`extractor.py` `_clean_english_segments`](src/extractor.py)) |
| 배포된 대시보드에 신규 회차 누락 | DB 업로드 전에 대시보드 빌드 | 파이프라인 순서 강제 (위 6.8) |

---

## 8. 새 비슷한 앱 만들 때 0일차 체크리스트

이 프로젝트의 경험을 토대로 한 짧은 가이드:

- [ ] **환경 / 의존성 핀**: ML 라이브러리는 처음부터 `==` 버전 핀. `>=` 는 미래의 자신을 한 밤중에 깨우는 버튼.
- [ ] **각 외부 시스템마다 shim 클래스**: 직접 호출 금지. 교체 가능성을 코드 모양으로 표현.
- [ ] **Config는 한 파일**: 도메인 노브 흩어지지 말 것. 새 패턴 발견 시 코드 안 건드리고 추가 가능해야 함.
- [ ] **실패 진단이 자동 출력**: 자동화가 "실패"만 외치면 디버깅에 사람 시간이 들어감. 다음 액션의 단서를 같이 출력.
- [ ] **파이프라인 단계는 폴더로 분리**: 메모리 큐가 아니라 디스크 (`source_mp3/`, `output_mp3/`, `temp_repo/`) 로 단계 사이를 잇자. 디버깅 시 단계별 재실행 가능.
- [ ] **오케스트레이션은 thread + subprocess**: 의존성 격리 + stdout 깔끔.
- [ ] **Cheap-pass → expensive-pass**: 비싼 추론은 작은 입력에만.
- [ ] **배포 순서 명시화**: race 가능한 단계는 코드에 순서 강제 (시간 동기화 X, 명시적 await O).
- [ ] **캐시 무력화**: 정적 자산은 URL 토큰 + 파일명 변경 두 가지 다 준비.
- [ ] **테스트는 진짜 외부 시스템에**: 모킹된 통합 테스트는 통과해도 실제는 깨짐 (DB, ASR 모두 동일).

---

## 9. 참고 위치

- 추출 알고리즘 핵심: [`src/extractor.py`](src/extractor.py)
- 튜닝 노브 전부: [`src/config.py`](src/config.py)
- 오케스트레이션: [`src/runner.py`](src/runner.py)
- 폴더 감시 + 회차 매핑: [`src/watcher.py`](src/watcher.py)
- 정적 자산 빌드: [`tools/build_player.py`](tools/build_player.py)
- 환경 점검: [`tools/check_gpu.py`](tools/check_gpu.py)
- README의 시행착오 7개 항목: [`README.md`](README.md)
