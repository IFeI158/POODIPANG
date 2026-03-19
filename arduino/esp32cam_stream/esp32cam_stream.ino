/**
 * esp32cam_stream.ino — FoodiPang ESP32-CAM 스트리밍 서버
 *
 * Wi-Fi 연결 후 MJPEG 스트리밍 서버를 실행합니다.
 *
 * 엔드포인트
 * ----------
 *   /stream   MJPEG 연속 스트리밍 → main.py 자동 연결
 *   /capture  JPEG 단일 프레임
 *
 * 보드 설정 (Arduino IDE)
 * -----------------------
 *   보드   : AI Thinker ESP32-CAM
 *   속도   : 115200
 *
 * 업로드 방법
 * -----------
 *   1. IO0 핀 → GND 연결 (업로드 모드)
 *   2. 업로드 완료 후 IO0 → GND 해제, 리셋
 *   3. 시리얼 모니터에서 IP 확인 → main.py의 ESP32_IP 에 입력
 */

#include "esp_camera.h"
#include <WiFi.h>
#include "esp_http_server.h"

// ── Wi-Fi ─────────────────────────────────────────────────────────────────────
const char* WIFI_SSID = "your_ssid";       // ← 본인 Wi-Fi 이름
const char* WIFI_PASS = "your_password";   // ← 본인 Wi-Fi 비밀번호

// ── AI Thinker ESP32-CAM 핀 ───────────────────────────────────────────────────
#define PWDN_GPIO_NUM  32
#define RESET_GPIO_NUM -1
#define XCLK_GPIO_NUM   0
#define SIOD_GPIO_NUM  26
#define SIOC_GPIO_NUM  27
#define Y9_GPIO_NUM    35
#define Y8_GPIO_NUM    34
#define Y7_GPIO_NUM    39
#define Y6_GPIO_NUM    36
#define Y5_GPIO_NUM    21
#define Y4_GPIO_NUM    19
#define Y3_GPIO_NUM    18
#define Y2_GPIO_NUM     5
#define VSYNC_GPIO_NUM 25
#define HREF_GPIO_NUM  23
#define PCLK_GPIO_NUM  22

#define PART_BOUNDARY "frame_boundary"
static const char* STREAM_CONTENT_TYPE =
    "multipart/x-mixed-replace;boundary=" PART_BOUNDARY;
static const char* STREAM_BOUNDARY = "\r\n--" PART_BOUNDARY "\r\n";
static const char* STREAM_PART =
    "Content-Type: image/jpeg\r\nContent-Length: %u\r\n\r\n";

httpd_handle_t httpd = NULL;

// ── /stream ───────────────────────────────────────────────────────────────────
static esp_err_t stream_handler(httpd_req_t* req) {
    httpd_resp_set_type(req, STREAM_CONTENT_TYPE);
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");

    char buf[64];
    while (true) {
        camera_fb_t* fb = esp_camera_fb_get();
        if (!fb) { Serial.println("[ERR] 프레임 취득 실패"); return ESP_FAIL; }

        httpd_resp_send_chunk(req, STREAM_BOUNDARY, strlen(STREAM_BOUNDARY));
        size_t hlen = snprintf(buf, sizeof(buf), STREAM_PART, fb->len);
        httpd_resp_send_chunk(req, buf, hlen);
        esp_err_t res = httpd_resp_send_chunk(req, (const char*)fb->buf, fb->len);
        esp_camera_fb_return(fb);
        if (res != ESP_OK) break;
    }
    return ESP_OK;
}

// ── /capture ──────────────────────────────────────────────────────────────────
static esp_err_t capture_handler(httpd_req_t* req) {
    camera_fb_t* fb = esp_camera_fb_get();
    if (!fb) { httpd_resp_send_500(req); return ESP_FAIL; }
    httpd_resp_set_type(req, "image/jpeg");
    httpd_resp_set_hdr(req, "Access-Control-Allow-Origin", "*");
    esp_err_t res = httpd_resp_send(req, (const char*)fb->buf, fb->len);
    esp_camera_fb_return(fb);
    return res;
}

// ── 서버 시작 ─────────────────────────────────────────────────────────────────
void startServer() {
    httpd_config_t cfg = HTTPD_DEFAULT_CONFIG();

    httpd_uri_t stream_uri  = { "/stream",  HTTP_GET, stream_handler,  NULL };
    httpd_uri_t capture_uri = { "/capture", HTTP_GET, capture_handler, NULL };

    if (httpd_start(&httpd, &cfg) == ESP_OK) {
        httpd_register_uri_handler(httpd, &stream_uri);
        httpd_register_uri_handler(httpd, &capture_uri);
    }
}

// ── Setup ─────────────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);

    camera_config_t cfg;
    cfg.ledc_channel = LEDC_CHANNEL_0;
    cfg.ledc_timer   = LEDC_TIMER_0;
    cfg.pin_d0       = Y2_GPIO_NUM;  cfg.pin_d1 = Y3_GPIO_NUM;
    cfg.pin_d2       = Y4_GPIO_NUM;  cfg.pin_d3 = Y5_GPIO_NUM;
    cfg.pin_d4       = Y6_GPIO_NUM;  cfg.pin_d5 = Y7_GPIO_NUM;
    cfg.pin_d6       = Y8_GPIO_NUM;  cfg.pin_d7 = Y9_GPIO_NUM;
    cfg.pin_xclk     = XCLK_GPIO_NUM;
    cfg.pin_pclk     = PCLK_GPIO_NUM;
    cfg.pin_vsync    = VSYNC_GPIO_NUM;
    cfg.pin_href     = HREF_GPIO_NUM;
    cfg.pin_sccb_sda = SIOD_GPIO_NUM;
    cfg.pin_sccb_scl = SIOC_GPIO_NUM;
    cfg.pin_pwdn     = PWDN_GPIO_NUM;
    cfg.pin_reset    = RESET_GPIO_NUM;
    cfg.xclk_freq_hz = 20000000;
    cfg.pixel_format = PIXFORMAT_JPEG;
    cfg.frame_size   = FRAMESIZE_VGA;   // 640×480
    cfg.jpeg_quality = 12;
    cfg.fb_count     = 2;

    if (esp_camera_init(&cfg) != ESP_OK) {
        Serial.println("[ERR] 카메라 초기화 실패");
        return;
    }

    WiFi.begin(WIFI_SSID, WIFI_PASS);
    Serial.print("[INFO] Wi-Fi 연결 중");
    while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
    Serial.println();
    Serial.print("[INFO] IP 주소: ");
    Serial.println(WiFi.localIP());
    Serial.println("[INFO] main.py 의 ESP32_IP 를 위 주소로 설정하세요.");

    startServer();
    Serial.println("[INFO] 스트리밍 서버 시작 완료");
}

void loop() { delay(10000); }
