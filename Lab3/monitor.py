import serial
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation

# Cấu hình cổng COM kết nối ESP32 (Thay COM7 bằng cổng thực tế của bạn)
PORT = 'COM7'
BAUD_RATE = 115200

x_data, target_data, current_data = [], [], []

ser = serial.Serial(PORT, BAUD_RATE, timeout=0.1)

fig, ax = plt.subplots(figsize=(10, 5))
line_target, = ax.plot([], [], 'r--', label='Tốc độ Đặt (Target)')
line_current, = ax.plot([], [], 'b-', label='Tốc độ Thực tế (Current)')
ax.set_ylim(0, 400)
ax.set_xlim(0, 200)
ax.set_xlabel('Thời gian mẫu')
ax.set_ylabel('Vận tốc (Ticks/s)')
ax.set_title('Giám sát Vòng lặp PID Vận tốc Động cơ DC (Live-plot)')
ax.legend()
ax.grid(True)

def update(frame):
    line = ser.readline().decode('utf-8', errors='ignore').strip()
    if "Target:" in line and "Current:" in line:
        try:
            parts = line.split(',')
            target = float(parts[0].split(':')[1])
            current = float(parts[1].split(':')[1])
            
            x_data.append(len(x_data))
            target_data.append(target)
            current_data.append(current)
            
            # Giữ lại 200 điểm gần nhất trên đồ thị
            if len(x_data) > 200:
                x_data.pop(0)
                target_data.pop(0)
                current_data.pop(0)
                
            line_target.set_data(x_data, target_data)
            line_current.set_data(x_data, current_data)
            ax.set_xlim(x_data[0], x_data[-1] + 10)
        except Exception as e:
            pass
    return line_target, line_current

ani = FuncAnimation(fig, update, interval=10, blit=True)
plt.show()
ser.close()