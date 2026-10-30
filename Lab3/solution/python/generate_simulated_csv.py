"""Generate illustrative, non-hardware PID CSVs compatible with monitor.py."""

import argparse
import csv
import math
from pathlib import Path


SAMPLE_TIME_S = 0.01
ENCODER_PPR = 11.0
GEAR_RATIO = 34.0
QUADRATURE_MULTIPLIER = 4.0
COUNTS_PER_OUTPUT_REV = (
    ENCODER_PPR * GEAR_RATIO * QUADRATURE_MULTIPLIER
)
SPEED_FILTER_ALPHA = 0.3
KP = 0.8
KI = 1.0
KD = 0.0
SETPOINT_RPM = 40.0
MOTOR_NO_LOAD_SPEED_RPM_AT_100_PERCENT = 300.0
MOTOR_TIME_CONSTANT_S = 0.25
LOAD_SPEED_DROP_RPM = 25.0
STEP_TIME_S = 1.0
LOAD_START_S = 6.0
LOAD_END_S = 8.0


def simulate(duration_s: float, include_load: bool) -> list[tuple[float, float, float, float, str]]:
    sample_count = round(duration_s / SAMPLE_TIME_S)
    if not math.isclose(sample_count * SAMPLE_TIME_S, duration_s):
        raise ValueError("Duration must be a multiple of the 10 ms sample time")

    actual_rpm = 0.0
    filtered_rpm = 0.0
    encoder_position = 0.0
    previous_encoder_count = 0
    integral = 0.0
    previous_error = 0.0
    output_percent = 0.0
    samples = []

    for index in range(sample_count + 1):
        t = round(index * SAMPLE_TIME_S, 2)
        if index > 0:
            load_drop = (
                LOAD_SPEED_DROP_RPM
                if include_load and LOAD_START_S <= t < LOAD_END_S
                else 0.0
            )
            motor_target_rpm = (
                output_percent
                * MOTOR_NO_LOAD_SPEED_RPM_AT_100_PERCENT
                / 100.0
                - load_drop
            )
            actual_rpm += (
                motor_target_rpm - actual_rpm
            ) * SAMPLE_TIME_S / MOTOR_TIME_CONSTANT_S

            encoder_position += (
                actual_rpm
                * COUNTS_PER_OUTPUT_REV
                * SAMPLE_TIME_S
                / 60.0
            )
            encoder_count = math.floor(encoder_position)
            delta_count = encoder_count - previous_encoder_count
            previous_encoder_count = encoder_count
            measured_rpm = (
                delta_count
                / COUNTS_PER_OUTPUT_REV
                / SAMPLE_TIME_S
                * 60.0
            )
            filtered_rpm += SPEED_FILTER_ALPHA * (
                measured_rpm - filtered_rpm
            )

        setpoint_rpm = SETPOINT_RPM if t >= STEP_TIME_S else 0.0
        event = ""
        if index == 0:
            event = (
                "SIMULATED DATA ONLY; assumed first-order plant, "
                "not measured hardware"
            )
        elif math.isclose(t, STEP_TIME_S, abs_tol=1e-9):
            event = (
                f"SIMULATED: pid {KP} {KI} {KD}; "
                f"sp {SETPOINT_RPM:g} rpm"
            )
        elif include_load and math.isclose(
            t, LOAD_START_S, abs_tol=1e-9
        ):
            event = (
                f"SIMULATED LOAD ON: assumed {LOAD_SPEED_DROP_RPM:g} rpm "
                "load drop"
            )
        elif include_load and math.isclose(
            t, LOAD_END_S, abs_tol=1e-9
        ):
            event = "SIMULATED LOAD OFF"

        if t >= STEP_TIME_S:
            error = setpoint_rpm - filtered_rpm
            candidate_integral = integral + error
            unconstrained_output = (
                KP * error
                + KI * SAMPLE_TIME_S * candidate_integral
                + KD * (error - previous_error) / SAMPLE_TIME_S
            )
            output_percent = max(
                -100.0, min(100.0, unconstrained_output)
            )
            saturated_high = unconstrained_output > 100.0
            saturated_low = unconstrained_output < -100.0
            if (
                (not saturated_high and not saturated_low)
                or (saturated_high and error < 0.0)
                or (saturated_low and error > 0.0)
            ):
                integral = candidate_integral
            previous_error = error

        samples.append(
            (t, setpoint_rpm, filtered_rpm, output_percent, event)
        )

    return samples


def write_csv(path: Path, samples: list[tuple[float, float, float, float, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["t", "sp", "rpm", "u", "event"])
        for t, setpoint, rpm, output, event in samples:
            writer.writerow(
                [f"{t:.2f}", f"{setpoint:.2f}", f"{rpm:.2f}", f"{output:.2f}", event]
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "data",
        help="directory where the simulated CSV files are written",
    )
    args = parser.parse_args()

    outputs = (
        (
            args.out_dir / "simulated_step_response.csv",
            simulate(5.0, include_load=False),
        ),
        (
            args.out_dir / "simulated_load_disturbance.csv",
            simulate(10.0, include_load=True),
        ),
    )
    for path, samples in outputs:
        write_csv(path, samples)
        print(f"Wrote {len(samples)} simulated samples to {path}")


if __name__ == "__main__":
    main()
