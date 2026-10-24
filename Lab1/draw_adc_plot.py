import pandas as pd
import matplotlib.pyplot as plt
import numpy as np

filename = "khiem.csv"     

df = pd.read_csv(filename)

# Đổi thời gian về giây
time_s = df["timestamp_us"] / 1e6

# Tính chu kỳ thực tế
period = df["timestamp_us"].diff().dropna()

mean_period = period.mean()
jitter = period.std()

print("===== KET QUA =====")
print(f"Chu ky TB : {mean_period:.2f} us")
print(f"Jitter    : {jitter:.2f} us")

plt.figure(figsize=(12,6))
plt.plot(time_s, df["adc"], linewidth=1)

plt.title(
    f"ADC Signal\nMean Period={mean_period:.2f} us | Jitter={jitter:.2f} us"
)

plt.xlabel("Time (s)")
plt.ylabel("ADC Value")
plt.grid(True)

plt.tight_layout()
plt.savefig("khiem_plot.png", dpi=300)
plt.show()