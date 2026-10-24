"""Live-plot + chỉnh Kp/Ki/Kd runtime qua Serial cho Lab 3.

Chạy:  python monitor.py --port COM5 --out data/run1.csv
Gõ lệnh vào terminal rồi Enter (kp 1.2, ki 10, sp 150, open 40, stop, ?...).
Lệnh 'mark <ghi chú>' không gửi xuống ESP32, chỉ gắn nhãn sự kiện vào CSV (vd: mark load).
Đóng cửa sổ đồ thị để dừng động cơ và lưu CSV.
"""
import argparse
import csv
import sys
import threading
import time
from collections import deque
from pathlib import Path

import matplotlib.pyplot as plt
import serial
from matplotlib.animation import FuncAnimation


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", required=True)
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--window", type=float, default=10.0, help="số giây hiển thị")
    ap.add_argument("--out", default=f"data/run_{time.strftime('%Y%m%d_%H%M%S')}.csv")
    args = ap.parse_args()

    ser = serial.Serial(args.port, args.baud, timeout=0.1)
    maxlen = int(args.window * 100) + 10
    buf = {k: deque(maxlen=maxlen) for k in ("t", "sp", "rpm", "u")}
    rows = []
    lock = threading.Lock()
    stop = threading.Event()
    state = {"t0": None, "pending": "", "t_last": 0.0}

    def reader():
        while not stop.is_set():
            line = ser.readline().decode(errors="ignore").strip()
            if not line:
                continue
            if not line.startswith("D,"):
                print(line)
                continue
            try:
                _, t_ms, sp, rpm, u = line.split(",")
                t_ms, sp, rpm, u = int(t_ms), float(sp), float(rpm), float(u)
            except ValueError:
                continue
            with lock:
                if state["t0"] is None:
                    state["t0"] = t_ms
                t = (t_ms - state["t0"]) / 1000.0
                state["t_last"] = t
                for k, v in zip(("t", "sp", "rpm", "u"), (t, sp, rpm, u)):
                    buf[k].append(v)
                rows.append((t, sp, rpm, u, state["pending"]))
                state["pending"] = ""

    def writer():
        for line in sys.stdin:
            cmd = line.strip()
            if not cmd:
                continue
            if not cmd.lower().startswith("mark"):
                ser.write((cmd + "\n").encode())
            with lock:
                state["pending"] = (state["pending"] + ";" + cmd).strip(";")
            print(f"> {cmd} @ t={state['t_last']:.2f}s")

    threading.Thread(target=reader, daemon=True).start()
    threading.Thread(target=writer, daemon=True).start()

    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(10, 6))
    (l_sp,) = ax1.plot([], [], "r--", label="Setpoint")
    (l_rpm,) = ax1.plot([], [], "b-", label="Vận tốc")
    (l_u,) = ax2.plot([], [], "g-", label="u (%)")
    ax1.set_ylabel("rpm")
    ax2.set_ylabel("u [%]")
    ax2.set_xlabel("t [s]")
    ax2.set_ylim(-105, 105)
    for ax in (ax1, ax2):
        ax.grid(True)
        ax.legend(loc="upper left")

    def update(_):
        with lock:
            t, sp, rpm, u = (list(buf[k]) for k in ("t", "sp", "rpm", "u"))
        if not t:
            return l_sp, l_rpm, l_u
        l_sp.set_data(t, sp)
        l_rpm.set_data(t, rpm)
        l_u.set_data(t, u)
        ax1.set_xlim(max(0.0, t[-1] - args.window), max(args.window, t[-1]))
        ax1.relim()
        ax1.autoscale_view(scalex=False)
        return l_sp, l_rpm, l_u

    _anim = FuncAnimation(fig, update, interval=50, cache_frame_data=False)
    plt.tight_layout()
    plt.show()

    stop.set()
    ser.write(b"stop\n")
    time.sleep(0.2)
    ser.close()

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t", "sp", "rpm", "u", "event"])
        w.writerows(rows)
    print(f"Đã lưu {len(rows)} mẫu vào {out}")


if __name__ == "__main__":
    main()
