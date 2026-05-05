# EBS 왕초보 영어 자동화 시스템

EBS 왕초보 영어 다시보기 MP3를 **자동으로 다운로드 → 영어 대화 구간만 추출**하는 통합 시스템입니다.

## 🎬 동작 흐름

```
[run_all.py 한 번 실행]
        │
        ├─ 1) watch_and_extract.py 백그라운드 시작 (감시 모드)
        │
        ├─ 2) ebs_auto_download.py 실행
        │      ├─ 사용자의 Chrome 프로필로 브라우저 열기 (네이버 로그인 유지)
        │      ├─ EBS 다시보기 페이지 이동
        │      ├─ 최신 회차 클릭 → MP3 버튼 클릭
        │      └─ EBS Downloader 외부 앱 실행
        │
        ├─ 3) EBS Downloader 가 C:\EBSe\ 에 MP3 다운로드 (자동)
        │
        └─ 4) watch_and_extract 가 새 MP3 감지
               ├─ source_mp3/ 로 이동
               ├─ smart_extract 실행 (Whisper 영어 구간 추출)
               └─ output_mp3/ 에 결과 저장
```

## 📦 구성 파일

| 파일 | 역할 |
|------|------|
| `smart_extract.py` | 핵심 추출 엔진 (Whisper + inaSpeech) |
| `watch_and_extract.py` | EBS Downloader 저장 폴더 감시 + 자동 추출 |
| `ebs_auto_download.py` | Chrome 자동화로 EBS 사이트 다운로드 트리거 |
| **`run_all.py`** | **위 두 스크립트 통합 실행** ⭐ |

## 🚀 빠른 시작

### 1단계: 의존성 설치

```bash
pip install selenium openai-whisper pydub inaSpeechSegmenter tensorflow
```

### 2단계: 첫 실행 (한 번만 수동 로그인)

처음에는 네이버 로그인을 위해 한 번 수동으로 로그인해야 합니다.

```bash
# 같은 프로필을 쓰는 모든 Chrome 창을 먼저 닫으세요!
python ebs_auto_download.py --keep-open
```

브라우저가 열리면:
1. 네이버 로그인 (수동)
2. EBS Downloader 팝업 발생 시 **"항상 home.ebse.co.kr 에서 ... 허용"** 체크박스 선택
3. "EBS Downloader 열기" 클릭
4. EBS Downloader 가 동작하는지 확인

이렇게 한 번만 설정하면 다음부터는 완전 자동입니다.

### 3단계: 일상 사용

```bash
python run_all.py
```

이 한 줄이면 끝입니다. 자동으로:
- Chrome 열기 → 최신 회차 다운로드 트리거
- 폴더 감시 → 다운로드 완료 감지
- 영어 구간 추출 → `output_mp3/` 에 결과 저장

## 🎛️ 옵션

### `run_all.py` (통합)

```bash
python run_all.py --model small        # Whisper 모델 (기본: small)
```

### `ebs_auto_download.py` (다운로드만)

```bash
python ebs_auto_download.py --keep-open                          # 브라우저 안 닫음
python ebs_auto_download.py --user-data-dir "D:\Chrome\Profile"  # Chrome 프로필 변경
python ebs_auto_download.py --profile "Profile 1"                # 프로필 이름 지정
```

### `watch_and_extract.py` (추출만)

```bash
python watch_and_extract.py                       # 무한 감시
python watch_and_extract.py --once                # 1개 처리 후 종료
python watch_and_extract.py --process-existing    # 기존 파일도 처리
python watch_and_extract.py --debug               # 디버그 로그
python watch_and_extract.py --watch-dir "D:\다운로드"  # 다른 폴더 감시
python watch_and_extract.py --model tiny          # Whisper 모델 변경
```

## ⚠️ 중요 사항

### Chrome 프로필 충돌

Chrome 은 **동일 프로필을 동시에 두 곳에서 사용할 수 없습니다**. `ebs_auto_download.py` 실행 전에 같은 프로필을 쓰는 모든 Chrome 창을 닫아야 합니다.

별도 Chrome 인스턴스를 쓰고 싶다면 새 프로필을 만들어 `--user-data-dir` 와 `--profile` 옵션을 지정하세요.

### EBS Downloader 저장 경로

기본값은 `C:\EBSe` 입니다. (EBS Downloader UI 에서는 폰트 때문에 `C:\WEBSe` 처럼 보일 수 있지만 실제 폴더명은 `C:\EBSe` 입니다.)

다른 경로로 바꿨다면:
```bash
python watch_and_extract.py --watch-dir "D:\내경로"
```

### 페이지 구조 변경

EBS 사이트 HTML 구조가 변경되면 셀렉터가 안 맞을 수 있습니다. `ebs_auto_download.py` 의 `find_first_replay_link()` 와 `find_first_mp3_button()` 함수에 여러 셀렉터 후보가 들어 있어 어느 정도 견고하지만, 완전히 바뀌면 수정이 필요합니다.

## 🔒 보안 관련

- **이 시스템은 자동 로그인을 하지 않습니다**. 사용자가 한 번 직접 로그인한 Chrome 프로필을 재사용할 뿐입니다.
- 비밀번호는 어디에도 저장되지 않습니다.
- 네이버 약관상 자동 로그인 매크로는 금지되어 있어 의도적으로 그 부분은 제외했습니다.

## 📂 출력 파일

`output_mp3/` 폴더에 회차당 4개 파일이 생성됩니다.

| 파일명 | 설명 |
|--------|------|
| `extracted_<원본>.mp3` | 추출된 영어 대화 (320kbps) |
| `script_<원본>.txt` | 한국어 전사 스크립트 (타임스탬프 포함) |
| `transcription_<원본>.json` | 원본 한국어 전사 전체 |
| `player_<원본>.json` | 웹 플레이어용 영어 전사 (0초 기준) |

## 🐛 트러블슈팅

### "Chrome 실행 실패"
같은 프로필을 쓰는 다른 Chrome 창을 모두 닫고 재시도. Chrome 작업 관리자에서 백그라운드 프로세스도 종료하세요.

### "다시보기 링크를 찾지 못했습니다"
로그인 상태가 아닐 가능성 → `--keep-open` 으로 실행 후 페이지 상태 확인

### "MP3 버튼을 찾지 못했습니다"
회차 페이지가 제대로 로딩되지 않았을 수 있음 → `time.sleep(4)` 값을 늘려 보세요

### "새 파일이 감지되지 않음"
```bash
python watch_and_extract.py --debug
```
로 폴더 스캔 결과 확인. 파일명 패턴(`YYYYMMDD_HHMMSS_xxxxxxxx_mp3.mp3`)이 맞는지, EBS Downloader 의 실제 저장 경로가 맞는지 점검.

### "Selenium Manager 가 드라이버를 찾지 못함"
Selenium 4.6 미만 버전일 가능성:
```bash
pip install -U selenium
```
