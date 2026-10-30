# Báo cáo Lab 3 — Vòng lặp PID rời rạc

**Họ tên:** Dương Quốc Thịnh | **MSSV:** 23521498 | **Nhóm:** 14

**Ngày đo:** __________
**Đề tài đồ án:** ____________________

> Điền các bảng từ dữ liệu đo trên phần cứng và các file CSV đính kèm. Không dùng
> số mô phỏng thay cho kết quả thí nghiệm. Xác nhận PPR và tỉ số truyền của đúng
> động cơ trước khi dùng giá trị RPM để báo cáo.

> `python/data/simulated_*.csv` là dữ liệu mô phỏng để kiểm tra đồ thị và cách
> phân tích khi chưa chạy được phần cứng; không điền các số mô phỏng vào bảng
> kết quả thực nghiệm.

## 1. Phần cứng và phép đo vận tốc (2 điểm)

**Thiết bị:** ESP32 DevKit V1, TB6612FNG, động cơ DC có encoder hai kênh.

**Chu kỳ lấy mẫu:** \(T_s = 10\,\mathrm{ms}\).

**Số đếm mỗi vòng trục ra:** \(CPR=PPR \times G \times 4=\) __________ count/vòng.

| Chân / dây | Nối tới |
|---|---|
| ESP32 GPIO25 | TB6612FNG PWMA |
| ESP32 GPIO26 / GPIO27 | TB6612FNG AIN1 / AIN2 |
| ESP32 3V3 | TB6612FNG VCC và STBY; dây VCC encoder |
| ESP32 GPIO32 / GPIO33 | Encoder A / Encoder B (hai dây giữa) |
| ESP32 GND | Encoder GND; cả hai GND TB6612FNG; cực âm nguồn động cơ |
| Nguồn ngoài 7.4–12 V (+) | TB6612FNG VM, nếu điện áp phù hợp định mức động cơ |
| Động cơ M1 (ngoài cùng bên phải) / M2 | TB6612FNG AO1 / AO2 |

STBY nối cố định 3V3 nên driver luôn được bật khi có nguồn. Xác nhận định mức
điện áp động cơ trước khi cấp 12 V; không cấp động cơ từ chân ESP32.

| Duty (%) | Tốc độ encoder (rpm) | Tốc độ đối chiếu (rpm) | Sai số (%) |
|---:|---:|---:|---:|
| | | | |
| | | | |
| | | | |

## 2. Tune PID và đáp ứng bước (5 điểm)

**Phương pháp:** ____________________ (Ziegler–Nichols / thử-sai có hệ thống)

**Bước đặt:** __________ rpm; **dải xác lập:** ±5% (hoặc nêu rõ dải đã dùng).

| Lần đo | Kp | Ki | Kd | Vọt lố (%) | Thời gian tăng (s) | Xác lập (s) | Sai số cuối (rpm) |
|---|---:|---:|---:|---:|---:|---:|---:|
| | | | | | | |
| | | | | | | | |
| | | | | | | | |

**Bộ thông số được chọn:** Kp = ______, Ki = ______, Kd = ______.

Đính kèm đồ thị tốc độ đặt/thực và PWM, cùng file CSV đã ghi. Định nghĩa
thời gian xác lập và độ vọt lố phải nhất quán khi so sánh các lần tune. Nên ghi
mỗi lần đáp ứng bước vào một CSV riêng để số liệu cuối không lẫn với lần đổi đặt
tốc độ tiếp theo.

## 3. Tải thay đổi đột ngột (1 điểm)

| Kp | Ki | Kd | Setpoint (rpm) | Lệch cực đại (rpm) | Thời gian hồi phục (s) | Ghi chú tải |
|---:|---:|---:|---:|---:|---:|---|
| | | | | | | |

Đánh dấu thời điểm tác động tải trong CSV bằng lệnh `mark load`, rồi đính kèm
đồ thị và mô tả tải đã tác động. Chỉ cản nhẹ, trong thời gian ngắn, và không
chạm dây/đầu nối hoặc bộ phận quay.

## 4. Liên hệ PID với đề tài đồ án (150–250 từ, 2 điểm)

**Đoạn mẫu dưới đây giả định đề tài có điều khiển góc nghiêng bằng MPU6050;
đổi biến đo/chấp hành nếu đề tài thực tế khác.**

Trong đề tài robot cân bằng dùng MPU6050, biến điều khiển là góc nghiêng thân
robot; giá trị đặt là góc thẳng đứng. ESP32 đọc accelerometer và gyroscope, kết
hợp hai tín hiệu để ước lượng góc, rồi tính sai lệch giữa góc đặt và góc đo mỗi
10 ms. PID tạo tín hiệu PWM cho driver TB6612FNG để điều chỉnh mô-men động cơ
và giữ robot gần vị trí cân bằng. Khâu P phản ứng với sai lệch hiện tại, khâu
I bù sai lệch kéo dài do tải hoặc ma sát, còn khâu D giảm dao động bằng cách
phản ứng với tốc độ thay đổi của góc. Tuy nhiên, D khuếch đại nhiễu nên cần
lọc phép đo và kiểm tra thực tế. Các hệ số tìm được trong bài điều khiển tốc
độ không dùng nguyên xi cho góc vì đối tượng và đơn vị khác nhau. Khi triển
khai, tăng Kp từ thấp, bổ sung Ki để giảm sai số xác lập, rồi thử Kd nếu còn
vọt lố. Ghi lại góc, PWM và đáp ứng sau mỗi lần chỉnh. Giới hạn PWM, góc
nghiêng và dừng động cơ khi mất dữ liệu cảm biến để tránh hệ chạy mất kiểm
soát. Bộ PID cuối phải được xác nhận trên phần cứng thật với tải dự kiến.

## 5. Kết luận

Nêu bộ PID cuối, chỉ số đo được, giới hạn của phép thử và điểm cần cải thiện:

____________________________________________________________________________

____________________________________________________________________________

