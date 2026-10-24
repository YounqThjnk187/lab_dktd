#include <OneWire.h>
#include <DallasTemperature.h>

#define ONE_WIRE_BUS 15 // GPIO 4

OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);

void setup() {
  Serial.begin(115200);
  sensors.begin();
  Serial.println("--- DEMO GIAO TIẾP 1-WIRE (DS18B20) ---");
}

void loop() {
  sensors.requestTemperatures(); 
  float tempC = sensors.getTempCByIndex(0);

  if (tempC != DEVICE_DISCONNECTED_C) {
    Serial.print("Nhiet do DS18B20: ");
    Serial.print(tempC);
    Serial.println(" °C");
  } else {
    Serial.println("Loi: Khong tim thay cam bien DS18B20!");
  }

  delay(1000); // Đọc định kỳ 1 giây/lần
}