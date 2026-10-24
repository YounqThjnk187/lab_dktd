#include <Arduino.h>

// Định nghĩa chân phần cứng
const int encA = 32;   // Chân Encoder A
const int encB = 33;   // Chân Encoder B
const int pwmPin = 25; // Chân PWM điều khiển tốc độ động cơ (TB6612 PWMA)
const int in1 = 26;    // Chiều quay 1
const int in2 = 27;    // Chiều quay 2

// Biến đếm encoder và vận tốc
volatile long encoderTicks = 0;
float currentSpeed = 0; // đơn vị: vòng/phút (RPM) hoặc tick/s
float targetSpeed = 150; // Tốc độ đặt mong muốn

// Thông số PID
float Kp = 1.2;
float Ki = 0.5;
float Kd = 0.01;

// Biến lưu trữ trạng thái PID rời rạc
float Ts = 0.01; // Chu kỳ lấy mẫu 10ms = 0.01s
float error = 0, lastError = 0, integral = 0, derivative = 0;
float output = 0;

// Biến định thời 10ms dùng millis() hoặc Timer phần cứng
unsigned long lastTime = 0;

void IRAM_ATTR handleEncoder() {
  // Đọc xung kênh B để xác định chiều
  if (digitalRead(encB) == HIGH) {
    encoderTicks++;
  } else {
    encoderTicks--;
  }
}

void setup() {
  Serial.begin(115200);

  pinMode(encA, INPUT_PULLUP);
  pinMode(encB, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(encA), handleEncoder, RISING);

  pinMode(pwmPin, OUTPUT);
  pinMode(in1, OUTPUT);
  pinMode(in2, OUTPUT);

  // Quay một chiều cố định
  digitalWrite(in1, HIGH);
  digitalWrite(in2, LOW);

  // Cấu hình kênh PWM cho ESP32
  ledcAttach(pwmPin, 5000, 8); // Tần số 5kHz, độ phân giải 8-bit (0-255)
  
  Serial.println("Khoi động hệ thống PID Vận Tốc DC Motor...");
}

void parseSerialCommand() {
  if (Serial.available() > 0) {
    String input = Serial.readStringUntil('\n');
    input.trim();
    if (input.startsWith("P")) {
      Kp = input.substring(1).toFloat();
    } else if (input.startsWith("I")) {
      Ki = input.substring(1).toFloat();
    } else if (input.startsWith("D")) {
      Kd = input.substring(1).toFloat();
    } else if (input.startsWith("S")) {
      targetSpeed = input.substring(1).toFloat();
    }
    Serial.printf("Updated -> Kp: %.2f, Ki: %.2f, Kd: %.2f, Target: %.2f\n", Kp, Ki, Kd, targetSpeed);
  }
}

void loop() {
  // Nhận lệnh thay đổi tham số từ Serial (nếu có)
  parseSerialCommand();

  // Thực thi vòng lặp PID đúng chu kỳ Ts = 10ms
  if (millis() - lastTime >= 10) {
    lastTime = millis();

    // 1. Tính vận tốc thực tế (tick trong 10ms quy đổi ra đơn vị tương ứng)
    noInterrupts();
    long ticks = encoderTicks;
    encoderTicks = 0;
    interrupts();

    currentSpeed = (ticks / Ts); // Tốc độ theo tick/s

    // 2. Tính toán PID rời rạc
    // Phương trình: u[k] = Kp*e[k] + Ki*Ts*Σe[k] + Kd*(e[k]-e[k-1])/Ts
    error = targetSpeed - currentSpeed;
    integral += error * Ts;
    // Chống bão hòa tích phân (Anti-windup cơ bản)
    if (integral > 255) integral = 255;
    if (integral < -255) integral = -255;

    derivative = (error - lastError) / Ts;

    output = (Kp * error) + (Ki * integral) + (Kd * derivative);
    lastError = error;

    // Giới hạn PWM ngõ ra từ 0 đến 255
    int pwmOut = constrain((int)output, 0, 255);
    ledcWrite(pwmPin, pwmOut);

    // 3. Gửi dữ liệu qua Serial để Python vẽ đồ thị (Format: Target, Current, PWM)
    Serial.print("Target:"); Serial.print(targetSpeed);
    Serial.print(",Current:"); Serial.print(currentSpeed);
    Serial.print(",PWM:"); Serial.println(pwmOut);
  }
}