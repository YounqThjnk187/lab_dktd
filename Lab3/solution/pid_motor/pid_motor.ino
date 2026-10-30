/*
 * Lab 3: Discrete PID speed control for ESP32 + TB6612FNG + JGA25-370 encoder.
 * Encoder A/B use GPIO32/33; TB6612FNG STBY is tied to 3V3 externally.
 * Set ENC_PPR and GEAR_RATIO to match the motor before testing.
 */
#include <Arduino.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <esp_arduino_version.h>
#include <soc/gpio_reg.h>
#include <soc/soc.h>

constexpr uint8_t PIN_PWM = 25;
constexpr uint8_t PIN_IN1 = 26;
constexpr uint8_t PIN_IN2 = 27;
constexpr uint8_t PIN_ENC_A = 32;
constexpr uint8_t PIN_ENC_B = 33;
constexpr uint8_t GPIO_IN1_PIN_OFFSET = 32;

constexpr float ENC_PPR = 11.0f;
constexpr float GEAR_RATIO = 34.0f;
constexpr float QUADRATURE_MULTIPLIER = 4.0f;
constexpr float COUNTS_PER_OUTPUT_REV =
    ENC_PPR * GEAR_RATIO * QUADRATURE_MULTIPLIER;
constexpr int8_t ENCODER_DIRECTION = 1;

constexpr uint32_t SAMPLE_US = 10000;
constexpr float TS = SAMPLE_US / 1000000.0f;
constexpr float MAX_OUTPUT_PERCENT = 100.0f;
constexpr float SPEED_FILTER_ALPHA = 0.3f;
constexpr uint8_t PWM_RESOLUTION_BITS = 10;
constexpr uint16_t PWM_MAX = (1U << PWM_RESOLUTION_BITS) - 1;
constexpr uint16_t PWM_FREQUENCY_HZ = 20000;

constexpr int8_t QUADRATURE_TABLE[16] = {
    0, -1, 1, 0, 1, 0, 0, -1,
    -1, 0, 0, 1, 0, 1, -1, 0};

volatile int32_t encoderCount = 0;
volatile uint8_t previousEncoderState = 0;
portMUX_TYPE encoderMux = portMUX_INITIALIZER_UNLOCKED;

enum class ControlMode : uint8_t { Stop, OpenLoop, ClosedLoop };

struct Controller {
  float kp = 0.2f;
  float ki = 0.0f;
  float kd = 0.0f;
  float integral = 0.0f;
  float previousError = 0.0f;
  float setpointRpm = 0.0f;
  float openLoopPercent = 0.0f;
  float outputPercent = 0.0f;
  ControlMode mode = ControlMode::Stop;
  uint16_t logEvery = 1;
};

Controller controller;
uint32_t lastControlUs = 0;
uint32_t sampleNumber = 0;
char commandBuffer[96];
size_t commandLength = 0;

void IRAM_ATTR encoderISR() {
  // GPIO32-39 are in GPIO_IN1_REG, not GPIO_IN_REG (GPIO0-31).
  const uint32_t pins = REG_READ(GPIO_IN1_REG);
  const uint8_t state =
      (((pins >> (PIN_ENC_A - GPIO_IN1_PIN_OFFSET)) & 1U) << 1) |
      ((pins >> (PIN_ENC_B - GPIO_IN1_PIN_OFFSET)) & 1U);

  portENTER_CRITICAL_ISR(&encoderMux);
  const uint8_t index = (previousEncoderState << 2) | state;
  encoderCount += QUADRATURE_TABLE[index];
  previousEncoderState = state;
  portEXIT_CRITICAL_ISR(&encoderMux);
}

int32_t readEncoderCount() {
  portENTER_CRITICAL(&encoderMux);
  const int32_t count = encoderCount;
  portEXIT_CRITICAL(&encoderMux);
  return count;
}

void writeMotor(float outputPercent) {
  outputPercent = constrain(outputPercent, -MAX_OUTPUT_PERCENT,
                            MAX_OUTPUT_PERCENT);
  digitalWrite(PIN_IN1, outputPercent >= 0.0f ? HIGH : LOW);
  digitalWrite(PIN_IN2, outputPercent >= 0.0f ? LOW : HIGH);
  const uint16_t duty = static_cast<uint16_t>(
      fabsf(outputPercent) * PWM_MAX / MAX_OUTPUT_PERCENT);
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcWrite(PIN_PWM, duty);
#else
  ledcWrite(0, duty);
#endif
}

float updatePid(float error) {
  const float candidateIntegral = controller.integral + error;
  float output = controller.kp * error +
                 controller.ki * TS * candidateIntegral +
                 controller.kd * (error - controller.previousError) / TS;
  const bool saturatedHigh = output > MAX_OUTPUT_PERCENT;
  const bool saturatedLow = output < -MAX_OUTPUT_PERCENT;
  output = constrain(output, -MAX_OUTPUT_PERCENT, MAX_OUTPUT_PERCENT);

  // Conditional integration prevents the integral term winding up at the limits.
  if ((!saturatedHigh && !saturatedLow) ||
      (saturatedHigh && error < 0.0f) ||
      (saturatedLow && error > 0.0f)) {
    controller.integral = candidateIntegral;
  }
  controller.previousError = error;
  return output;
}

void resetPid() {
  controller.integral = 0.0f;
  controller.previousError = 0.0f;
}

bool parseFloat(const char *text, float &value) {
  char *end = nullptr;
  value = strtof(text, &end);
  return end != text && *end == '\0' && isfinite(value);
}

void printParameters() {
  const char *mode = controller.mode == ControlMode::ClosedLoop
                         ? "CLOSED"
                         : controller.mode == ControlMode::OpenLoop ? "OPEN"
                                                                     : "STOP";
  Serial.printf("# Kp=%.4f Ki=%.4f Kd=%.5f SP=%.2f open=%.1f "
                "mode=%s Ts=%luus CPR=%.0f\n",
                controller.kp, controller.ki, controller.kd,
                controller.setpointRpm, controller.openLoopPercent, mode,
                static_cast<unsigned long>(SAMPLE_US),
                COUNTS_PER_OUTPUT_REV);
}

void handleCommand(char *line) {
  char command[8] = {};
  char first[24] = {};
  char second[24] = {};
  char third[24] = {};
  char extra[8] = {};
  const int count =
      sscanf(line, "%7s %23s %23s %23s %7s", command, first, second, third,
             extra);
  if (count < 1) return;

  for (char *p = command; *p; ++p) {
    if (*p >= 'A' && *p <= 'Z') *p = static_cast<char>(*p - 'A' + 'a');
  }

  float a = 0.0f, b = 0.0f, c = 0.0f;
  if (strcmp(command, "pid") == 0) {
    if (count != 4 || !parseFloat(first, a) || !parseFloat(second, b) ||
        !parseFloat(third, c) || a < 0.0f || b < 0.0f || c < 0.0f) {
      Serial.println("# ERR usage: pid <Kp>=0 <Ki>=0 <Kd>=0");
      return;
    }
    controller.kp = a;
    controller.ki = b;
    controller.kd = c;
  } else if (strcmp(command, "kp") == 0 || strcmp(command, "ki") == 0 ||
             strcmp(command, "kd") == 0 || strcmp(command, "sp") == 0 ||
             strcmp(command, "open") == 0) {
    if (count != 2 || !parseFloat(first, a)) {
      Serial.println("# ERR command requires one finite number");
      return;
    }
    if (strcmp(command, "kp") == 0 || strcmp(command, "ki") == 0 ||
        strcmp(command, "kd") == 0) {
      if (a < 0.0f) {
        Serial.println("# ERR PID gains must be non-negative");
        return;
      }
      if (command[1] == 'p') controller.kp = a;
      if (command[1] == 'i') controller.ki = a;
      if (command[1] == 'd') controller.kd = a;
    } else if (strcmp(command, "sp") == 0) {
      controller.setpointRpm = a;
      controller.mode = ControlMode::ClosedLoop;
    } else {
      if (fabsf(a) > MAX_OUTPUT_PERCENT) {
        Serial.println("# ERR open-loop duty must be between -100 and 100");
        return;
      }
      controller.openLoopPercent = a;
      controller.mode = ControlMode::OpenLoop;
      resetPid();
    }
  } else if (strcmp(command, "stop") == 0 && count == 1) {
    controller.mode = ControlMode::Stop;
    controller.setpointRpm = 0.0f;
    resetPid();
  } else if (strcmp(command, "reset") == 0 && count == 1) {
    resetPid();
  } else if (strcmp(command, "rate") == 0 && count == 2) {
    char *end = nullptr;
    const long rate = strtol(first, &end, 10);
    if (end == first || *end != '\0' || rate < 1 || rate > 100) {
      Serial.println("# ERR rate must be an integer from 1 to 100");
      return;
    }
    controller.logEvery = static_cast<uint16_t>(rate);
  } else if (strcmp(command, "?") == 0 && count == 1) {
    printParameters();
    return;
  } else {
    Serial.println("# ERR commands: kp, ki, kd, pid, sp, open, stop, reset, rate, ?");
    return;
  }
  printParameters();
}

void readSerialCommands() {
  while (Serial.available() > 0) {
    const char ch = static_cast<char>(Serial.read());
    if (ch == '\n' || ch == '\r') {
      if (commandLength > 0) {
        commandBuffer[commandLength] = '\0';
        handleCommand(commandBuffer);
        commandLength = 0;
      }
    } else if (commandLength + 1 < sizeof(commandBuffer)) {
      commandBuffer[commandLength++] = ch;
    } else {
      commandLength = 0;
      Serial.println("# ERR command too long");
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(PIN_IN1, OUTPUT);
  pinMode(PIN_IN2, OUTPUT);
#if ESP_ARDUINO_VERSION_MAJOR >= 3
  ledcAttach(PIN_PWM, PWM_FREQUENCY_HZ, PWM_RESOLUTION_BITS);
#else
  ledcSetup(0, PWM_FREQUENCY_HZ, PWM_RESOLUTION_BITS);
  ledcAttachPin(PIN_PWM, 0);
#endif
  writeMotor(0.0f);

  pinMode(PIN_ENC_A, INPUT_PULLUP);
  pinMode(PIN_ENC_B, INPUT_PULLUP);
  previousEncoderState =
      (digitalRead(PIN_ENC_A) << 1) | digitalRead(PIN_ENC_B);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_A), encoderISR, CHANGE);
  attachInterrupt(digitalPinToInterrupt(PIN_ENC_B), encoderISR, CHANGE);

  lastControlUs = micros();
  Serial.println("# Lab3 PID ready; CSV: D,t_ms,sp_rpm,rpm,u_percent");
  printParameters();
}

void loop() {
  readSerialCommands();

  const uint32_t nowUs = micros();
  const uint32_t elapsedUs = nowUs - lastControlUs;
  if (elapsedUs < SAMPLE_US) return;
  lastControlUs += SAMPLE_US;
  if (elapsedUs >= 2 * SAMPLE_US) {
    lastControlUs = nowUs;
    if (Serial.availableForWrite() >= 48) {
      Serial.println("# WARN control loop missed a sample");
    }
  }

  const int32_t count = readEncoderCount();
  static int32_t previousCount = count;
  const int32_t deltaCount = count - previousCount;
  previousCount = count;

  const float elapsedSeconds = elapsedUs / 1000000.0f;
  const float measuredRpm =
      ENCODER_DIRECTION * (deltaCount / COUNTS_PER_OUTPUT_REV) /
      elapsedSeconds * 60.0f;
  static float filteredRpm = 0.0f;
  filteredRpm += SPEED_FILTER_ALPHA * (measuredRpm - filteredRpm);

  switch (controller.mode) {
    case ControlMode::ClosedLoop:
      controller.outputPercent =
          updatePid(controller.setpointRpm - filteredRpm);
      break;
    case ControlMode::OpenLoop:
      controller.outputPercent = controller.openLoopPercent;
      break;
    case ControlMode::Stop:
      controller.outputPercent = 0.0f;
      break;
  }
  writeMotor(controller.outputPercent);

  if (++sampleNumber % controller.logEvery == 0 &&
      Serial.availableForWrite() >= 80) {
    Serial.printf("D,%lu,%.2f,%.2f,%.2f\n",
                  static_cast<unsigned long>(millis()),
                  controller.setpointRpm, filteredRpm,
                  controller.outputPercent);
  }
}
