import pandas as pd
import matplotlib.pyplot as plt

df = pd.read_csv("khiem.csv")

period = df["timestamp_us"].diff().dropna()

plt.figure(figsize=(10,5))
plt.hist(period, bins=30)

plt.xlabel("Sample Period (us)")
plt.ylabel("Count")
plt.title("Sampling Period Distribution")
plt.grid(True)

plt.savefig("khiem_jitter.png", dpi=300)
plt.show()