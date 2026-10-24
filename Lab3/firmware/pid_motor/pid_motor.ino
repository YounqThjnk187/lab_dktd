/*
 * Lab 3 - Vòng lặp PID rời rạc điều khiển vận tốc động cơ DC
 * ESP32 DevKit V1 + TB6612FNG + JGA25-370 (encoder Hall 2 kênh)
 *
 * Đấu nối:
 *   TB6612  PWMA -> GPIO25   AIN1 -> GPIO26   AIN2 -> GPIO27   STBY -> GPIO33
 *           VM   -> 12V (pin 18650 x2 / nguồn tổ ong)   VCC -> 3V3   GND chung
 *           AO1/AO2 -> 2 dây động cơ
 *   Encoder A -> GPIO18   B -> GPIO19   VCC -> 3V3   GND -> GND
 *
 * Lệnh Serial (115200, kết thúc bằng '\n'):
 *   kp <v> | ki <v> | kd <v> | pid <kp> <ki> <kd>
 *   sp <rpm>      : đặt vận tốc, chuyển sang vòng kín
 *   open <duty%>  : chạy vòng hở (-100..100), dùng cho nhận dạng / Ziegler-Nichols
 *   stop          : dừng động cơ
 *   reset         : xóa tích phân và e[k-1]
 *   rate <n>      : chỉ in 1 mẫu mỗi n chu kỳ
 *   ?             : in tham số hiện tại
 * Dữ liệu ra: "D,<t_ms>,<sp_rpm>,<rpm>,<u_%>"
 */
#include <Arduino.h>

// ---------------- Chân ----------------
constexpr int PIN_PWMA  = 25;
constexpr int PIN_AIN1  = 26;
constexpr int PIN_AIN2  = 27;
constexpr int PIN_STBY  = 33;
constexpr int PIN_ENC_A = 18;   // phải < 32 vì ISR đọc GPIO_IN_REG
constexpr int PIN_ENC_B = 19;

// ---------------- Động cơ / encoder ----------------
constexpr float ENC_PPR    = 11.0f;  // xung/vòng trên trục động cơ (trước hộp số)
constexpr float GEAR_RATIO = 34.0f;  // xem nhãn động cơ: 1:21.3, 1:34, 1:46.8, ...
constexpr float DECODE     = 4.0f;   // giải mã x4 (CHANGE trên cả A và B)
constexpr float CPR        = ENC_PPR * GEAR_RATIO * DECODE;  // count / vòng trục ra
constexpr int   ENC_DIR    = 1;      // đổi thành -1 nếu u>0 mà rpm<0

// ---------------- Vòng điều khiển ----------------
constexpr uint32_t TS_MS     = 10;
constexpr float    TS        = TS_MS / 1000.0f;
constexpr float    U_MAX     = 100.0f;  // giới hạn đầu ra (% duty)
constexpr float    RPM_ALPHA = 0.3f;    // lọc EMA vận tốc, 1.0 = không lọc

// ---------------- PWM ----------------
constexpr int PWM_FREQ     = 20000;
constexpr int PWM_RES_BITS = 10;
constexpr int PWM_MAX      = (1 << PWM_RES_BITS) - 1;
constexpr int PWM_CH       = 0;  // chỉ dùng cho core 2.x

// ================= Encoder =================
volatile int32_t encCount = 0;
volatile uint8_t encPrev  = 0;
portMUX_TYPE encMux = portMUX_INITIALIZER_UNLOCKED;

// Bảng giải mã cầu phương, chỉ số = (trạng thái cũ << 2) | trạng thái mới, trạng thái = (A<<1)|B
const int8_t QDEC[16] = {0, -1, 1, 0, 1, 0, 0, -1, -1, 0, 0, 1, 0, 1, -1, 0};

void IRAM_ATTR encoderISR() {
  uint32_t in = REG_READ(GPIO_IN_REG);
  uint8_t s = (((in >> PIN_ENC_A) & 1) << 1) | ((in >> PIN_ENC_B) & 1);
  portENTER_CRITICAL_ISR(&encMux);
  encCount += QDEC[(encPrev << 2) | s];
  encPrev = s;
  portEXIT_CRITICAL_ISR(&encMux);
}

int32_t readEncoder() {
  portENTER_CRITICAL(&encMux);
  int32_t c = encCount;
  portEXIT_CRITICAL(&encMux);
  return c;
}

// ================= PID rời rạc =================
struct PID {
  float kp = 0.8f, ki = 8.0f, kd = 0.0f;
  float sumE  = 0.0f;  // Σe[k]
  float ePrev = 0.0f;  // e[k-1]

  // u[k] = Kp·e[k] + Ki·Ts·Σe[k] + Kd·(e[k]-e[k-1])/Ts
  float compute(float e) {
    float sumNew = sumE + e;
    float u = kp * e + ki * TS * sumNew + kd * (e - ePrev) / TS;

    // Anti-windup (conditional integration): không tích lũy khi bão hòa cùng chiều với e
    if (u > U_MAX) {
      u = U_MAX;
      if (e < 0) sumE = sumNew;
    } else if (u < -U_MAX) {
      u = -U_MAX;
      if (e > 0) sumE = sumNew;
    } else {
      sumE = sumNew;
    }
    ePrev = e;
    return u;
  }

  void reset() { sumE = 0.0f; ePrev = 0.0f; }
};

// ================= Tham số dùng chung giữa loop() và controlTask =================
enum class Mode : uint8_t { STOP, OPEN, CLOSED };

struct Shared {
  float kp = 0.8f, ki = 8.0f, kd = 0.0f;
  float sp = 0.0f;
  float openDuty = 0.0f;
  Mode  mode = Mode::STOP;
  bool  resetReq = false;
} g;
portMUX_TYPE paramMux = portMUX_INITIALIZER_UNLOCKED;

struct Sample {
  uint32_t t;
  float sp, rpm, u;
};
QueueHandle_t sampleQueue;
uint32_t logDiv = 1;

// ================= Driver động cơ =================
void motorInit() {
  pinMode(PIN_AIN1, OUTPUT);
  pinMode(PIN_AIN2, OUTPUT);
  pinMode(PIN_STBY, OUTPUT);
  digitalWrite(PIN_STBY, HIGH);
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(PIN_PWMA, PWM_FREQ, PWM_RES_BITS);
#else
  ledcSetup(PWM_CH, PWM_FREQ, PWM_RES_BITS);
  ledcAttachPin(PIN_PWMA, PWM_CH);
#endif
}

void motorWrite(float u) {  // u: -100..100 %
  u = constrain(u, -U_MAX, U_MAX);
  digitalWrite(PIN_AIN1, u >= 0 ? HIGH : LOW);
  digitalWrite(PIN_AIN2, u >= 0 ? LOW : HIGH);
  uint32_t duty = (uint32_t)(fabsf(u) / 100.0f * PWM_MAX);
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(PIN_PWMA, duty);
#else
  ledcWrite(PWM_CH, duty);
#endif
}

// ================= Task điều khiển, chu kỳ cố định Ts =================
void controlTask(void *) {
  PID pid;
  int32_t prevCount = readEncoder();
  float rpm = 0.0f;
  TickType_t last = xTaskGetTickCount();

  for (;;) {
    vTaskDelayUntil(&last, pdMS_TO_TICKS(TS_MS));

    // 1. Đo vận tốc
    int32_t c = readEncoder();
    int32_t dc = c - prevCount;
    prevCount = c;
    float rpmRaw = ENC_DIR * (dc / CPR) / TS * 60.0f;
    rpm += RPM_ALPHA * (rpmRaw - rpm);

    // 2. Chụp tham số (có thể bị đổi bất kỳ lúc nào qua Serial)
    portENTER_CRITICAL(&paramMux);
    pid.kp = g.kp; pid.ki = g.ki; pid.kd = g.kd;
    float sp = g.sp, openDuty = g.openDuty;
    Mode mode = g.mode;
    bool rst = g.resetReq;
    g.resetReq = false;
    portEXIT_CRITICAL(&paramMux);
    if (rst) pid.reset();

    // 3. Tính u[k]
    float u = 0.0f;
    switch (mode) {
      case Mode::CLOSED: u = pid.compute(sp - rpm); break;
      case Mode::OPEN:   u = openDuty; pid.reset(); break;
      default:           u = 0.0f;     pid.reset(); break;
    }

    // 4. Xuất PWM và gửi mẫu cho loop() in ra (không in trực tiếp để tránh jitter)
    motorWrite(u);
    Sample s{millis(), sp, rpm, u};
    xQueueSend(sampleQueue, &s, 0);
  }
}

// ================= Serial =================
void printParams() {
  portENTER_CRITICAL(&paramMux);
  Shared p = g;
  portEXIT_CRITICAL(&paramMux);
  const char *m = p.mode == Mode::CLOSED ? "CLOSED" : p.mode == Mode::OPEN ? "OPEN" : "STOP";
  Serial.printf("# Kp=%.4f Ki=%.4f Kd=%.5f SP=%.1f open=%.1f mode=%s Ts=%lums CPR=%.0f\n",
                p.kp, p.ki, p.kd, p.sp, p.openDuty, m, (unsigned long)TS_MS, CPR);
}

void handleCommand(String line) {
  line.trim();
  if (line.isEmpty()) return;
  int sp1 = line.indexOf(' ');
  String cmd = (sp1 < 0) ? line : line.substring(0, sp1);
  String arg = (sp1 < 0) ? "" : line.substring(sp1 + 1);
  cmd.toLowerCase();
  float v = arg.toFloat();
  float a = 0, b = 0, c = 0;
  int nPid = sscanf(arg.c_str(), "%f %f %f", &a, &b, &c);

  portENTER_CRITICAL(&paramMux);
  bool ok = true;
  if      (cmd == "kp") g.kp = v;
  else if (cmd == "ki") g.ki = v;
  else if (cmd == "kd") g.kd = v;
  else if (cmd == "pid") {
    if (nPid == 3) { g.kp = a; g.ki = b; g.kd = c; }
    else ok = false;
  }
  else if (cmd == "sp")    { g.sp = v; g.mode = Mode::CLOSED; }
  else if (cmd == "open")  { g.openDuty = constrain(v, -U_MAX, U_MAX); g.mode = Mode::OPEN; }
  else if (cmd == "stop")  { g.mode = Mode::STOP; g.sp = 0; }
  else if (cmd == "reset") { g.resetReq = true; }
  else if (cmd == "rate")  { logDiv = max(1, (int)v); }
  else if (cmd != "?")     ok = false;
  portEXIT_CRITICAL(&paramMux);

  if (ok) printParams();
  else Serial.printf("# ERR unknown/invalid: %s\n", line.c_str());
}

void setup() {
  Serial.begin(115200);
  motorInit();
  motorWrite(0);

  pinMode(PIN_ENC_A, INPUT_PULLUP);
  pinMode(PIN_ENC_B, INPUT_PULLUP);
  encPrev = (digitalRead(PIN_ENC_A) << 1) | digitalRead(PIN_ENC_B);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_A), encoderISR, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_B), encoderISR, CHANGE);

  sampleQueue = xQueueCreate(64, sizeof(Sample));
  xTaskCreatePinnedToCore(controlTask, "ctrl", 4096, nullptr, configMAX_PRIORITIES - 2, nullptr, 1);

  Serial.println("# Lab3 PID ready");
  printParams();
}

void loop() {
  static uint32_t n = 0;
  static String rx;

  Sample s;
  while (xQueueReceive(sampleQueue, &s, 0) == pdTRUE) {
    if (++n % logDiv == 0)
      Serial.printf("D,%lu,%.1f,%.2f,%.2f\n", (unsigned long)s.t, s.sp, s.rpm, s.u);
  }

  while (Serial.available()) {
    char ch = (char)Serial.read();
    if (ch == '\n' || ch == '\r') {
      handleCommand(rx);
      rx = "";
    } else if (rx.length() < 64) {
      rx += ch;
    }
  }
  delay(1);
}
