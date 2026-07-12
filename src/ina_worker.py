"""
inaSpeechSegmenter 서브프로세스 워커.

ctranslate2(Whisper GPU)와 TensorFlow(INA)가 같은 프로세스에서 CUDA 컨텍스트를
공유하면 GPU inference 중 crash(exit 9) 발생. 이 스크립트를 별도 프로세스로
실행해 TF와 ctranslate2를 완전히 격리한다.

사용법: python -m src.ina_worker <audio_path>
출력:   JSON 배열 (label, start, end) → stdout

Keras/TF 진행률 출력(2398/2398 - 23s ...)이 stdout을 오염시키면 JSON 파싱이
실패하므로, INA 호출 전에 sys.stdout을 sys.stderr로 교체해 격리한다.
"""
import json
import sys


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "audio_path argument required"}))
        sys.exit(1)

    audio_path = sys.argv[1]

    # Keras/TF가 stdout에 쓰는 진행률 출력을 stderr로 돌림
    # JSON 결과만 원래 stdout(real_stdout)으로 출력
    real_stdout = sys.stdout
    sys.stdout = sys.stderr

    try:
        from inaSpeechSegmenter import Segmenter
        segmenter = Segmenter()
        segments = segmenter(audio_path)
        result = [{"label": label, "start": float(start), "end": float(end)}
                  for label, start, end in segments]
    except Exception as e:
        sys.stdout = real_stdout
        print(json.dumps({"error": str(e)}))
        sys.exit(1)

    sys.stdout = real_stdout
    print(json.dumps(result))


if __name__ == "__main__":
    main()
