import serial
import csv
import time
import matplotlib.pyplot as plt

# CẤU HÌNH CỔNG COM
PORT = 'COM7'  # Sửa lại đúng cổng COM của bạn
BAUD_RATE = 115200
SAMPLES = 800  # Thu thập 800 mẫu (8 giây ở 100Hz)

def collect_data(test_name):
    raw_list, ma_list, comp_list, time_list = [], [], [], []
    
    print(f"\n==========================================")
    print(f"BẮT ĐẦU THỬ NGHIỆM: {test_name.upper()}")
    print(f"==========================================")
    input("Chuẩn bị phần cứng xong, bấm ENTER để bắt đầu thu thập dữ liệu...")

    try:
        ser = serial.Serial(PORT, BAUD_RATE, timeout=1)
        time.sleep(2)
        ser.reset_input_buffer()
        
        start_time = time.perf_counter()
        print("Đang thu thập 800 mẫu (8 giây)...")

        while len(raw_list) < SAMPLES:
            line = ser.readline().decode('utf-8', errors='ignore').strip()
            
            # Xử lý chuỗi định dạng "Raw:...,MA:...,Comp:..."
            if "Raw:" in line and "MA:" in line and "Comp:" in line:
                try:
                    parts = line.split(',')
                    r = float(parts[0].split(':')[1])
                    m = float(parts[1].split(':')[1])
                    c = float(parts[2].split(':')[1])
                    t = time.perf_counter() - start_time

                    raw_list.append(r)
                    ma_list.append(m)
                    comp_list.append(c)
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

    # Lưu CSV
    csv_file = f"mpu6050_{test_name}.csv"
    with open(csv_file, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["Time_s", "Raw_Angle", "Moving_Average", "Complementary_Filter"])
        for row in zip(time_list, raw_list, ma_list, comp_list):
            writer.writerow(row)
    print(f"Đã lưu file: {csv_file}")

    return time_list, raw_list, ma_list, comp_list

# --- THỰC HIỆN 2 THỬ NGHIỆM ---
res_static = collect_data("dung_yen")

if res_static is not None:
    t_static, r_static, m_static, c_static = res_static

    # Tiếp tục thu thập lần 2 khi lần 1 thành công
    res_dynamic = collect_data("rung_dong")
    
    if res_dynamic is not None:
        t_dynamic, r_dynamic, m_dynamic, c_dynamic = res_dynamic
        
        # --- VẼ ĐỒ THỊ BÁO CÁO ---
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))

        # Đồ thị 1: Đứng yên
        ax1.plot(t_static, r_static, label='Góc thô Gia tốc (Raw)', color='gray', alpha=0.6, linewidth=1)
        ax1.plot(t_static, m_static, label='Moving Average (N=10)', color='blue', linewidth=1.5)
        ax1.plot(t_static, c_static, label='Complementary Filter (alpha=0.96)', color='red', linewidth=2)
        ax1.set_title('1. ĐÁNH GIÁ ĐỘ ỔN ĐỊNH KHI ĐỨNG YÊN (STATIC TEST)')
        ax1.set_xlabel('Thời gian (giây)')
        ax1.set_ylabel('Góc nghiêng (Độ)')
        ax1.grid(True)
        ax1.legend()

        # Đồ thị 2: Có Rung Động Nhẹ
        ax2.plot(t_dynamic, r_dynamic, label='Góc thô Gia tốc (Raw)', color='gray', alpha=0.6, linewidth=1)
        ax2.plot(t_dynamic, m_dynamic, label='Moving Average (N=10)', color='blue', linewidth=1.5)
        ax2.plot(t_dynamic, c_dynamic, label='Complementary Filter (alpha=0.96)', color='red', linewidth=2)
        ax2.set_title('2. ĐÁNH GIÁ ĐỘ ỔN ĐỊNH KHI CÓ RUNG ĐỘNG NHẸ (DYNAMIC TEST)')
        ax2.set_xlabel('Thời gian (giây)')
        ax2.set_ylabel('Góc nghiêng (Độ)')
        ax2.grid(True)
        ax2.legend()

        plt.tight_layout()
        plt.savefig("mpu6050_2_conditions_comparison.png", dpi=300)
        plt.show()
else:
    print("\n[LỖI] Chưa thể đọc dữ liệu. Hãy tắt Serial Monitor/Plotter trong Arduino IDE rồi chạy lại script!")