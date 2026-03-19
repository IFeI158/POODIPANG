# 🍱 PoodiPang (푸디팡)

한남대학교 디자인팩토리 CPD 수업 팀 프로젝트 (2024년 1학기)

ESP32-CAM으로 식판을 촬영하면 AI가 음식을 자동 인식하고 영양소를 분석해 출력하는 **스마트 식판 분석 시스템**입니다.

---

## 시연 영상

[![FoodiPang 시연](https://img.youtube.com/vi/kgzCFk0rImw/0.jpg)](https://www.youtube.com/watch?v=kgzCFk0rImw)

---

## 동작 흐름

```
ESP32-CAM 스트리밍
        ↓
실시간 영상 화면 표시
        ↓  [SPACE] 촬영
식판 자동 분할 (3×2 그리드)
        ↓
각 칸 → TFLite 모델 추론
        ↓
음식명 + 영양소 합산 결과 출력
```

---

## 저장소 구조

```
Poodipang/
├── model/
│   ├── model_unquant.tflite   TFLite 추론 모델
│   ├── labels.txt             클래스 레이블 (5종)
│   ├── model.json             Teachable Machine 원본 (TF.js)
│   ├── weights.bin            원본 가중치
│   └── metadata.json          메타데이터
│
├── src/
│   └── main.py                메인 실행 파일
│
├── arduino/
│   └── esp32cam_stream/
│       └── esp32cam_stream.ino  ESP32-CAM 펌웨어
│
├── requirements.txt
└── README.md
```

---

## 빠른 시작

### 1. 의존성 설치

```bash
pip install -r requirements.txt
```

### 2. ESP32-CAM 펌웨어 업로드

1. `arduino/esp32cam_stream/esp32cam_stream.ino` 를 Arduino IDE로 열기
2. `WIFI_SSID`, `WIFI_PASS` 수정
3. 보드: **AI Thinker ESP32-CAM** 선택
4. IO0 → GND 연결 후 업로드
5. 업로드 완료 후 IO0 → GND 해제, 리셋
6. 시리얼 모니터(115200)에서 IP 확인

### 3. 메인 프로그램 실행

```bash
# src/main.py 상단의 ESP32_IP 를 확인한 IP 로 수정
python3 src/main.py
```

### 키 조작

| 키 | 동작 |
|----|------|
| `SPACE` | 현재 화면 촬영 + 식판 분석 |
| `Q` / `ESC` | 종료 |

---

## AI 모델

- **Google Teachable Machine** 으로 학습
- 학습 설정: Epochs 50 / Batch 16 / LR 0.001
- 추론 형식: TFLite (Unquantized)
- 입력 크기: 224 × 224 px

| 음식 | 학습 이미지 |
|------|-----------|
| 밥 | 12장 |
| 미역국 | 10장 |
| 배추김치 | 11장 |
| 소야볶 | 13장 |
| 계란말이 | 12장 |

---

## 하드웨어

| 부품 | 역할 |
|------|------|
| ESP32-CAM (AI Thinker) | 식판 촬영 및 Wi-Fi 스트리밍 |
| LCD 디스플레이 | 분석 결과 출력 |
| MDF 합판 하우징 | 집 모양 본체 (직접 설계·제작·도색) |

---


