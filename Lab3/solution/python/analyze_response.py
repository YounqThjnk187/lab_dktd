"""Plot a recorded step response and calculate basic PID performance metrics."""

import argparse
import csv
from pathlib import Path

import matplotlib.pyplot as plt


def load_samples(path: Path) -> list[tuple[float, float, float, float]]:
    samples = []
    with path.open(newline="", encoding="utf-8-sig") as csv_file:
        for row in csv.DictReader(csv_file):
            try:
                samples.append(
                    (
                        float(row["t"]),
                        float(row["sp"]),
                        float(row["rpm"]),
                        float(row["u"]),
                    )
                )
            except (KeyError, ValueError) as exc:
                raise ValueError(f"Invalid telemetry row: {row}") from exc
    if len(samples) < 2:
        raise ValueError("CSV must contain at least two valid telemetry samples")
    if any(samples[i][0] <= samples[i - 1][0] for i in range(1, len(samples))):
        raise ValueError("CSV timestamps must be strictly increasing")
    return samples


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv", type=Path)
    parser.add_argument("--start", type=float, required=True, help="step start time (s)")
    parser.add_argument("--target", type=float, required=True, help="step target (rpm)")
    parser.add_argument("--band", type=float, default=0.05, help="settling band fraction")
    parser.add_argument("--plot", type=Path, help="optional PNG output path")
    args = parser.parse_args()
    if args.band <= 0 or args.band >= 1:
        parser.error("--band must be between 0 and 1")

    samples = load_samples(args.csv)
    response = [sample for sample in samples if sample[0] >= args.start]
    if len(response) < 2:
        raise ValueError("Not enough samples after --start")

    first_time, initial_speed = response[0][0], response[0][2]
    change = args.target - initial_speed
    if change == 0:
        raise ValueError("Target equals the initial speed; no step response to analyze")
    final_window = response[max(0, int(len(response) * 0.9)) :]
    steady_speed = sum(sample[2] for sample in final_window) / len(final_window)
    peak_speed = max(sample[2] for sample in response) if change > 0 else min(
        sample[2] for sample in response
    )
    overshoot = max(0.0, (peak_speed - args.target) * (1 if change > 0 else -1))
    overshoot_percent = 100.0 * overshoot / abs(change)

    def crossing_time(fraction: float) -> float | None:
        threshold = initial_speed + fraction * change
        for t, _sp, rpm, _u in response:
            if (change > 0 and rpm >= threshold) or (
                change < 0 and rpm <= threshold
            ):
                return t - first_time
        return None

    tolerance = args.band * abs(change)
    outside = [
        sample[0]
        for sample in response
        if abs(sample[2] - args.target) > tolerance
    ]
    settled_samples = (
        [sample for sample in response if sample[0] > outside[-1]]
        if outside
        else response
    )
    settling_time = (
        settled_samples[0][0] - first_time if settled_samples else None
    )
    final_error = abs(args.target - steady_speed)

    print(
        "Rise time (10-90%): "
        f"{format_duration(crossing_time(0.9), crossing_time(0.1))}"
    )
    print(f"Overshoot: {overshoot_percent:.2f}%")
    settling_text = (
        f"{settling_time:.3f} s"
        if settling_time is not None
        else "not settled within capture"
    )
    print(f"Settling time (±{args.band * 100:.1f}%): {settling_text}")
    error_percent = (
        100.0 * final_error / abs(args.target) if args.target else None
    )
    percent_text = f"{error_percent:.2f}%" if error_percent is not None else "n/a"
    print(f"Steady-state error: {final_error:.3f} rpm ({percent_text})")

    time_values = [sample[0] for sample in samples]
    setpoints = [sample[1] for sample in samples]
    speeds = [sample[2] for sample in samples]
    outputs = [sample[3] for sample in samples]
    figure, (speed_axis, output_axis) = plt.subplots(
        2, 1, sharex=True, figsize=(10, 6)
    )
    speed_axis.plot(time_values, setpoints, "r--", label="Setpoint")
    speed_axis.plot(time_values, speeds, "b-", label="Measured speed")
    speed_axis.axvline(args.start, color="k", linestyle=":", label="Step start")
    speed_axis.set_ylabel("Speed (rpm)")
    speed_axis.grid(True)
    speed_axis.legend()
    output_axis.plot(time_values, outputs, "g-", label="PID output")
    output_axis.set_ylabel("Output (%)")
    output_axis.set_xlabel("Time (s)")
    output_axis.grid(True)
    output_axis.legend()
    figure.tight_layout()
    if args.plot:
        args.plot.parent.mkdir(parents=True, exist_ok=True)
        figure.savefig(args.plot, dpi=160)
        print(f"Saved plot to {args.plot}")
    else:
        plt.show()


def format_duration(end: float | None, start: float | None) -> str:
    if end is None or start is None:
        return "not reached"
    return f"{max(0.0, end - start):.3f} s"


if __name__ == "__main__":
    main()
