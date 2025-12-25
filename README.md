# Whisper Segment Extractor

Whisper AI를 활용하여 오디오 파일에서 특정 대화 구간을 자동으로 감지하고 추출하는 도구입니다.

강의, 팟캐스트, 인터뷰 등 다양한 오디오 콘텐츠에서 원하는 세그먼트를 정확하게 추출할 수 있습니다.

## 주요 기능

- 🎤 **Whisper STT**: OpenAI Whisper로 "전체대화" 앵커 자동 감지
- 🎼 **음악 인식**: inaSpeechSegmenter로 음악/음성 구간 자동 분석
- 🇬🇧 **영어 구간 추출**: 전사 분석으로 영어 대화만 정확하게 추출
- 📝 **스크립트 생성**: 대화 내용을 텍스트로 자동 변환
- ⚡ **고속 처리**: 23분부터 전사하여 처리 속도 2-3배 향상
- 🎯 **고음질**: 320kbps MP3로 무손실 수준 품질

## 설치

```bash
# 1. 필수 라이브러리
pip install openai-whisper pydub inaSpeechSegmenter tensorflow

# 2. FFmpeg 설치 (Windows)
choco install ffmpeg
```

## 사용 방법

## 사용 예시

### EBS 영어 강의
```bash
# "전체대화" 앵커로 대화 구간 추출
python smart_extract.py -f ebs_lecture.mp3 --model small
```

### 팟캐스트
```bash
# 특정 문구 이후 대화 추출 (코드 수정 필요)
python smart_extract.py -f podcast.mp3
```

### 인터뷰/회의록
```bash
# 폴더의 모든 오디오 파일 처리
python smart_extract.py --folder "C:\Recordings"
```

## 출력 파일

각 파일 처리 시 3개의 파일이 생성됩니다:

- `extracted_[파일명].mp3` - 추출된 영어 대화 오디오
- `script_[파일명].txt` - 대화 스크립트 (타임스탬프 포함)
- `transcription_[파일명].json` - 전체 전사 결과

## 동작 원리

1. **23분부터 전사**: 불필요한 앞부분 건너뛰기 (2-3배 빠름)
2. **앵커 감지**: "전체대화", "전체되어" 등 다양한 패턴 검색
3. **영어 구간 분석**: 각 세그먼트의 한글 비율로 영어/한국어 구분
4. **자동 종료**: 연속 2개 이상 한국어 세그먼트에서 추출 종료
5. **음악 시작점 조정**: inaSpeechSegmenter로 정확한 시작점 찾기

## 주요 스크립트

- `smart_extract.py` - **[권장]** Whisper 전사 기반 지능형 추출
- `fast_extract.py` - 고정 시간 기반 빠른 추출 (46초 offset + 50초)
- `batch_extract_conversation.py` - inaSpeechSegmenter만 사용 (느림)
- `extract_conversation.py` - 기본 추출 도구

## 옵션

```bash
python smart_extract.py --help

옵션:
  -f, --file FILE      처리할 특정 MP3 파일 경로
  --folder FOLDER      처리할 폴더 (기본: 현재 폴더)
  --model {tiny,base,small,medium,large}
                       Whisper 모델 크기 (기본: tiny)
```

## 모델 크기별 성능

| 모델 | 속도 | 정확도 | 권장 용도 |
|------|------|--------|-----------|
| tiny | ⚡⚡⚡ | ⭐⭐⭐ | 빠른 배치 처리 |
| base | ⚡⚡ | ⭐⭐⭐⭐ | 일반적 사용 |
| small | ⚡ | ⭐⭐⭐⭐⭐ | **권장** |
| medium | 🐌 | ⭐⭐⭐⭐⭐ | 최고 품질 |

## 트러블슈팅

### FFmpeg 오류
```
pip install pydub
choco install ffmpeg
```

### GPU 가속 (선택사항)
CUDA 설치 시 자동으로 GPU 사용 → 10배 빠름

### 앵커를 찾지 못하는 경우
`transcription_*.json` 파일을 열어 실제 앵커 문구 확인

## 라이선스

MIT License

## 기여

이슈나 PR은 언제든 환영합니다!
