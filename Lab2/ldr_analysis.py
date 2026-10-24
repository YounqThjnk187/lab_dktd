import serial
import csv
import time
import matplotlib.pyplot as plt

# CẤU HÌNH CỔNG COM
PORT = 'COM7'       # Sửa lại đúng cổng COM của bạn
BAUD_RATE = 115200
SAMPLES = 400       # Thu thập 400 mẫu (~8 giây ở 50Hz)

def collect_ldr_data(test_name):
    raw_list, filtered_list, time_list = [], [], []
    
    print(f"\n==========================================")
    print(f"BẮT ĐẦU THỬ NGHIỆM LDR: {test_name.upper()}")
    print(f"==========================================")
    input(f"Chuẩn bị trạng thái [{test_name.upper()}], bấm ENTER để bắt đầu thu thập...")

    try:
        ser = serial.Serial(PORT, BAUD_RATE, timeout=1)
        time.sleep(2)
        ser.reset_input_buffer()
        
        start_time = time.perf_counter()
        print("Đang thu thập dữ liệu...")

        while len(raw_list) < SAMPLES:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            
            # Đọc chuỗi format "Raw:...,Filtered:..."
            if "Raw:" in line and "Filtered:" in line:
                try:
                    parts = line.split(',')
                    r = float(parts[0].split(':')[1])
                    f = float(parts[1].split(':')[1])
                    t = time.perf_counter() - start_time

                    raw_list.append(r)
                    filtered_list.append(f)
                    time_list.append(t)
                except (IndexError, ValueError):
                    continue

        print("Thu thập xong!")

    except Exception as e:
        print(f"Lỗi kết nối Serial: {e}")
        return None
    finally:
        if 'ser' in locals() and ser.is_open:
            ser.close()

    # Lưu file CSV
    csv_file = f"ldr_{test_name}.csv"
    with open(csv_file, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Time_s", "LDR_Raw", "LDR_Filtered"])
        for row in zip(time_list, raw_list, filtered_list):
            writer.writerow(row)
    print(f"Đã lưu CSV: {csv_file}")

    return time_list, raw_list, filtered_list

# --- THỰC HIỆN 2 THỬ NGHIỆM ---
# Thử nghiệm 1: Trạng thái Chiếu sáng (Mở đèn/Chiếu đèn pin)
res_light = collect_ldr_data("chieu_sang")

if res_light is not None:
    t_light, r_light, f_light = res_light

    # Thử nghiệm 2: Trạng thái Che tối (Dùng tay hoặc vật che kín LDR)
    res_dark = collect_ldr_data("che_toi")
    
    if res_dark is not None:
        t_dark, r_dark, f_dark = res_dark
        
        # --- VẼ ĐỒ THỊ BÁO CÁO ---
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8))

        # Đồ thị 1: Chiếu sáng
        ax1.plot(t_light, r_light, label='LDR Raw (Thô)', color='orange', alpha=0.5, linewidth=1)
        ax1.plot(t_light, f_light, label='LDR Filtered (Moving Average N=10)', color='red', linewidth=2)
        ax1.set_title('1. ĐÁNH GIÁ TÍN HIỆU LDR KHI CHIẾU SÁNG (LIGHT TEST)')
        ax1.set_xlabel('Thời gian (giây)')
        ax1.set_ylabel('Giá trị ADC (0 - 4095)')
        ax1.grid(True)
        ax1.legend()

        # Đồ thị 2: Che tối
        ax2.plot(t_dark, r_dark, label='LDR Raw (Thô)', color='gray', alpha=0.5, linewidth=1)
        ax2.plot(t_dark, f_dark, label='LDR Filtered (Moving Average N=10)', color='blue', linewidth=2)
        ax2.set_title('2. ĐÁNH GIÁ TÍN HIỆU LDR KHI CHE TỐI (DARK TEST)')
        ax2.set_xlabel('Thời gian (giây)')
        ax2.set_ylabel('Giá trị ADC (0 - 4095)')
        ax2.grid(True)
        ax2.legend()

        plt.tight_layout()
        plt.savefig("ldr_light_vs_dark_comparison.png", dpi=300)
        plt.show()
else:
    print("\n[LỖI] Không thể mở cổng Serial. Đảm bảo đã tắt Serial Plotter/Monitor trong Arduino IDE!")