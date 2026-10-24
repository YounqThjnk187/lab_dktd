"""Generate explicitly simulated PID data for use with analyze_response.py.

The plant is a hypothetical first-order motor model, not a measurement or
identified model of the user's hardware. Values are stored in the analyzer's
`rpm` column for compatibility, in virtual rpm rather than measured rpm.
"""
import argparse
import csv
from pathlib import Path


TS = 0.01
SETPOINT = 150.0
PLANT_GAIN = 1.2  # virtual rpm per PWM count
PLANT_TAU = 0.18  # seconds
LOAD_DROP = 35.0  # virtual rpm at fixed PWM

TUNINGS = {
    "P": (1.2, 0.0, 0.0),
    "PI": (0.7, 1.2, 0.0),
    "PID": (0.6, 1.5, 0.01),
}


def simulate(kp, ki, kd, duration, with_load, step_time=0.5, load_time=5.0):
    rows = []
    speed = 0.0
    integral = 0.0
    last_error = 0.0
    pwm = 0
    count = int(duration / TS)

    for index in range(count):
        t = index * TS
        target = SETPOINT if t >= step_time else 0.0
        error = target - speed
        integral = max(-255.0, min(255.0, integral + error * TS))
        derivative = (error - last_error) / TS
        output = kp * error + ki * integral + kd * derivative
        pwm = max(0, min(255, int(output)))
        last_error = error

        load = LOAD_DROP if with_load and t >= load_time else 0.0
        speed += TS * (PLANT_GAIN * pwm - load - speed) / PLANT_TAU
        event = "load" if with_load and abs(t - load_time) < TS / 2 else ""
        rows.append((t, target, speed, pwm, event))
    return rows


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(("t", "sp", "rpm", "u", "event"))
        writer.writerows(
            (f"{t:.2f}", f"{sp:.2f}", f"{speed:.4f}", f"{pwm:.2f}", event)
            for t, sp, speed, pwm, event in rows
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).parent / "data_simulated",
        help="output folder (default: homework/data_simulated)",
    )
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    for name, (kp, ki, kd) in TUNINGS.items():
        rows = simulate(kp, ki, kd, duration=6.0, with_load=False)
        write_csv(args.out_dir / f"step_{name.lower()}.csv", rows)

    kp, ki, kd = TUNINGS["PID"]
    rows = simulate(kp, ki, kd, duration=10.0, with_load=True)
    write_csv(args.out_dir / "load_pid.csv", rows)
    print(f"Created SIMULATED data (not hardware measurements): {args.out_dir}")
    print(f"Final simulated PID: Kp={kp}, Ki={ki}, Kd={kd}")


if __name__ == "__main__":
    main()
