"""[BÀI VỀ NHÀ] Phân tích đáp ứng từ CSV do monitor.py ghi (cột: t,sp,rpm,u,event).

Đáp ứng bước (độ vọt lố, thời gian lên, thời gian xác lập, sai số xác lập):
    python analyze_response.py step ../data/run1.csv --index 0 --band 0.05
Đáp ứng với tải đột ngột (dùng nhãn 'mark load' đã gõ trong monitor.py):
    python analyze_response.py disturbance ../data/run2.csv --mark load --post 4

Kết quả: in một dòng bảng Markdown để dán vào báo cáo + lưu đồ thị PNG cạnh file CSV.
"""
import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def load(path):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    col = lambda k: np.array([float(r[k]) for r in rows])
    return col("t"), col("sp"), col("rpm"), col("u"), [r["event"] for r in rows]


def smooth(y, n):
    if n <= 1:
        return y
    return np.convolve(y, np.ones(n) / n, mode="same")


# ---------------------------------------------------------------- step
def step_metrics(t, y, r, y0, band):
    """t tính từ thời điểm đổi SP; r: SP mới; y0: giá trị trước bước; band: dải xác lập (tỉ lệ)."""
    dy = r - y0
    yn = (y - y0) / dy  # chuẩn hóa 0 -> 1

    i_peak = int(np.argmax(yn))
    mp = max(0.0, (yn[i_peak] - 1.0) * 100.0)

    def first_cross(level):
        idx = np.flatnonzero(yn >= level)
        return t[idx[0]] if idx.size else np.nan

    tr = first_cross(0.9) - first_cross(0.1)

    outside = np.flatnonzero(np.abs(y - r) > band * abs(dy))
    if outside.size == 0:
        ts = 0.0
    elif outside[-1] + 1 < len(t):
        ts = t[outside[-1] + 1]
    else:
        ts = np.nan  # chưa xác lập trong đoạn dữ liệu

    tail = y[int(0.8 * len(y)):]  # 20% cuối đoạn coi là xác lập
    ess = r - tail.mean()
    return dict(Mp=mp, tr=tr, ts=ts, ess=ess, ess_pct=abs(ess) / abs(r) * 100 if r else np.nan,
                t_peak=t[i_peak], y_peak=y[i_peak])


def cmd_step(a):
    t, sp, rpm, u, _ = load(a.csv)
    y_all = smooth(rpm, a.smooth)
    steps = np.flatnonzero(np.diff(sp) != 0) + 1
    if steps.size == 0:
        raise SystemExit("Không tìm thấy bước thay đổi setpoint trong file.")
    i0 = steps[a.index]
    i1 = steps[a.index + 1] if a.index + 1 < steps.size else len(t)

    tt = t[i0:i1] - t[i0]
    y = y_all[i0:i1]
    r = sp[i0]
    y0 = y_all[max(0, i0 - 10):i0].mean() if i0 > 0 else 0.0
    m = step_metrics(tt, y, r, y0, a.band)

    print(f"Bước #{a.index}: {y0:.1f} -> {r:.1f} rpm  (dải xác lập ±{a.band*100:.0f}%)")
    print("| Kp | Ki | Kd | Mp (%) | tr (s) | ts (s) | ess (rpm) | ess (%) |")
    print("|---|---|---|---|---|---|---|---|")
    print(f"| {a.kp} | {a.ki} | {a.kd} | {m['Mp']:.1f} | {m['tr']:.3f} | {m['ts']:.3f} "
          f"| {m['ess']:.2f} | {m['ess_pct']:.2f} |")

    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(9, 6))
    ax1.plot(tt, np.full_like(tt, r), "r--", label="Setpoint")
    ax1.plot(tt, y, "b", label="Vận tốc")
    ax1.axhspan(r - a.band * abs(r - y0), r + a.band * abs(r - y0), color="g", alpha=0.15,
                label=f"±{a.band*100:.0f}%")
    ax1.plot(m["t_peak"], m["y_peak"], "ko")
    if not np.isnan(m["ts"]):
        ax1.axvline(m["ts"], color="k", ls=":", label=f"ts={m['ts']:.2f}s")
    ax1.set_title(f"Kp={a.kp} Ki={a.ki} Kd={a.kd} | Mp={m['Mp']:.1f}%  ess={m['ess']:.2f} rpm")
    ax1.set_ylabel("rpm")
    ax2.plot(tt, u[i0:i1], "g")
    ax2.set_ylabel("PWM (0–255)")
    ax2.set_xlabel("t [s]")
    for ax in (ax1, ax2):
        ax.grid(True)
    ax1.legend()
    out = Path(a.csv).with_name(Path(a.csv).stem + f"_step{a.index}.png")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print(f"Đồ thị: {out}")
    plt.show()


# ---------------------------------------------------------------- disturbance
def cmd_disturbance(a):
    t, sp, rpm, u, ev = load(a.csv)
    y = smooth(rpm, a.smooth)

    if a.t_dist is not None:
        t_mark = a.t_dist
    else:
        marks = [i for i, e in enumerate(ev) if e and a.mark in e]
        if not marks:
            raise SystemExit(f"Không có nhãn chứa '{a.mark}'. Dùng --t-dist để nhập tay.")
        t_mark = t[marks[0]]

    # Nhãn gõ tay có độ trễ -> tìm thời điểm bắt đầu nhiễu trong [t_mark - pre, t_mark + post]
    win = np.flatnonzero((t >= t_mark - a.pre) & (t <= t_mark + a.post))
    r = sp[win[0]]
    tol = a.band * abs(r)
    e = y[win] - r
    out_idx = np.flatnonzero(np.abs(e) > tol)
    if out_idx.size == 0:
        raise SystemExit("Không thấy vận tốc lệch khỏi dải trong cửa sổ — tăng tải hoặc giảm --band.")

    i_start = win[out_idx[0]]
    i_peak = win[int(np.argmax(np.abs(e)))]
    i_rec = win[out_idx[-1]] + 1 if win[out_idx[-1]] + 1 <= win[-1] else None
    t_rec = t[i_rec] - t[i_start] if i_rec is not None else np.nan
    drop = y[i_peak] - r
    base = slice(max(0, i_start - 50), i_start)
    du = u[i_rec:win[-1]].mean() - u[base].mean() if i_rec is not None else np.nan

    print(f"SP={r:.1f} rpm | dải ±{a.band*100:.0f}%")
    print("| Kp | Ki | Kd | Độ lệch max (rpm) | Độ lệch max (%) | T phục hồi (s) | ΔPWM bù tải (count) |")
    print("|---|---|---|---|---|---|---|")
    print(f"| {a.kp} | {a.ki} | {a.kd} | {drop:.1f} | {abs(drop)/abs(r)*100:.1f} | {t_rec:.3f} | {du:.1f} |")

    tt = t[win] - t[i_start]
    fig, (ax1, ax2) = plt.subplots(2, 1, sharex=True, figsize=(9, 6))
    ax1.plot(tt, sp[win], "r--", label="Setpoint")
    ax1.plot(tt, y[win], "b", label="Vận tốc")
    ax1.axhspan(r - tol, r + tol, color="g", alpha=0.15)
    ax1.axvline(0, color="k", ls=":", label="Bắt đầu tải")
    if i_rec is not None:
        ax1.axvline(t_rec, color="m", ls=":", label=f"Phục hồi {t_rec:.2f}s")
    ax1.set_title(f"Tải đột ngột | Kp={a.kp} Ki={a.ki} Kd={a.kd}")
    ax1.set_ylabel("rpm")
    ax1.legend()
    ax2.plot(tt, u[win], "g")
    ax2.set_ylabel("PWM (0–255)")
    ax2.set_xlabel("t [s] (0 = bắt đầu lệch)")
    for ax in (ax1, ax2):
        ax.grid(True)
    out = Path(a.csv).with_name(Path(a.csv).stem + "_disturbance.png")
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print(f"Đồ thị: {out}")
    plt.show()


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("csv")
        p.add_argument("--band", type=float, default=0.05, help="dải xác lập, 0.02 hoặc 0.05")
        p.add_argument("--smooth", type=int, default=1, help="trung bình trượt N mẫu khi phân tích")
        p.add_argument("--kp", default="?")
        p.add_argument("--ki", default="?")
        p.add_argument("--kd", default="?")

    p = sub.add_parser("step")
    common(p)
    p.add_argument("--index", type=int, default=0, help="bước SP thứ mấy trong file")
    p.set_defaults(func=cmd_step)

    p = sub.add_parser("disturbance")
    common(p)
    p.add_argument("--mark", default="load")
    p.add_argument("--t-dist", type=float, default=None, help="nhập tay thời điểm có tải (s)")
    p.add_argument("--pre", type=float, default=1.5)
    p.add_argument("--post", type=float, default=4.0)
    p.set_defaults(func=cmd_disturbance)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
