# Lab 3 — Điều khiển tốc độ động cơ bằng PID

README này hướng dẫn chạy project trong thư mục `solution`: nạp firmware cho
ESP32, thu dữ liệu từ động cơ, phân tích đáp ứng và phân biệt dữ liệu mô phỏng
với kết quả đo phần cứng.

## 1. Cấu trúc thư mục

| Đường dẫn | Chức năng |
|---|---|
| `Lab3.pdf` | Đề bài và tiêu chí đánh giá Lab 3 |
| `solution/pid_motor/pid_motor.ino` | Firmware ESP32: đọc encoder, tính PID, điều khiển PWM và nhận lệnh Serial |
| `solution/python/monitor.py` | Kết nối Serial, vẽ đồ thị trực tiếp và lưu dữ liệu thành CSV |
| `solution/python/analyze_response.py` | Tính chỉ số đáp ứng bước và xuất đồ thị PNG từ CSV |
| `solution/python/requirements.txt` | Các thư viện Python cần cho monitor và phân tích |
| `solution/python/data/step_response.csv` | Dữ liệu đáp ứng bước |
| `solution/python/data/load_disturbance.csv` | Dữ liệu thay đổi tải |
| `solution/python/data/run_test.csv` | Một phiên monitor đã lưu; hiện các giá trị đặt, tốc độ và PWM đều bằng 0 |
| `23521498_DuongQuocThinh_Lab3.docx` | Báo cáo Lab dạng có thể chỉnh sửa |
| `23521498_DuongQuocThinh_Lab3.pdf` | Bản PDF của báo cáo Lab |

## 2. Thiết bị và nối dây

Project mẫu sử dụng ESP32 DevKit V1, driver TB6612FNG và động cơ DC có encoder
hai kênh. Kết nối theo bảng sau:

| Chân / dây | Kết nối |
|---|---|
| ESP32 GPIO25 | TB6612FNG PWMA |
| ESP32 GPIO26 / GPIO27 | TB6612FNG AIN1 / AIN2 |
| ESP32 GPIO32 / GPIO33 | Encoder A / Encoder B |
| ESP32 3V3 | TB6612FNG VCC và STBY; VCC encoder |
| ESP32 GND | Encoder GND, hai chân GND driver, cực âm nguồn động cơ |
| Nguồn động cơ (+) | TB6612FNG VM |
| Động cơ M1 / M2 | TB6612FNG AO1 / AO2 |

Chỉ cấp nguồn động cơ trong giới hạn điện áp của cả động cơ và driver; không
cấp động cơ từ chân 3V3/5V ESP32. STBY nối thẳng 3V3 nên driver luôn được bật
khi có nguồn. Cố định động cơ, giữ công tắc nguồn trong tầm với và không chạm
trục quay hoặc dây nối khi đang cấp điện.

Trước khi dùng kết quả RPM, xác nhận `ENC_PPR`, `GEAR_RATIO` và
`ENCODER_DIRECTION` ở đầu file `solution/pid_motor/pid_motor.ino` đúng với động
cơ thực tế. CPR trục ra được tính theo:

```text
CPR = ENC_PPR * GEAR_RATIO * 4
```

Giá trị PPR = 11 và tỉ số truyền = 34 trong firmware là giá trị ví dụ, chưa
được xác nhận cho động cơ của bạn.

## 3. Nạp firmware lên ESP32

1. Mở `solution/pid_motor/pid_motor.ino` bằng Arduino IDE.
2. Chọn board ESP32 phù hợp và cổng USB/Serial đang kết nối với ESP32.
3. Kiểm tra cấu hình encoder, dây nối và nguồn động cơ.
4. Nhấn **Upload** để biên dịch và nạp chương trình.

Sau khi khởi động, firmware vào chế độ `STOP`, gửi telemetry ở baud rate
115200 và chạy vòng điều khiển mỗi 10 ms. Không mở Arduino Serial Monitor cùng
lúc với chương trình Python monitor vì hai chương trình không thể đồng thời sử
dụng cùng một cổng Serial.

## 4. Cài Python và chạy monitor

Mở Terminal tại thư mục `Lab3/solution`:

```bash
cd Lab3/solution
```

Cài các thư viện cần thiết:

```bash
python -m pip install -r python/requirements.txt
```

Chạy monitor và lưu phiên đo vào CSV:

```bash
python python/monitor.py --out python/data/run_test.csv
```

Nếu máy có nhiều cổng Serial hoặc tự dò không đúng thiết bị, chỉ định cổng
thủ công, ví dụ:

```bash
python python/monitor.py --port /dev/cu.usbserial-0001 --out python/data/run_test.csv
```

Thay `/dev/cu.usbserial-0001` bằng cổng của ESP32 trên máy bạn. Trên Windows,
cổng thường có dạng `COM7`.

Monitor mở đồ thị tốc độ đặt, tốc độ đo và đầu ra PWM. Nhập các lệnh sau trong
Terminal đang chạy monitor:

| Lệnh | Tác dụng |
|---|---|
| `?` | Xem hệ số PID, setpoint, chế độ, chu kỳ lấy mẫu và CPR |
| `open 10` | Chạy open-loop với duty 10% để kiểm tra chiều động cơ |
| `pid 0.2 0 0` | Đặt lần lượt Kp, Ki, Kd |
| `kp 0.3` / `ki 0.5` / `kd 0.001` | Thay đổi riêng một hệ số PID |
| `sp 40` | Đặt tốc độ mục tiêu 40 rpm và bật điều khiển vòng kín |
| `rate 2` | Chỉ ghi mỗi mẫu thứ hai; vòng PID vẫn chạy ở 100 Hz |
| `mark step-40` | Gắn nhãn sự kiện vào mẫu CSV kế tiếp |
| `mark load` | Đánh dấu mẫu kế tiếp là thời điểm tác động tải |
| `reset` | Xóa tích phân và sai lệch trước đó của PID |
| `stop` | Dừng động cơ |

Bắt đầu với duty/setpoint thấp. Khi đóng cửa sổ đồ thị, monitor gửi lệnh `stop`
và lưu CSV. Nên tạo một CSV riêng cho từng lần thử đáp ứng bước.

## 5. Phân tích dữ liệu ví dụ

Chạy các lệnh từ thư mục `Lab3/solution`. Hai CSV dưới đây được tạo để minh họa
và có nhãn `SIMULATED DATA ONLY`; chúng **không phải số đo phần cứng**.

Phân tích đáp ứng bước:

```bash
python python/analyze_response.py python/data/step_response.csv --start 1 --target 40 --band 0.05 --plot python/data/step_response.png
```

Phân tích file mô phỏng có nhiễu loạn tải:

```bash
python python/analyze_response.py python/data/load_disturbance.csv --start 1 --target 40 --band 0.05 --plot python/data/load_disturbance.png
```

`--start 1` chọn thời điểm bắt đầu đáp ứng ở giây thứ nhất, `--target 40` là
tốc độ đặt 40 rpm, và `--band 0.05` chọn dải xác lập ±5%. Kết quả chỉ số được
in ra Terminal; `--plot` lưu đồ thị thành PNG.

Chương trình phân tích được thiết kế chủ yếu cho đáp ứng bước. Khi chạy với
`load_disturbance.csv`, nó vẫn tính rise time, overshoot, settling time và sai
số theo đoạn từ `--start`, nhưng **không tự tính thời gian hồi phục sau khi
tải tác động**. Để đánh giá nhiễu loạn tải, xem thời điểm `SIMULATED LOAD ON` /
`SIMULATED LOAD OFF` trong cột `event` cùng đồ thị và đo độ lệch, thời gian hồi
phục riêng.

## 6. Phân tích CSV đo từ phần cứng

Sau khi thu được một lần chạy có bước đặt thực tế, ví dụ bắt đầu bước ở giây
thứ 1 và đặt 40 rpm, thay đường dẫn CSV bằng file vừa ghi:

```bash
python python/analyze_response.py python/data/run_test.csv --start 1 --target 40 --band 0.05 --plot python/data/run_test.png
```

`--start` phải là thời gian trên trục `t` của CSV, không phải thời điểm mở
monitor. CSV cần có tối thiểu hai mẫu hợp lệ và các cột `t,sp,rpm,u,event`.
Nếu capture không chứa bước đặt hoặc dữ liệu sau bước quá ngắn thì chỉ số
không có ý nghĩa để đánh giá PID.

File `python/data/run_test.csv` hiện có trong thư mục chỉ ghi toàn số 0 ở
`sp`, `rpm`, `u` và không có nhãn sự kiện. Đây chưa phải dữ liệu đáp ứng bước;
hãy tạo capture mới khi ESP32, động cơ và encoder hoạt động rồi mới dùng làm
kết quả báo cáo.

## 7. Hoàn thiện báo cáo

Hoàn thiện báo cáo `23521498_DuongQuocThinh_Lab3.docx` bằng thông số encoder đã
xác nhận, số liệu thử nghiệm phần cứng, thông số PID, đồ thị và CSV tương ứng.
Ghi rõ cách tune và điều kiện thử tải. Xuất lại PDF sau khi hoàn tất. Không
đưa dữ liệu mô phỏng hoặc capture toàn số 0 vào bảng kết quả thực nghiệm.
