import serial
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime

PORT = "COM6"     
BAUD = 115200

ser = serial.Serial(PORT, BAUD)

data = []

print("Dang thu du lieu...")

try:
    while len(data) < 2000:      # lấy 20 giây
        line = ser.readline().decode().strip()

        try:
            t, n, adc = line.split(',')

            data.append([
                int(t),
                int(n),
                int(adc)
            ])

        except:
            pass

except KeyboardInterrupt:
    pass

ser.close()

df = pd.DataFrame(
    data,
    columns=["timestamp_us",
             "sample",
             "adc"]
)

filename = "dthinh.csv"

df.to_csv(filename, index=False)

print("Da luu:", filename)

plt.figure(figsize=(10,5))
plt.plot(df["timestamp_us"]/1e6,
         df["adc"])

plt.xlabel("Time (s)")
plt.ylabel("ADC")
plt.title("ADC Signal")
plt.grid(True)
plt.show()

period = df["timestamp_us"].diff()

period = period.dropna()

mean_period = period.mean()

jitter = period.std()

print()
print("===== KET QUA =====")
print(f"Chu ky trung binh = {mean_period:.2f} us")
print(f"Jitter (std) = {jitter:.2f} us")