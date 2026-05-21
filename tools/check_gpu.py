"""
GPU 사용 가능 여부 확인.

사용:
  python -m tools.check_gpu
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))


def check_pytorch_cuda():
    print("=" * 80)
    print("PyTorch + CUDA")
    print("=" * 80)
    try:
        import torch
        print(f"PyTorch 버전: {torch.__version__}")
        print(f"CUDA 사용 가능: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"CUDA 버전: {torch.version.cuda}")
            print(f"cuDNN 버전: {torch.backends.cudnn.version()}")
            print(f"GPU 개수: {torch.cuda.device_count()}")
            for i in range(torch.cuda.device_count()):
                name = torch.cuda.get_device_name(i)
                mem = torch.cuda.get_device_properties(i).total_memory / (1024**3)
                print(f"  GPU {i}: {name} ({mem:.1f} GB)")
            print("\n[OK] Whisper 가 GPU 를 사용합니다!")
        else:
            print("\n[INFO] CUDA 사용 불가 - CPU 로 동작")
            print("\nGPU 사용을 원한다면:")
            print("  1. NVIDIA GPU 가 있는지 확인")
            print("  2. CUDA Toolkit 설치 여부 확인")
            print("  3. PyTorch CUDA 버전 재설치:")
            print("     pip uninstall torch")
            print("     pip install torch --index-url https://download.pytorch.org/whl/cu121")
            print("     (cu121 = CUDA 12.1, 본인 CUDA 버전에 맞게 변경)")
    except ImportError as e:
        print(f"[ERROR] PyTorch 미설치: {e}")
        print("  pip install torch")
    print()


def check_tensorflow_gpu():
    print("=" * 80)
    print("TensorFlow + GPU (inaSpeechSegmenter 용)")
    print("=" * 80)
    try:
        import tensorflow as tf
        print(f"TensorFlow 버전: {tf.__version__}")
        gpus = tf.config.list_physical_devices('GPU')
        print(f"감지된 GPU: {len(gpus)}개")
        for gpu in gpus:
            print(f"  {gpu}")

        if gpus:
            print("\n[OK] inaSpeechSegmenter 가 GPU 를 사용할 수 있습니다.")
        else:
            print("\n[INFO] GPU 인식 안 됨 - inaSpeechSegmenter 는 CPU 사용")
            print("       (Whisper 는 별도로 GPU 사용 가능)")
    except ImportError:
        print("[ERROR] TensorFlow 미설치")
    print()


def check_whisper():
    print("=" * 80)
    print("Whisper (faster-whisper 백엔드)")
    print("=" * 80)
    try:
        import faster_whisper
        print(f"faster-whisper 버전: {faster_whisper.__version__}")

        from src.extractor import detect_device
        from src.config import DEFAULT_MODEL
        device = detect_device()
        print(f"자동 감지된 디바이스: {device}")
        print(f"기본 모델: {DEFAULT_MODEL}")
        if device == "cuda":
            print("compute_type: float16 (CUDA)")
        else:
            print("compute_type: int8 (CPU)")
    except ImportError:
        print("[ERROR] faster-whisper 미설치")
        print("  pip install faster-whisper")
    print()


if __name__ == "__main__":
    print()
    check_pytorch_cuda()
    check_tensorflow_gpu()
    check_whisper()

    print("=" * 80)
    print("실행 시 GPU 사용 명시:")
    print("=" * 80)
    print("  run.bat --episode 2707          # 자동 감지 (기본)")
    print("  python -m src.runner --device cuda --episode 2707  # GPU 강제")
    print("  python -m src.runner --device cpu --episode 2707   # CPU 강제")
    print()
