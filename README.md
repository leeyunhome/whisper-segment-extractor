# EBS 오디오 학습 플랫폼 (whisper-segment-extractor)

EBS 왕초보 영어 방송을 자동으로 다운로드하고, faster-whisper(large-v3-turbo)로 전사하여 영어 대화 구간만 잘라내 MP3·스크립트로 만들고, 웹 플레이어로 배포하는 자동화 파이프라인입니다.

구조와 데이터 흐름은 [ARCHITECTURE.md](ARCHITECTURE.md)를 참고하세요.

## 🚀 주요 기능
- **자동 다운로드**: Playwright와 EBS 다운로더 PC 앱 제어로 지정한 회차를 다운로드
- **AI 전사**: faster-whisper(CTranslate2) `large-v3-turbo`로 한국어/영어 전사
- **스마트 MP3 분할**: 앵커 문구 + inaSpeechSegmenter(음악/음성 구간)로 영어 대화 구간만 정밀 추출
- **배포**: MP3는 Cloudflare R2, 플레이어는 GitHub Pages(`temp_repo`)로 배포
- **시니어 친화적 UI**: 큰 글씨, 배속 제어(0.5x~2.0x), 문장 반복

## ⚙️ 사전 요구사항
- Windows 10/11, NVIDIA GPU 권장(없으면 CPU로 자동 전환, 느림)
- Miniconda + conda 환경 `whisper_env`
- EBS 다운로더 PC 앱 설치, 다운로드 폴더 `C:\EBSe`(변경: `.env`의 `EBS_DOWNLOAD_DIR`)
- EBS 계정, Cloudflare R2 버킷

## 🛠️ 설치
```
conda create -n whisper_env python=3.9
setup.bat
```
`setup.bat`이 패키지 설치(`requirements.txt`), Chromium 설치, `.env` 생성을 수행합니다. 설치 후 `.env`를 편집하세요.

> Windows에서는 `tensorflow-cpu==2.10.0`, `numpy==1.23.5`, `protobuf==3.19.6` 조합이 안정적입니다(아래 개발 로그 8번).

## 🔑 환경변수 (`.env`)
| 키 | 설명 |
|---|---|
| `EBS_USERNAME`, `EBS_PASSWORD` | EBS 로그인 |
| `EBS_DOWNLOAD_DIR` | 다운로더 저장 폴더 (기본 `C:\EBSe`) |
| `R2_ACCOUNT_ID`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` | Cloudflare R2 인증 |
| `R2_BUCKET_NAME` | 버킷 이름 (기본 `ebs-learning`) |
| `R2_PUBLIC_URL` | R2 공개 URL (설정되면 실행 끝에 누락 파일을 일괄 업로드) |

`SUPABASE_*` 키는 사용 중단되었습니다.

## ▶️ 실행
```
run.bat                        # 최신 1개 회차
run.bat --episode 2707         # 특정 회차
run.bat --episode 2784-2817    # 범위
```
옵션: `--model`(기본 large-v3-turbo), `--device cuda|cpu`, `--process-existing`(이미 있는 파일도 처리), `--watch-first-delay`(다운로드 트리거 전 대기 초).

- 실행 중에는 GUI 자동화가 동작하므로 마우스/키보드를 조작하지 마세요.
- 회차가 많으면 `2784-2795`처럼 나눠 실행하고, 처음에는 `--episode 2784-2785`로 시험하는 것을 권장합니다.
- 결과물: `output_mp3/`(추출 MP3, 스크립트, player.json), R2(MP3 업로드), `temp_repo/`가 있으면 GitHub Pages로 push.

## ⏰ 매일 자동 실행 (스케줄러)
매일 저녁 8시(20:00)에 EBS 웹사이트를 확인하여, **아직 처리되지 않은 새 회차가 올라왔을 때만 자동으로 다운로드 및 Whisper 전사·배포를 수행**합니다. (이미 최신 상태이거나 주말/공휴일 등 새 회차가 없으면 10초 내로 스킵됩니다.)

### 스케줄러 등록 및 관리
- **스케줄러 등록 (매일 20:00)**: `tools\register_task.bat` 실행 (Windows 작업 스케줄러에 등록)
- **등록 상태 확인**: `tools\check_task.bat` 실행 (다음 실행 시각 및 상태 조회)
- **스케줄러 삭제**: `tools\unregister_task.bat` 실행

### 수동 실행 및 테스트
```
cron_run.bat                     # 기본 실행 (미처리 회차 최대 3개 순차 처리)
cron_run.bat --dry-run           # 실제 다운로드 없이 새 회차 감지 결과만 확인
cron_run.bat --max-batch 5       # 한 번에 처리할 최대 회차 수 지정
```
- 실행 로그는 `logs/cron_YYYY-MM-DD.log`에 자동 기록되며, 작업 완료 시 Windows 토스트 알림이 표시됩니다.
- *주의: 데스크탑 다운로더 PC 앱 UI 클릭이 필요하므로, 저녁 8시에 PC가 켜져 있고 화면이 로그인된 상태여야 정상 작동합니다.*

## 🧰 도구 (`tools/`)
| 명령 | 용도 |
|---|---|
| `tools\register_task.bat` | 매일 20:00 자동 전사 Windows 작업 스케줄러 등록 |
| `tools\check_task.bat` | 작업 스케줄러 등록 상태 및 다음 실행 예정 시간 확인 |
| `tools\unregister_task.bat` | 작업 스케줄러에서 자동 전사 작업 삭제 |
| `python -m tools.check_gpu` | GPU/CUDA 사용 가능 여부 확인 |
| `python -m tools.find_anchor <mp3>` | 앵커를 못 찾을 때 전사 결과를 보고 `src/config.py`의 `ANCHOR_PHRASES`에 추가할 문구 확인 |
| `python tools/retranscribe_episode.py 2754` | 추출된 MP3를 영어로 재전사해 player.json 스크립트 갱신 |
| `python tools/upload_to_r2.py [--dry-run]` | `output_mp3/`의 MP3를 R2에 업로드하고 player.json URL 교체 |

## 🩺 문제 해결
- **영어 구간을 못 찾음**: `tools/find_anchor`로 확인 후 `ANCHOR_PHRASES`에 추가
- **GPU 크래시 / CUDA 충돌**: inaSpeechSegmenter는 서브프로세스(`src/ina_worker.py`)로 분리되어 있음. 개발 로그 8~9번 참고
- **`mkl_malloc` 메모리 오류**: `run.bat`이 `OMP_NUM_THREADS=1`, `MKL_NUM_THREADS=1`을 설정함
- **콘솔 인코딩 오류**: `PYTHONIOENCODING=utf-8` (개발 로그 10번)
- **R2 업로드 실패**: `boto3` 설치 및 `.env`의 R2 키 확인

## 📝 개발 및 시행착오 기록 (Development Log)

본 프로젝트는 완성도 높은 사용자 경험을 위해 다음과 같은 기술적 도전과 해결 과정을 거쳤습니다.

### 1. 아키텍처 현대화 (Single Page Architecture)
- **문제**: 초기 시스템은 회차별로 정적 HTML을 생성하여 유지보수가 어렵고 저장 효율이 낮았음.
- **해결**: 단일 플레이어(`play.html`)와 JSON 데이터 기반의 동적 렌더링 방식으로 전환. UI 수정 시 한 번의 변경으로 모든 회차에 적용 가능해짐.

### 2. 파이프라인 정합성 확보
- **문제**: 배포 과정에서 신규 회차가 대시보드 리스트에서 누락되는 현상 발생.
- **원인**: 데이터가 DB에 완전히 저장되기 전에 대시보드가 생성되었기 때문임.
- **해결**: `[Supabase Upload] -> [Refresh Dashboard] -> [GitHub Push]` 순서로 파이프라인을 재설계하여 실시간 데이터 반영 보장.

### 3. 시니어 맞춤형 UX 개선
- **문제**: 모바일 환경에서 폰트가 작고 버튼 조작이 어려워 실제 사용자(어르신)의 가독성이 떨어짐.
- **해결**: 
  - 제목 폰트 28px, 본문 22px로 확대 적용.
  - 고대비(Dark Mode) 테마 적용으로 눈의 피로도 감소.
  - 배속 제어(0.5x~2.0x) 및 문장 반복(Repeat) 기능 추가.

### 4. 브라우저 캐시 무력화 (Cache Busting)
- **문제**: 코드 업데이트 후에도 사용자의 브라우저가 예전 파일을 계속 보여주는 현상 발생.
- **해결**: 
  - 플레이어 파일명을 `player.html`에서 `play.html`로 변경하여 강제 갱신 유도.
  - 데이터 호출 시 타임스탬프 파라미터(`?v=Date.now()`)를 추가하여 브라우저 캐시를 원천 차단.

### 5. 특수문자 및 인코딩 대응
- **문제**: 회차 제목에 로마자(`Ⅱ`), 한글 복합자 등이 포함될 경우 파일 경로를 찾지 못하는 문제 발생.
- **해결**: `decodeURIComponent` 기반의 견고한 URL 처리 로직을 플레이어에 이식하여 다양한 제목 형식에 완벽 대응.

### 6. 실시간 업데이트 시스템
- **문제**: 대량의 회차(예: 50개 이상)를 처리할 때 전체 종료 전까지 웹사이트가 업데이트되지 않음.
- **해결**: 매 회차 처리 완료 시마다 즉시 GitHub Push를 수행하는 **실시간 업데이트 모드** 도입.

### 7. AI 전사 품질 고도화 (Transcription Quality)
- **문제**: 세그먼트 간 중복 제거 과정에서 단어가 잘리거나(예: 'th' + 'e table'), 반복되는 대화 블록이 제대로 걸러지지 않는 현상 발생.
- **해결**:
  - **단어 경계 인식 중복 제거**: 단어 중간에서 텍스트가 잘리지 않도록 경계 검사 로직 추가.
  - **N-gram 고도화**: 기존 Bigram(n=2)에서 **Trigram(n=3)**으로 유사도 측정 방식을 업그레이드하여 정밀도 향상.
  - **모델 업그레이드**: Whisper `small`에서 **`medium`** 모델로 기본 설정을 변경하여 전사 정확도 및 환각 현상 대폭 개선.
  - **중복 검사 범위 확대**: 이전 3개에서 **10개 세그먼트**까지 검사 범위를 넓혀 반복되는 대화 블록을 완벽하게 처리.

### 8. Windows 환경에서의 TensorFlow 의존성 및 DLL 크래시 해결
- **문제**: Windows 가상 환경(`whisper_env`)에서 최신 TensorFlow 버전(2.12.0/2.20.0)이 C++ 네이티브 확장 모듈(`_pywrap_tensorflow_internal`) 로딩 실패(`DLL 초기화 루틴을 실행할 수 없습니다` 또는 `지정된 모듈을 찾을 수 없습니다`)를 유발하고 `numba` 라이브러리와 `numpy 2.x`가 호환되지 않는 심각한 패키지 꼬임 문제 발생. 이로 인해 음악/음성 분석용 `inaSpeechSegmenter` 임포트가 실패함.
- **해결**: 최신 TensorFlow 및 충돌하는 Numpy 2.x 패키지를 완전 제거하고, Windows에서 가장 완벽하게 동작하는 안정된 빌드인 **`tensorflow-cpu==2.10.0`**, **`numpy==1.23.5`**, **`protobuf==3.19.6`** 조합으로 전면 재설치하여 CPU 세그멘테이션 안정성을 완벽히 확보함.

### 9. TensorFlow/Keras 진행률 텍스트로 인한 서브프로세스 JSON 파싱 우회
- **문제**: ctranslate2(Whisper GPU)와의 CUDA 컨텍스트 경합 및 크래시를 회피하기 위해 `inaSpeechSegmenter`를 외부 서브프로세스(`src/ina_worker.py`)로 분리함. 그러나 TensorFlow C++ 코드가 native stdout으로 직접 출력하는 Keras 진행률 바(`2398/2398 - 23s...`)가 파이프라인의 결과 표준 출력을 오염시켜 `json.JSONDecodeError`를 야기하고 전체 추출 단계가 실패함.
- **해결**: [src/extractor.py](file:///c:/coding/github-repository/whisper-segment-extractor/src/extractor.py)의 결과 처리부에 **Robust JSON Parser** 로직을 이식. 표준 출력에서 첫 번째 괄호(`[`, `{`)와 마지막 괄호(`]`, `}`) 영역만을 동적으로 잘라내어 로드함으로써, 어떠한 경고 메시지나 TensorFlow native stdout 노이즈에도 강인하게 데이터 파싱을 완수하도록 강화함.

### 10. Windows 콘솔 이모지 유니코드 인코딩 크래시 방지
- **문제**: 파이프라인 진행 상태를 알리기 위해 출력하던 유니코드 이모지(예: `🔄`, `✅` 등)가 Windows 한글 인코딩 페이지(`CP949`) 환경의 스트림으로 캡처 및 리다이렉션될 때 `UnicodeEncodeError`를 일으키며 전체 가동 프로세스가 강제 중단됨.
- **해결**: 파이프라인 프로세스 기동 시 환경 변수에 **`PYTHONIOENCODING=utf-8`**을 강제로 주입하여 모든 콘솔 및 파일 캡처 스트림 인코딩을 UTF-8로 고정함으로써 문자 인코딩 관련 조기 크래시 리스크를 원천적으로 배제함.

### 11. 스케줄러 배치 파일 줄바꿈(LF) + 한글 → cmd가 깨진 명령 실행
- **문제**: 매일 20:00 스케줄러 창에 `'李⑸?'은(는) 내부 또는 외부 명령...` 같은 오류만 반복되고 작업이 실행되지 않음.
- **원인**: `cron_run.bat` 등이 **LF 줄바꿈 + 한글 주석**이라 cmd가 줄 경계를 잘못 잡아 주석 조각을 명령으로 실행.
- **해결**: 배치 파일을 **CRLF**로 변환. (.bat은 항상 CRLF로 저장할 것)

### 12. 다운로드 자동화가 "성공"인데 실제로는 시작되지 않음
- **문제**: 로그인 간헐 실패(`PW 입력란 못 찾음`), "다운로드 실행" 클릭이 먹지 않아 다운로더 목록이 "대기"로 남음, 다운로드가 실패해도 watcher가 영원히 대기.
- **해결**: 로그인 재시도(최대 3회, 대기 10초) / 클릭 후 **파일이 실제로 생기는지 확인하고 재클릭**(최대 4회) / 처리 대기 타임아웃(회차×10분, 최소 15분)과 실패 시 watcher 종료.
- **확인**: 스케줄 실행에서 로그인 재시도 성공, `다운로드 시작 확인`, 타임아웃 동작을 각각 로그로 확인.

### 13. watcher 경쟁 상태: 다운로드가 모델 로딩보다 먼저 끝나면 파일을 무시
- **문제**: 다운로드는 3/3 완료인데 처리가 시작되지 않음. watcher가 시작 시 이미 있는 파일을 "기존 파일"로 무시하는데, 모델 로딩이 길어져 그 사이 받은 파일까지 무시됨.
- **해결**: `--since`(실행 시작 시각) 옵션 — 그 시각 이후 생긴 파일은 새 파일로 처리.

### 14. 번역이 36개 회차(2784~2819)에서 통째로 누락 → Gemini API 전환
- **문제**: 공식 강의안이 없는 회차의 기계 번역(`deep-translator` Google 비공식 엔드포인트)이 **IP 차단(429)**되어 한국어 해석이 비었는데 파이프라인은 성공으로 보고. 지연·재시도로는 해결되지 않음.
- **해결**: `src/translator.py` — 한 회차의 문장을 **Gemini API로 묶어서 번역**(문맥 반영, 실패 시 Google 번역 대체), `tools/backfill_translations.py`로 153문장 복구. `.env`의 `GEMINI_API_KEY`가 OS 환경변수에 가려지는 문제도 `.env` 우선 읽기로 해결.

### 15. 방송 구조가 바뀐 회차(2820)와 조용한 실패, 간헐 INA 오류의 원인
- **문제**: "전체 대화" 안내 뒤에 한국어 설명이 이어지는 회차에서 구간이 어긋나 스크립트가 비었는데도 "성공" 처리되어 사이트까지 반영됨. 영어로 고정한 전사는 `I'm going to make a mission!` 같은 **환각**을 냄.
- **해결**: 보조 앵커(`미션 해결`), 구간을 좁힌 재전사(VAD + `condition_on_previous_text=False`), 결과물 검증(`[MISSING]`/`[NO-TRANSLATION]`) 추가. 구조가 다른 회차는 원본에서 대화 구간만 잘라 `tools/retranscribe_episode.py`로 복구.
- **근본 원인(INA 간헐 실패)**: `ina_worker`가 오류를 stdout으로 내는데 stderr만 출력해 원인이 가려져 있었음. 수정 후 **시스템 메모리/디스크 부족**(`Unable to allocate 265 MiB`, C: 여유 0.19GB, 가상 메모리 26GB 팽창)으로 확인됨.

---
*Last Updated: 2026-10-09*
