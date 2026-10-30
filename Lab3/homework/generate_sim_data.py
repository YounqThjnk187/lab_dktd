"""Sinh bộ CSV MÔ PHỎNG (không phải đo thật) để chạy thử analyze_response.py và ziegler_nichols.py
khi chưa có phần cứng.

Mô phỏng bám sát firmware/pid_motor/pid_motor.ino:
  - Ts = 10 ms, encoder x4 (CPR = 11*34*4) -> lượng tử hóa vận tốc ~4 rpm/mẫu, lọc EMA alpha = 0.3
  - PID rời rạc u[k] = Kp·e + Ki·Ts·Σe + Kd·Δe/Ts, anti-windup có điều kiện, u ∈ [-100, 100] %
  - u[k] được áp dụng trong chu kỳ kế tiếp (đúng thứ tự đo -> tính -> xuất PWM)
Đối tượng: JGA25-370 1:34 @12V giả định (~330 rpm không tải), vùng chết ~6 %, 2 hằng số thời gian.
CSV có cùng định dạng monitor.py ghi: t,sp,rpm,u,event (event = lệnh đã gõ, vd 'mark load').

    python generate_sim_data.py                # ghi vào ../data_sim/
"""
import argparse
import csv
from pathlib import Path

import numpy as np

# ---- giống firmware
TS = 0.010
CPR = 11 * 34 * 4
RPM_ALPHA = 0.3
U_MAX = 100.0

# ---- đối tượng giả định
K_PLANT = 3.5      # rpm / % duty (sau vùng chết)
DEADZONE = 6.0     # % duty chưa thắng ma sát tĩnh
TAU_M = 0.12       # s, cơ
TAU_E = 0.015      # s, điện + driver
SUBSTEPS = 10
NOISE_RPM = 3.0    # nhiễu mô-men quy đổi (rpm)
LOAD_RPM = 70.0    # tải cản trục quy đổi (rpm sụt ở vòng hở)


class Motor:
    def __init__(self, rng, noise=True):
        self.w = self.xe = self.pos = 0.0
        self.prev_cnt = 0
        self.rpm = 0.0
        self.rng, self.noise = rng, noise

    def step(self, u, load):
        """Áp u trong 1 chu kỳ Ts rồi trả về rpm đã lọc như firmware."""
        dt = TS / SUBSTEPS
        drive = K_PLANT * np.sign(u) * max(abs(u) - DEADZONE, 0.0)
        for _ in range(SUBSTEPS):
            n = self.rng.normal(0, NOISE_RPM) if self.noise and abs(self.w) > 1 else 0.0
            self.xe += dt * (drive - self.xe) / TAU_E
            ld = load * np.sign(self.w) if abs(self.w) > 1 else 0.0
            self.w += dt * (self.xe - self.w - ld + n) / TAU_M
            self.pos += self.w / 60.0 * CPR * dt
        if self.noise:
            cnt = int(np.floor(self.pos))
            dc, self.prev_cnt = cnt - self.prev_cnt, cnt
            raw = dc / CPR / TS * 60.0
        else:  # đo lý tưởng, dùng khi dò Ku
            raw = self.w
        self.rpm += RPM_ALPHA * (raw - self.rpm)
        return self.rpm


class PID:
    def __init__(self, kp, ki, kd):
        self.kp, self.ki, self.kd = kp, ki, kd
        self.sum = self.prev = 0.0

    def compute(self, e):
        s = self.sum + e
        u = self.kp * e + self.ki * TS * s + self.kd * (e - self.prev) / TS
        if u > U_MAX:
            u = U_MAX
            if e < 0:
                self.sum = s
        elif u < -U_MAX:
            u = -U_MAX
            if e > 0:
                self.sum = s
        else:
            self.sum = s
        self.prev = e
        return u


def run(duration, script, gains=(0, 0, 0), load=(), seed=0, noise=True):
    """script: {t: (mode, value, event)} với mode 'sp' (vòng kín) hoặc 'open' (vòng hở).
    load: [(t_on, t_off, t_mark)] — t_mark là lúc người gõ 'mark load' (trễ hơn tải thật)."""
    rng = np.random.default_rng(seed)
    m, pid = Motor(rng, noise), PID(*gains)
    mode, sp, duty, u = "stop", 0.0, 0.0, 0.0
    rows, pending = [], []
    events = sorted(script.items())
    marks = sorted((tm, "mark load") for _, _, tm in load)
    for k in range(int(round(duration / TS))):
        t = k * TS
        ld = LOAD_RPM if any(a <= t < b for a, b, _ in load) else 0.0
        rpm = m.step(u, ld)  # u của chu kỳ trước được áp trong khoảng vừa qua
        while events and events[0][0] <= t + 1e-9:
            _, (md, val, ev) = events.pop(0)
            if md == "sp":
                if mode != "closed":
                    pid.sum = pid.prev = 0.0
                mode, sp = "closed", val
            elif md == "open":
                mode, duty = "open", val
            if ev:
                pending.append(ev)
        while marks and marks[0][0] <= t + 1e-9:
            pending.append(marks.pop(0)[1])
        if mode == "closed":
            u = pid.compute(sp - rpm)
        elif mode == "open":
            u, pid.sum, pid.prev = duty, 0.0, 0.0
        else:
            u = 0.0
        rows.append((round(t, 3), round(sp if mode == "closed" else 0.0, 1),
                     round(rpm, 2), round(u, 2), ";".join(pending)))
        pending = []
    return rows


def write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["t", "sp", "rpm", "u", "event"])
        w.writerows(rows)
    print(f"  {path.name:16s} {len(rows)} mẫu")


def osc_growth(kp):
    """Tỉ số biên độ dao động cuối/đầu với điều khiển P (không nhiễu, không bão hòa đáng kể)."""
    rows = run(8.0, {0.0: ("sp", 60.0, "")}, (kp, 0, 0), noise=False)
    y = np.array([r[2] for r in rows])
    a1, a2 = np.ptp(y[200:400]), np.ptp(y[600:800])
    return 0.0 if a1 < 0.5 else a2 / a1


def find_ku():
    lo, hi = 0.1, 20.0
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        lo, hi = (mid, hi) if osc_growth(mid) < 1.0 else (lo, mid)
    return hi


def steps(gains_txt):
    return {0.0: ("stop", 0, gains_txt),
            0.5: ("sp", 150.0, "sp 150"),
            4.0: ("sp", 220.0, "sp 220"),
            7.0: ("sp", 100.0, "sp 100")}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out-dir", type=Path, default=Path(__file__).resolve().parent.parent / "data_sim")
    a = ap.parse_args()
    out = a.out_dir

    ku = round(find_ku() * 1.02, 2)
    print(f"Ku (mô phỏng) ≈ {ku}")

    tunings = {
        "p":     (0.8, 0.0, 0.0),
        "pi":    (0.5, 6.0, 0.0),
        "zn":    (0.82, 8.2, 0.02),   # ZN vòng hở từ zn_open.csv, chưa chỉnh
        "pid":   (0.5, 4.0, 0.006),   # sau khi thử-sai từ bộ ZN
    }
    print(f"Ghi vào {out}:")
    # 1) Vòng hở cho ZN đường cong phản ứng: open 30 -> open 60
    write(out / "zn_open.csv", run(6.0, {0.5: ("open", 30.0, "open 30"),
                                        3.0: ("open", 60.0, "open 60")}, seed=1))
    # 2) Vòng kín chỉ P tại Ku -> dao động duy trì
    write(out / "zn_osc.csv", run(8.0, {0.0: ("stop", 0, f"pid {ku} 0 0"),
                                       0.5: ("sp", 150.0, "sp 150")}, (ku, 0, 0), seed=2))
    # 3) Đáp ứng bước với các bộ thông số (thử-sai có hệ thống)
    for i, (name, g) in enumerate(tunings.items()):
        write(out / f"step_{name}.csv", run(10.0, steps(f"pid {g[0]} {g[1]} {g[2]}"), g, seed=10 + i))
    # 4) Tải đột ngột: cản trục từ 5.0 s đến 10.5 s, người gõ 'mark load' trễ 0.25 s
    g = tunings["pid"]
    write(out / "load_pid.csv", run(12.0, {0.0: ("stop", 0, f"pid {g[0]} {g[1]} {g[2]}"),
                                          0.5: ("sp", 150.0, "sp 150")}, g,
                                   load=[(5.0, 10.5, 5.25)], seed=20))
    print("LƯU Ý: dữ liệu MÔ PHỎNG, không phải số đo phần cứng.")


if __name__ == "__main__":
    main()
