#include <Wire.h>
#include <MPU6050_light.h>
#include "esp32-hal-timer.h"

#define SDA_PIN 21
#define SCL_PIN 22

MPU6050 mpu(Wire);

// --- BỘ LỌC MOVING AVERAGE (N = 10) ---
const int WINDOW_SIZE = 10;
float window[WINDOW_SIZE];
int windowIndex = 0;
float windowSum = 0;

// --- BỘ LỌC COMPLEMENTARY (alpha = 0.96) ---
float angleCompX = 0;
const float alpha = 0.96;
const float dt = 0.01; // 10ms = 100Hz

// --- NGẮT TIMER (100Hz) ---
hw_timer_t * timer = NULL;
volatile bool sampleFlag = false;

void IRAM_ATTR onTimer() {
  sampleFlag = true;
}

void setup() {
  Serial.begin(115200);
  Wire.begin(SDA_PIN, SCL_PIN);

  byte status = mpu.begin();
  if (status != 0) {
    Serial.println("Loi: Khong tim thay MPU6050!");
    while (1);
  }

  // Hiệu chỉnh offset (Giữ MPU6050 đứng yên trong 2 giây)
  Serial.println("Dang hieu chinh Offset (Giu nguyen cam bien)...");
  delay(1000);
  mpu.calcOffsets();
  Serial.println("Hieu chinh xong!");

  for (int i = 0; i < WINDOW_SIZE; i++) window[i] = 0;

  // Cấu hình Ngắt Timer 100Hz
  timer = timerBegin(1000000);
  timerAttachInterrupt(timer, &onTimer);
  timerAlarm(timer, 10000, true, 0);
}

void loop() {
  if (sampleFlag) {
    sampleFlag = false;
    mpu.update();

    // 1. Góc thô Gia tốc (Raw Accel Angle)
    float accX = mpu.getAccX();
    float accY = mpu.getAccY();
    float accZ = mpu.getAccZ();
    float angleRawX = atan2(accY, sqrt(accX * accX + accZ * accZ)) * 180.0 / PI;

    // 2. Bộ lọc Moving Average
    windowSum -= window[windowIndex];
    window[windowIndex] = angleRawX;
    windowSum += window[windowIndex];
    windowIndex = (windowIndex + 1) % WINDOW_SIZE;
    float angleMA = windowSum / WINDOW_SIZE;

    // 3. Bộ lọc Complementary Filter
    float gyroX = mpu.getGyroX();
    angleCompX = alpha * (angleCompX + gyroX * dt) + (1.0 - alpha) * angleRawX;

    // In theo định dạng gắn nhãn rõ ràng cho Serial Plotter & Python
    Serial.print("Raw:");
    Serial.print(angleRawX);
    Serial.print(",MA:");
    Serial.print(angleMA);
    Serial.print(",Comp:");
    Serial.println(angleCompX);
  }
}