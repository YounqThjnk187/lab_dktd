# Lab 3 – Lưu đồ thuật toán PID rời rạc (vận tốc động cơ DC)

Công thức rời rạc (Ts = 10 ms):

$$u[k] = K_p e[k] + K_i T_s \sum_{j=0}^{k} e[j] + K_d \frac{e[k]-e[k-1]}{T_s}$$

## 1. Tổng quan hệ thống

```mermaid
flowchart LR
    PC["PC: monitor.py<br/>(pyserial + matplotlib)"] -- "lệnh: kp/ki/kd/sp/open/stop" --> ESP
    ESP -- "D,t,sp,rpm,u (100 Hz)" --> PC
    subgraph ESP["ESP32"]
        ISR["ISR Encoder (x4)"] --> CNT[(encCount)]
        CNT --> CTRL["controlTask Ts=10ms<br/>tính rpm + PID"]
        CTRL --> Q[(Queue mẫu)]
        Q --> LOOP["loop(): in dữ liệu + parse lệnh"]
        LOOP --> PAR[(Kp, Ki, Kd, SP, mode)]
        PAR --> CTRL
    end
    CTRL -- "PWM + DIR" --> DRV["TB6612FNG"] --> M["JGA25-370"]
    M -- "kênh A/B" --> ISR
```

## 2. setup()

```mermaid
flowchart TD
    A([Start]) --> B[Serial 115200]
    B --> C[Cấu hình chân TB6612: PWMA/AIN1/AIN2/STBY<br/>PWM 20 kHz, 10 bit]
    C --> D[Encoder A/B: INPUT_PULLUP<br/>attachInterrupt CHANGE cho cả A và B]
    D --> E[Tạo Queue mẫu]
    E --> F[Tạo controlTask, ưu tiên cao, core 1]
    F --> G([Vào loop])
```

## 3. ISR encoder (giải mã cầu phương x4)

```mermaid
flowchart TD
    A([Ngắt CHANGE trên A hoặc B]) --> B["Đọc s = (A<<1)|B"]
    B --> C["idx = (prev<<2)|s"]
    C --> D["encCount += QDEC[idx]  (+1 / -1 / 0)"]
    D --> E[prev = s]
    E --> F([Return])
```

## 4. controlTask – vòng lặp PID chu kỳ cố định 10 ms

```mermaid
flowchart TD
    A([Start task]) --> B["last = tick hiện tại"]
    B --> C["vTaskDelayUntil(last, 10 ms)"]
    C --> D["Đọc encCount (critical section)<br/>Δc = count - prevCount"]
    D --> E["rpm_raw = Δc / CPR / Ts × 60<br/>rpm = rpm + α (rpm_raw - rpm)"]
    E --> F["Chụp tham số: Kp, Ki, Kd, SP, mode"]
    F --> G{mode?}
    G -- STOP --> H["u = 0, reset PID"]
    G -- OPEN --> I["u = openDuty"]
    G -- CLOSED --> J["e = SP - rpm"]
    J --> K["P = Kp·e<br/>I = Ki·Ts·Σe<br/>D = Kd·(e - e_prev)/Ts"]
    K --> L["u = P + I + D"]
    L --> M{"|u| > Umax?"}
    M -- Có --> N["u = ±Umax<br/>Anti-windup: chỉ cộng Σe nếu e kéo u về vùng tuyến tính"]
    M -- Không --> O["Σe += e"]
    N --> P["e_prev = e"]
    O --> P
    H --> Q
    I --> Q
    P --> Q["motorWrite(u): chiều + duty PWM"]
    Q --> R["Đẩy mẫu {t, SP, rpm, u} vào Queue"]
    R --> C
```

## 5. loop() – giao tiếp Serial

```mermaid
flowchart TD
    A([loop]) --> B{Queue có mẫu?}
    B -- Có --> C["In 'D,t,sp,rpm,u'<br/>(mỗi logDiv mẫu)"]
    C --> B
    B -- Không --> D{Serial có ký tự?}
    D -- Không --> A
    D -- Có --> E[Gom ký tự đến '\n']
    E --> F{Lệnh}
    F -- "kp/ki/kd/pid" --> G[Cập nhật hệ số]
    F -- "sp x" --> H["SP = x, mode = CLOSED"]
    F -- "open x" --> I["openDuty = x, mode = OPEN"]
    F -- stop --> J[mode = STOP]
    F -- reset --> K[Xóa Σe, e_prev]
    F -- "?" --> L[In tham số hiện tại]
    F -- khác --> M[Báo lỗi]
    G & H & I & J & K & L & M --> A
```

## 6. monitor.py (PC)

```mermaid
flowchart TD
    A([Start]) --> B[Mở cổng Serial]
    B --> C[Thread đọc: readline]
    B --> D[Thread nhập lệnh từ bàn phím]
    B --> E[Main: FuncAnimation vẽ live-plot]
    C --> C1{"Dòng bắt đầu 'D,'?"}
    C1 -- Có --> C2[Parse → buffer vẽ + list ghi CSV]
    C1 -- Không --> C3[In ra console]
    D --> D1{"Lệnh 'mark ...'?"}
    D1 -- Có --> D2[Chỉ ghi nhãn sự kiện vào CSV]
    D1 -- Không --> D3[Gửi xuống ESP32 + ghi nhãn sự kiện]
    E --> F{Đóng cửa sổ?}
    F -- Có --> G[Gửi 'stop', lưu CSV, thoát]
```

## 7. Quy trình bài tập về nhà

```mermaid
flowchart TD
    A([Start]) --> B{Phương pháp tune}
    B -- "ZN vòng hở" --> C["open 30 → open 60, ghi CSV"]
    C --> D["ziegler_nichols.py openloop<br/>→ K, L, T → Kp, Ki, Kd"]
    B -- "ZN vòng kín" --> E["ki 0, kd 0; tăng Kp đến dao động duy trì"]
    E --> F["ziegler_nichols.py closedloop<br/>→ Ku, Tu → Kp, Ki, Kd"]
    B -- "Thử-sai" --> G["Kp → Ki → Kd, mỗi lần 1 tham số"]
    D & F & G --> H["Chạy bước SP (vd 0 → 150 rpm), ghi CSV"]
    H --> I["analyze_response.py step<br/>→ Mp, tr, ts, ess + đồ thị"]
    I --> J{Đạt yêu cầu?}
    J -- Không --> G
    J -- Có --> K["Đang ổn định: cản trục + 'mark load'"]
    K --> L["analyze_response.py disturbance<br/>→ độ sụt, thời gian phục hồi"]
    L --> M["Điền homework/BaoCao_Lab3.md"]
    M --> N([Nộp])
```
