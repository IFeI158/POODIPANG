"""
convert_to_tflite.py — Teachable Machine TF.js 모델 → TFLite 변환

Teachable Machine에서 export한 TF.js 모델(model.json + weights.bin)을
TensorFlow Lite 형식으로 변환합니다.

변환 후 생성 파일:
  model/model.tflite   → ESP32 / 로컬 추론용
  model/labels.txt     → 클래스명 목록

사용법:
  pip install tensorflow tensorflowjs
  python3 src/convert_to_tflite.py
"""

import json
import os
import numpy as np

MODEL_DIR   = os.path.join(os.path.dirname(__file__), "..", "model")
TFJS_MODEL  = os.path.join(MODEL_DIR, "model.json")
TFLITE_OUT  = os.path.join(MODEL_DIR, "model.tflite")
LABELS_OUT  = os.path.join(MODEL_DIR, "labels.txt")
META_FILE   = os.path.join(MODEL_DIR, "metadata.json")


def load_labels():
    with open(META_FILE, encoding="utf-8") as f:
        meta = json.load(f)
    return meta["labels"]


def convert():
    import tensorflow as tf
    import tensorflowjs as tfjs

    print("[1/3] TF.js 모델 로드 중...")
    tmp_saved = os.path.join(MODEL_DIR, "_saved_model_tmp")
    tfjs.converters.load_keras_model(TFJS_MODEL).save(tmp_saved)
    print(f"      SavedModel 저장: {tmp_saved}")

    print("[2/3] TFLite 변환 중...")
    converter = tf.lite.TFLiteConverter.from_saved_model(tmp_saved)
    converter.optimizations = [tf.lite.Optimize.DEFAULT]   # 양자화 (크기 축소)
    tflite_model = converter.convert()

    with open(TFLITE_OUT, "wb") as f:
        f.write(tflite_model)
    print(f"      TFLite 저장: {TFLITE_OUT}  ({len(tflite_model)/1024:.1f} KB)")

    print("[3/3] labels.txt 저장 중...")
    labels = load_labels()
    with open(LABELS_OUT, "w", encoding="utf-8") as f:
        for i, label in enumerate(labels):
            f.write(f"{i} {label}\n")
    print(f"      클래스: {labels}")

    print("\n✅ 변환 완료!")
    print(f"   모델: {TFLITE_OUT}")
    print(f"   라벨: {LABELS_OUT}")


if __name__ == "__main__":
    convert()
