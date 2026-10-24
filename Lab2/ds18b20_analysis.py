import serial
import csv
import time
import matplotlib.pyplot as plt

# ===================================================================
# CẤU HÌNH CỔNG COM
# ===================================================================
PORT = 'COM7'        # Thay đổi đúng cổng COM ESP32 trên máy bạn
BAUD_RATE = 115200
SAMPLES = 20         # Thu thập 20 mẫu (20 giây ở chu kỳ 1s/mẫu)

def collect_temp_data(state_name, prompt_instruction):
    time_list, temp_list = [], []

    print(f"\n==========================================")
    print(f"TRẠNG THÁI: {state_name.upper()}")
    print(f"==========================================")
    print(f"-> Hướng dẫn: {prompt_instruction}")
    input("Khi đã chuẩn bị xong cảm biến, bấm ENTER để bắt đầu đo...")

    try:
        ser = serial.Serial(PORT, BAUD_RATE, timeout=2)
        time.sleep(2)
        ser.reset_input_buffer()

        start_time = time.perf_counter()
        print("Đang thu thập dữ liệu nhiệt độ DS18B20 (khoảng 20 giây)...")

        while len(temp_list) < SAMPLES:
            line = ser.readline().decode('utf-8', errors='ignore').strip()

            # Xử lý khi nhận chuỗi in ra từ Arduino (VD: "Nhiet do DS18B20: 28.50 °C" hoặc chứa số float)
            if "Nhiet do" in line or "°C" in line or "Temp:" in line:
                try:
                    # Trích xuất giá trị số từ chuỗi
                    for part in line.split():
                        try:
                            val = float(part.replace('°C', '').strip())
                            # Lọc giá trị hợp lệ của DS18B20 trong khoảng -10°C đến 100°C
                            if -10 <= val <= 100:
                                t = time.perf_counter() - start_time
                                temp_list.append(val)
                                time_list.append(t)
                                print(f"  [Mẫu {len(temp_list)}/{SAMPLES}] Thời gian: {t:.1f}s | Nhiệt độ: {val:.2f} °C")
                                break
                        except ValueError:
                            continue
                except Exception:
                    continue

        print("-> Thu thập hoàn tất!")

    except Exception as e:
        print(f"[LỖI] Kết nối Serial thất bại: {e}")
        print("Mẹo: Hãy đóng Serial Monitor / Plotter trong Arduino IDE trước khi chạy!")
        return None
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()

    # Lưu file CSV
    csv_file = f"ds18b20_{state_name}.csv"
    with open(csv_file, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Time_s", "Temperature_C"])
        for row in zip(time_list, temp_list):
            writer.writerow(row)
    print(f"-> Đã lưu dữ liệu vào: {csv_file}")

    return time_list, temp_list

# ===================================================================
# THỰC HIỆN 2 THỬ NGHIỆM
# ===================================================================
# 1. Trạng thái Nhiệt độ phòng
data_room = collect_temp_data("nhiet_do_phong", "Để cảm biến DS18B20 tự do trong không khí phòng")

if data_room is not None:
    # 2. Trạng thái Kẹp nách / Đo nhiệt độ cơ thể
    data_body = collect_temp_data("nuoc_lanh", "Giữ cảm biến kim loại trong nước lạnh")

    if data_body is not None:
        t_r, temp_r = data_room
        t_b, temp_b = data_body

        # ===================================================================
        # VẼ ĐỒ THỊ SO SÁNH PHỤC VỤ BÁO CÁO
        # ===================================================================
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 8))

        # Đồ thị 1: Nhiệt độ phòng
        ax1.plot(t_r, temp_r, marker='o', color='blue', linewidth=2, label='Nhiệt độ phòng (°C)')
        ax1.set_title('1. ĐO NHIỆT ĐỘ PHÒNG (ROOM TEMPERATURE - 1-WIRE)')
        ax1.set_ylabel('Nhiệt độ (°C)')
        ax1.grid(True)
        ax1.legend()

        # Đồ thị 2: Kẹp nách / Đo cơ thể
        ax2.plot(t_b, temp_b, marker='s', color='red', linewidth=2, label='Nhiệt độ cơ thể (°C)')
        ax2.set_title('2. ĐO NHIỆT ĐỘ NƯỚC LẠNH (WATER TEMPERATURE - 1-WIRE)')
        ax2.set_xlabel('Thời gian (giây)')
        ax2.set_ylabel('Nhiệt độ (°C)')
        ax2.grid(True)
        ax2.legend()

        plt.tight_layout()
        plot_filename = "ds18b20_room_vs_water_comparison.png"
        plt.savefig(plot_filename, dpi=300)
        print(f"\n-> Đã xuất đồ thị báo cáo chất lượng cao: {plot_filename}")
        plt.show()