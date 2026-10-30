"""Live-plot ESP32 PID telemetry and save samples/events to CSV."""

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
from serial.tools import list_ports


def detect_serial_port() -> str:
    usb_ports = [
        port
        for port in list_ports.comports()
        if port.vid is not None and "BTHENUM" not in (port.hwid or "").upper()
    ]
    if len(usb_ports) == 1:
        return usb_ports[0].device
    if not usb_ports:
        raise RuntimeError(
            "No USB serial device found. Connect the ESP32 and check Device "
            "Manager, or run with --port COMx."
        )

    ports = ", ".join(
        f"{port.device} ({port.description})" for port in usb_ports
    )
    raise RuntimeError(
        f"Multiple USB serial devices found: {ports}. "
        "Choose the ESP32 with --port COMx."
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--port",
        help="serial port, e.g. COM7 (auto-detects one USB serial device if omitted)",
    )
    parser.add_argument("--baud", type=int, default=115200)
    parser.add_argument("--window", type=float, default=10.0)
    parser.add_argument(
        "--out",
        default=f"data/run_{time.strftime('%Y%m%d_%H%M%S')}.csv",
    )
    args = parser.parse_args()
    if args.window <= 0:
        parser.error("--window must be greater than zero")

    try:
        port = args.port or detect_serial_port()
    except RuntimeError as exc:
        parser.error(str(exc))
    print(f"Connecting to {port}...")
    try:
        connection = serial.Serial(port, args.baud, timeout=0.1)
    except serial.SerialException as exc:
        parser.error(
            f"Could not open {port}: {exc}. Close Arduino Serial Monitor "
            "and check that the ESP32 is connected."
        )
    max_points = max(10, int(args.window * 100) + 10)
    buffers = {
        name: deque(maxlen=max_points) for name in ("t", "sp", "rpm", "u")
    }
    rows: list[tuple[float, float, float, float, str]] = []
    lock = threading.Lock()
    stop = threading.Event()
    state: dict[str, float | int | str | None] = {
        "t0_ms": None,
        "last_t": 0.0,
        "pending_event": "",
    }

    def read_serial() -> None:
        while not stop.is_set():
            try:
                raw = connection.readline()
            except serial.SerialException as exc:
                if not stop.is_set():
                    print(f"Serial read failed: {exc}", file=sys.stderr)
                    stop.set()
                break
            if not raw:
                continue
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("D,"):
                print(line)
                continue
            try:
                _, t_ms_text, sp_text, rpm_text, u_text = line.split(",")
                t_ms = int(t_ms_text)
                sp, rpm, output = map(float, (sp_text, rpm_text, u_text))
            except ValueError:
                print(f"Skipping malformed telemetry: {line}", file=sys.stderr)
                continue

            with lock:
                if state["t0_ms"] is None:
                    state["t0_ms"] = t_ms
                t = (t_ms - int(state["t0_ms"])) / 1000.0
                state["last_t"] = t
                for name, value in zip(
                    ("t", "sp", "rpm", "u"), (t, sp, rpm, output)
                ):
                    buffers[name].append(value)
                rows.append((t, sp, rpm, output, str(state["pending_event"])))
                state["pending_event"] = ""

    def send_commands() -> None:
        for raw_command in sys.stdin:
            if stop.is_set():
                break
            command = raw_command.strip()
            if not command:
                continue
            if command.lower().startswith("mark "):
                event = command[5:].strip()
                with lock:
                    previous = str(state["pending_event"])
                    state["pending_event"] = ";".join(
                        part for part in (previous, event) if part
                    )
            else:
                try:
                    connection.write((command + "\n").encode("utf-8"))
                except serial.SerialException as exc:
                    print(f"Serial write failed: {exc}", file=sys.stderr)
                    stop.set()
                    break
            with lock:
                current_t = float(state["last_t"])
            print(f"> {command} @ t={current_t:.2f}s")

    reader = threading.Thread(target=read_serial, daemon=True)
    writer = threading.Thread(target=send_commands, daemon=True)
    reader.start()
    writer.start()

    figure, (speed_axis, output_axis) = plt.subplots(
        2, 1, sharex=True, figsize=(10, 6)
    )
    (setpoint_line,) = speed_axis.plot([], [], "r--", label="Setpoint")
    (speed_line,) = speed_axis.plot([], [], "b-", label="Measured speed")
    (output_line,) = output_axis.plot([], [], "g-", label="PID output")
    speed_axis.set_ylabel("Speed (rpm)")
    output_axis.set_ylabel("Output (%)")
    output_axis.set_xlabel("Time (s)")
    output_axis.set_ylim(-105, 105)
    for axis in (speed_axis, output_axis):
        axis.grid(True)
        axis.legend(loc="upper left")

    def update(_frame: int):
        with lock:
            t, sp, rpm, output = (
                list(buffers[name]) for name in ("t", "sp", "rpm", "u")
            )
        if not t:
            return setpoint_line, speed_line, output_line
        setpoint_line.set_data(t, sp)
        speed_line.set_data(t, rpm)
        output_line.set_data(t, output)
        speed_axis.set_xlim(max(0.0, t[-1] - args.window), max(args.window, t[-1]))
        speed_axis.relim()
        speed_axis.autoscale_view(scalex=False)
        return setpoint_line, speed_line, output_line

    animation = FuncAnimation(
        figure, update, interval=50, cache_frame_data=False
    )
    figure.tight_layout()
    try:
        plt.show()
    finally:
        stop.set()
        try:
            connection.write(b"stop\n")
            time.sleep(0.2)
        except serial.SerialException as exc:
            print(f"Could not send stop command: {exc}", file=sys.stderr)
        connection.close()

        output_path = Path(args.out)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer_csv = csv.writer(csv_file)
            writer_csv.writerow(["t", "sp", "rpm", "u", "event"])
            writer_csv.writerows(rows)
        print(f"Saved {len(rows)} samples to {output_path}")
        del animation


if __name__ == "__main__":
    main()
