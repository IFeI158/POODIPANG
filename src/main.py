"""
main.py — 푸디팡 (FoodiPang) 스마트 식판 분석 시스템

ESP32-CAM 스트리밍 영상을 화면에 표시하고,
SPACE 키를 누르면 식판을 3×2 그리드로 분할해
각 칸의 음식을 TFLite 모델로 인식합니다.

키 조작
-------
  SPACE  : 현재 화면 촬영 + 식판 분석
  Q / ESC: 종료

의존성 설치
-----------
  pip install opencv-python numpy tensorflow requests

ESP32-CAM 연결
--------------
  1. arduino/esp32cam_stream.ino 업로드
  2. 시리얼 모니터(115200)에서 IP 확인
  3. 아래 ESP32_IP 변수에 입력
"""

import cv2
import numpy as np
import threading
import time
import requests
import os
import tensorflow as tf

# ── 설정 ──────────────────────────────────────────────────────────────────────
ESP32_IP    = "192.168.0.101"           # ← 시리얼 모니터에서 확인한 IP 입력
STREAM_URL  = f"http://{ESP32_IP}/stream"
CAPTURE_URL = f"http://{ESP32_IP}/capture"

MODEL_DIR   = os.path.join(os.path.dirname(__file__), "..", "model")
MODEL_PATH  = os.path.join(MODEL_DIR, "model_unquant.tflite")
LABELS_PATH = os.path.join(MODEL_DIR, "labels.txt")

IMAGE_SIZE  = 224       # Teachable Machine 입력 크기
GRID_ROWS   = 2         # 식판 세로 칸 수
GRID_COLS   = 3         # 식판 가로 칸 수
CONF_THRESH = 0.5       # 신뢰도 임계값 (이하 → "인식 불가")
WIN_W       = 960       # 창 너비
WIN_H       = 600       # 창 높이
PANEL_W     = 320       # 우측 결과 패널 너비

# ── 영양소 DB (100g 기준) ──────────────────────────────────────────────────────
NUTRITION = {
    "밥":      {"kcal": 168, "protein": 2.6, "carb": 38.1, "fat": 0.3},
    "미역국":  {"kcal":  18, "protein": 1.2, "carb":  1.8, "fat": 0.8},
    "배추김치":{"kcal":  18, "protein": 1.1, "carb":  3.3, "fat": 0.5},
    "소야볶":  {"kcal": 105, "protein": 7.4, "carb":  4.2, "fat": 6.5},
    "계란말이":{"kcal": 154, "protein": 9.8, "carb":  2.1, "fat":11.8},
}


# ── 모델 & 라벨 로드 ──────────────────────────────────────────────────────────
def load_model():
    interpreter = tf.lite.Interpreter(model_path=MODEL_PATH)
    interpreter.allocate_tensors()

    with open(LABELS_PATH, encoding="utf-8") as f:
        labels = [line.strip().split(" ", 1)[1] for line in f if line.strip()]

    print(f"[INFO] 모델 로드 완료  클래스: {labels}")
    return interpreter, labels


# ── 추론 ──────────────────────────────────────────────────────────────────────
def predict(interpreter, labels, img_bgr):
    img = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    img = cv2.resize(img, (IMAGE_SIZE, IMAGE_SIZE)).astype(np.float32) / 255.0
    img = np.expand_dims(img, axis=0)

    in_idx  = interpreter.get_input_details()[0]["index"]
    out_idx = interpreter.get_output_details()[0]["index"]
    interpreter.set_tensor(in_idx, img)
    interpreter.invoke()

    probs  = interpreter.get_tensor(out_idx)[0]
    top    = int(np.argmax(probs))
    conf   = float(probs[top])

    return (labels[top], conf) if conf >= CONF_THRESH else ("인식 불가", conf)


# ── 식판 분할 ─────────────────────────────────────────────────────────────────
def split_tray(frame):
    h, w   = frame.shape[:2]
    ch, cw = h // GRID_ROWS, w // GRID_COLS
    return [
        (frame[r*ch:(r+1)*ch, c*cw:(c+1)*cw].copy(), r, c)
        for r in range(GRID_ROWS)
        for c in range(GRID_COLS)
    ]


# ── 카메라 뷰 오버레이 ────────────────────────────────────────────────────────
def draw_grid_overlay(frame, results):
    h, w   = frame.shape[:2]
    ch, cw = h // GRID_ROWS, w // GRID_COLS
    out    = frame.copy()

    for food, conf, r, c in results:
        x1, y1 = c * cw, r * ch
        x2, y2 = x1 + cw, y1 + ch
        color  = (50, 210, 80) if food != "인식 불가" else (60, 60, 200)

        cv2.rectangle(out, (x1, y1), (x2, y2), color, 2)
        label = f"{food}  {conf*100:.0f}%"
        (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(out, (x1+4, y1+4), (x1+tw+12, y1+th+14), (0,0,0), -1)
        cv2.putText(out, label, (x1+8, y1+th+8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,255,255), 1)

    return out


# ── 우측 영양소 패널 ──────────────────────────────────────────────────────────
def make_panel(results):
    panel = np.full((WIN_H, PANEL_W, 3), 28, dtype=np.uint8)
    y = 30

    def text(msg, color=(210,210,210), scale=0.52, bold=1):
        nonlocal y
        cv2.putText(panel, msg, (14, y),
                    cv2.FONT_HERSHEY_SIMPLEX, scale, color, bold)
        y += int(scale * 44)

    text("[ 식판 분석 결과 ]", (90, 210, 90), 0.62, 2)
    y += 6

    total = {k: 0.0 for k in ("kcal","protein","carb","fat")}
    seen  = set()

    for food, conf, r, c in results:
        if food == "인식 불가" or food in seen:
            continue
        seen.add(food)
        text(f"  {food} ({conf*100:.0f}%)", (220,210,80), 0.55, 1)

        if food in NUTRITION:
            n = NUTRITION[food]
            text(f"    {n['kcal']}kcal  P:{n['protein']}g  C:{n['carb']}g  F:{n['fat']}g",
                 (160,160,160), 0.42)
            for k in total:
                total[k] += n[k]
        y += 4

    # 합계 구분선
    cv2.line(panel, (12, y), (PANEL_W-12, y), (70,70,70), 1);  y += 16
    text("[ 합 계 ]", (110,170,255), 0.60, 2)
    text(f"  열량    {total['kcal']:.0f} kcal")
    text(f"  단백질  {total['protein']:.1f} g")
    text(f"  탄수화물 {total['carb']:.1f} g")
    text(f"  지방    {total['fat']:.1f} g")

    # 조작 안내
    y = WIN_H - 54
    cv2.line(panel, (12, y), (PANEL_W-12, y), (55,55,55), 1); y += 16
    cv2.putText(panel, "SPACE : 촬영 & 분석", (12, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.43, (110,110,110), 1); y += 20
    cv2.putText(panel, "Q / ESC : 종료",     (12, y),
                cv2.FONT_HERSHEY_SIMPLEX, 0.43, (110,110,110), 1)
    return panel


# ── ESP32-CAM 스트림 (백그라운드 스레드) ──────────────────────────────────────
class ESP32Stream:
    def __init__(self):
        self.frame   = None
        self._active = False

    def start(self):
        self._active = True
        threading.Thread(target=self._loop, daemon=True).start()

    def stop(self):
        self._active = False

    def _loop(self):
        cap = cv2.VideoCapture(STREAM_URL)
        while self._active:
            ret, frame = cap.read()
            if ret:
                self.frame = frame
            else:
                time.sleep(0.03)
        cap.release()


# ── 메인 ─────────────────────────────────────────────────────────────────────
def main():
    print("=" * 48)
    print("  🍱  FoodiPang — 스마트 식판 분석기")
    print("=" * 48)

    interpreter, labels = load_model()

    stream = ESP32Stream()
    stream.start()
    print(f"[INFO] ESP32-CAM 연결 중  ({STREAM_URL})")
    time.sleep(1.5)

    cam_w   = WIN_W - PANEL_W
    results = []
    panel   = make_panel([])

    cv2.namedWindow("FoodiPang", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("FoodiPang", WIN_W, WIN_H)
    print("[INFO] 준비 완료  SPACE=촬영  Q=종료")

    while True:
        frame = stream.frame

        # 카메라 뷰
        if frame is None:
            cam_view = np.full((WIN_H, cam_w, 3), 22, dtype=np.uint8)
            cv2.putText(cam_view, "ESP32-CAM 연결 대기 중...",
                        (20, WIN_H // 2), cv2.FONT_HERSHEY_SIMPLEX,
                        0.7, (90, 90, 90), 1)
        else:
            cam_view = cv2.resize(frame, (cam_w, WIN_H))
            if results:
                cam_view = draw_grid_overlay(cam_view, results)

        cv2.imshow("FoodiPang", np.hstack([cam_view, panel]))
        key = cv2.waitKey(30) & 0xFF

        # SPACE — 촬영 & 분석
        if key == ord(' '):
            if stream.frame is None:
                print("[WARN] 프레임 없음")
                continue
            snap    = stream.frame.copy()
            results = []
            print("\n[INFO] 분석 시작...")
            for cell, r, c in split_tray(snap):
                food, conf = predict(interpreter, labels, cell)
                results.append((food, conf, r, c))
                print(f"  [{r},{c}] {food:10s} {conf*100:.1f}%")
            panel = make_panel(results)
            print("[INFO] 완료")

        elif key in (ord('q'), 27):
            break

    stream.stop()
    cv2.destroyAllWindows()
    print("[INFO] 종료")


if __name__ == "__main__":
    main()
