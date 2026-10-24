#define ADC_PIN 34

hw_timer_t *timer = NULL;
volatile bool sampleFlag = false;
volatile unsigned long sampleCount = 0;

void ARDUINO_ISR_ATTR onTimer()
{
    sampleFlag = true;
    sampleCount++;
}

void setup()
{
    Serial.begin(115200);

    analogReadResolution(12);

    // Timer tick = 1 us
    timer = timerBegin(1000000);

    timerAttachInterrupt(timer, &onTimer);

    // 100 Hz = 10 ms
    timerAlarm(timer, 10000, true, 0);
}

void loop()
{
    if(sampleFlag)
    {
        sampleFlag = false;

        int adcValue = analogRead(ADC_PIN);

        unsigned long timestamp = micros();

        Serial.print(timestamp);
        Serial.print(",");

        Serial.print(sampleCount);
        Serial.print(",");

        Serial.println(adcValue);
    }
}