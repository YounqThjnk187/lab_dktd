"""[BÀI VỀ NHÀ] Tính Kp/Ki/Kd theo Ziegler-Nichols (dạng song song khớp firmware:
u = Kp·e + Ki·∫e + Kd·de/dt  =>  Ki = Kp/Ti, Kd = Kp·Td).

1) Vòng kín (ultimate gain): ki 0, kd 0, tăng Kp đến khi vận tốc dao động đều, ghi CSV.
     python ziegler_nichols.py closedloop ../data/zn_osc.csv --ku 2.4
     python ziegler_nichols.py closedloop --ku 2.4 --tu 0.12          # nhập tay
2) Vòng hở (đường cong phản ứng): 'open 30' chờ ổn định rồi 'open 60', ghi CSV.
     python ziegler_nichols.py openloop ../data/zn_open.csv

Lưu ý: ZN cho đáp ứng khá "gắt" (Mp ~ 25%) -> thường phải giảm Kp/Ki sau đó (thử-sai có hệ thống).
"""
import argparse
import csv

import numpy as np


def load(path):
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    col = lambda k: np.array([float(r[k]) for r in rows])
    return col("t"), col("sp"), col("rpm"), col("u")


def print_table(title, rows):
    print(f"\n{title}")
    print("| Bộ điều khiển | Kp | Ki | Kd |")
    print("|---|---|---|---|")
    for name, kp, ti, td in rows:
        ki = kp / ti if ti else 0.0
        print(f"| {name} | {kp:.4f} | {ki:.4f} | {kp * td:.5f} |")
    pid = rows[-1]
    print(f"\nLệnh Serial: pid {pid[1]:.4f} {pid[1] / pid[2]:.4f} {pid[1] * pid[3]:.5f}")


# ---------------------------------------------------------------- vòng kín
def estimate_tu(t, y, t_from):
    """Chu kỳ dao động = trung bình khoảng cách giữa các lần cắt trung bình theo chiều đi lên."""
    m = t >= t_from
    t, y = t[m], np.convolve(y[m], np.ones(3) / 3, mode="same")
    yc = y - y.mean()
    hyst = 0.2 * yc.std()
    ups, armed = [], False
    for i in range(1, len(yc)):
        if yc[i] < -hyst:
            armed = True
        elif armed and yc[i] > hyst:
            ups.append(t[i])
            armed = False
    if len(ups) < 3:
        raise SystemExit("Chưa đủ chu kỳ dao động để ước lượng Tu.")
    periods = np.diff(ups)
    print(f"Số chu kỳ: {len(periods)}, Tu = {periods.mean():.4f} s (std {periods.std():.4f}), "
          f"biên độ ~ {np.ptp(y) / 2:.1f} rpm")
    return periods.mean()


def cmd_closed(a):
    tu = a.tu
    if tu is None:
        if not a.csv:
            raise SystemExit("Cần file CSV hoặc --tu.")
        t, _, rpm, _ = load(a.csv)
        tu = estimate_tu(t, rpm, a.t_from)
    ku = a.ku
    print_table(f"ZN vòng kín: Ku={ku}, Tu={tu:.4f}s", [
        ("P",   0.50 * ku, 0.0,      0.0),
        ("PI",  0.45 * ku, tu / 1.2, 0.0),
        ("PID", 0.60 * ku, tu / 2,   tu / 8),
    ])


# ---------------------------------------------------------------- vòng hở
def cmd_open(a):
    t, _, rpm, u = load(a.csv)
    jumps = np.flatnonzero(np.abs(np.diff(u)) > 1e-6) + 1
    if jumps.size == 0:
        raise SystemExit("Không thấy bước thay đổi u (lệnh open) trong file.")
    i0 = jumps[a.index]
    i1 = jumps[a.index + 1] if a.index + 1 < jumps.size else len(t)

    u0, u1 = u[i0 - 1], u[i0]
    y0 = rpm[max(0, i0 - 20):i0].mean()
    y1 = rpm[i1 - max(5, (i1 - i0) // 5):i1].mean()
    tt = t[i0:i1] - t[i0]
    yn = (rpm[i0:i1] - y0) / (y1 - y0)

    K = (y1 - y0) / (u1 - u0)  # rpm / PWM count
    # Phương pháp 2 điểm (Smith): 28.3% and 63.2% of the response change.
    t28 = tt[np.argmax(yn >= 0.283)]
    t63 = tt[np.argmax(yn >= 0.632)]
    T = 1.5 * (t63 - t28)
    L = max(t63 - T, 1e-3)
    print(f"Mô hình FOPDT: K = {K:.3f} rpm/PWM-count, T = {T:.4f} s, L = {L:.4f} s")
    if L < 2 * 0.010:
        print("Cảnh báo: L rất nhỏ so với Ts=10ms -> hệ số ZN sẽ rất lớn, nên giảm bớt khi chạy thật.")

    base = T / (K * L)
    print_table("ZN vòng hở (đường cong phản ứng)", [
        ("P",   1.0 * base, 0.0,       0.0),
        ("PI",  0.9 * base, L / 0.3,   0.0),
        ("PID", 1.2 * base, 2.0 * L,   0.5 * L),
    ])


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("closedloop")
    p.add_argument("csv", nargs="?")
    p.add_argument("--ku", type=float, required=True, help="Kp tại đó dao động duy trì")
    p.add_argument("--tu", type=float, default=None, help="chu kỳ dao động (s), bỏ qua nếu có CSV")
    p.add_argument("--t-from", type=float, default=0.0, help="chỉ phân tích dữ liệu sau thời điểm này")
    p.set_defaults(func=cmd_closed)

    p = sub.add_parser("openloop")
    p.add_argument("csv")
    p.add_argument("--index", type=int, default=1, help="bước u thứ mấy (0 = từ 0 lên open đầu tiên)")
    p.set_defaults(func=cmd_open)

    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
