#define LDR_PIN 15 

// Bộ lọc Moving Average làm mịn tín hiệu Analog
const int WINDOW_SIZE = 10;
int window[WINDOW_SIZE];
int windowIndex = 0;
long windowSum = 0;

void setup() {
  Serial.begin(115200);
  analogReadResolution(12); // Độ phân giải ADC 12-bit (0 - 4095)
  for (int i = 0; i < WINDOW_SIZE; i++) window[i] = 0;
  Serial.println("--- DEMO GIAO TIẾP ANALOG (LDR ADC) ---");
}

void loop() {
  int rawLDR = analogRead(LDR_PIN); // Đọc tín hiệu Analog thô

  // Lọc Moving Average
  windowSum -= window[windowIndex];
  window[windowIndex] = rawLDR;
  windowSum += window[windowIndex];
  windowIndex = (windowIndex + 1) % WINDOW_SIZE;
  int filteredLDR = windowSum / WINDOW_SIZE;

  // In ra Serial Plotter
  Serial.print("LDR_Raw:");
  Serial.print(rawLDR);
  Serial.print(",LDR_Filtered:");
  Serial.println(filteredLDR);

  delay(20); // Lấy mẫu 50Hz
}