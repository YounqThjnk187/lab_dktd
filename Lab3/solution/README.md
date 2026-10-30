# Lab 3 — PID motor speed control

This solution is for ESP32 DevKit V1, TB6612FNG, and a two-channel DC motor
encoder. It implements a 10 ms discrete PID loop, runtime Serial tuning, live
plotting, CSV logging, and step-response analysis.

## Wiring

| Device pin/wire | Connect to |
|---|---|
| Motor M1 (outermost right) | TB6612FNG AO1 |
| Motor M2 | TB6612FNG AO2 |
| Encoder VCC | ESP32 3V3 |
| Encoder GND | ESP32 GND |
| Encoder A (middle wire 1) | ESP32 GPIO32 |
| Encoder B (middle wire 2) | ESP32 GPIO33 |
| TB6612FNG PWMA | ESP32 GPIO25 |
| TB6612FNG AIN1 / AIN2 | ESP32 GPIO26 / GPIO27 |
| TB6612FNG STBY | ESP32 3V3 (always enabled) |
| TB6612FNG VCC | ESP32 3V3 |
| TB6612FNG VM | Positive terminal of the external motor supply |
| Both TB6612FNG GND pins | Common ESP32 GND and motor-supply negative |

Use the stated 7.4–12 V motor supply only when it is within the motor and
driver ratings. Confirm the JGA25-370 motor voltage before applying 12 V. Keep
all grounds common. Never power the motor from the ESP32 3V3/5V pin. Keep a
power switch accessible. Do not touch the motor shaft or wiring while powered.
Because STBY is tied directly to 3V3, the driver is enabled whenever it is
powered; use the external supply switch and the firmware `stop` command.

The firmware uses GPIO32/33's upper GPIO input register in the encoder ISR;
GPIO33 must not also be assigned to STBY. Set `ENC_PPR`, `GEAR_RATIO`, and
`ENCODER_DIRECTION` near the top of `pid_motor/pid_motor.ino` to match the
actual motor. The current PPR (11) and gear ratio (34) are example values, not
verified JGA25-370 specifications. `PPR` is pulses per motor-shaft revolution;
counts per gearbox-output revolution are `PPR * gear ratio * 4` because both
encoder channels are decoded on both edges. Check the motor datasheet or
measure the output shaft before trusting displayed RPM. If a positive PWM
command produces negative measured RPM, change `ENCODER_DIRECTION` to `-1`.

## Run

1. Open `pid_motor/pid_motor.ino` in Arduino IDE, select the ESP32 board and
   correct port, then upload it. The controller starts in STOP mode.
2. Install the host dependencies:

   ```powershell
   python -m pip install -r .\python\requirements.txt
   ```

3. From this folder, start the monitor. If exactly one USB serial device is
   connected, its port is detected automatically:

   ```powershell
   python .\python\monitor.py
   ```

   To select a port manually or specify a CSV path:

   ```powershell
   python .\python\monitor.py --port COM7 --out .\data\step_01.csv
   ```

4. Type commands in the terminal running the monitor. Common commands:

   | Command | Purpose |
   |---|---|
   | `?` | Show current PID parameters and encoder CPR |
   | `open 15` | Apply 15% open-loop duty for direction/wiring checks |
   | `stop` | Stop the motor |
   | `pid 0.2 0 0` | Set Kp, Ki, Kd |
   | `sp 30` | Set a 30 rpm target and enable closed loop |
   | `kp 0.3`, `ki 0.5`, `kd 0.001` | Change one gain while running |
   | `reset` | Clear the integral and previous error |
   | `rate 2` | Log every other sample; the control loop still runs at 100 Hz |
   | `mark step-30`, `mark load` | Label the next CSV sample with an event |

   Begin at low duty/setpoint with the motor secured and an accessible power
   switch. Confirm the encoder direction and CPR before tuning. Tune one gain at
   a time and use an appropriate current-limited supply. Closing the plot sends
   `stop` and saves the CSV.

5. Analyze a single step-response CSV. Set `--start` to the step time in seconds
   on the CSV time axis and `--target` to the requested RPM:

   ```powershell
   python .\python\analyze_response.py .\data\step_01.csv `
       --start 1.0 --target 30 --plot .\data\step_01.png
   ```

   The analyzer reports 10–90% rise time, overshoot, settling time, and
   steady-state error. Use one CSV per step test. Use the event label and plot
   to inspect load recovery; record its recovery time and load method in the
   report.

## Offline example (simulated, not hardware data)

If hardware is unavailable, create example files with the same
`t,sp,rpm,u,event` columns saved by the monitor:

```powershell
python .\python\generate_simulated_csv.py
```

This writes `data\simulated_step_response.csv` and
`data\simulated_load_disturbance.csv`. The deterministic example uses the
firmware's 10 ms sample interval, encoder-count conversion, speed-filter
coefficient, and discrete PID/anti-windup equations. Its assumed motor gain,
time constant, load change, and encoder resolution have **not** been measured
on the user's hardware. The `SIMULATED` event labels are intentional. These
files can test plotting/analysis and illustrate expected signal shapes, but
must not be presented as real motor measurements or experimental grading
evidence.

Analyze the simulated step response with:

```powershell
python .\python\analyze_response.py .\python\data\simulated_step_response.csv `
    --start 1 --target 40 --plot .\python\data\simulated_step_response.png
```

## Submission

Complete `BaoCao_Lab3.md` with measured hardware results, attach the recorded
CSV/plots, and replace the example project-application paragraph if the actual
project is not a MPU6050-based balancing robot. Simulated or illustrative values
must not be reported as physical measurements.
