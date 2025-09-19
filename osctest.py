from pythonosc import udp_client
from pythonosc import dispatcher
from pythonosc import osc_server
import threading
import time

# 配置参数 - 确保这些与VRChat设置中的一致
VRC_IP = "127.0.0.1"          # VRChat所在机器的IP，通常是本机
VRC_OSC_IN_PORT = 9000        # VRChat的输入端口(默认)
LISTEN_IP = "127.0.0.1"       # 本机IP
LISTEN_PORT = 9001            # 监听端口(默认)

# 创建发送客户端（用于向VRChat发送请求）
sender = udp_client.SimpleUDPClient(VRC_IP, VRC_OSC_IN_PORT)

# 创建分发器来处理收到的OSC消息
disp = dispatcher.Dispatcher()

# 存储最新相机数据的变量
latest_camera_data = {
    "position": (0, 0, 0),
    "rotation": (0, 0, 0, 1),  # 四元数 (x, y, z, w)
    "last_update": 0
}

# 处理 /usercamera/Pose 响应的函数
def handle_camera_pose(unused_addr, *args):
    if len(args) == 6:
        # 假设前三个是位置 (x, y, z)，后三个是欧拉角 (x, y, z) 或 (pitch, yaw, roll)
        latest_camera_data["position"] = (args[0], args[1], args[2])
        latest_camera_data["rotation_euler"] = (args[3], args[4], args[5])
        latest_camera_data["last_update"] = time.time()
        
        print(f"\n相机位置: X={args[0]:.3f}, Y={args[1]:.3f}, Z={args[2]:.3f}")
        print(f"相机旋转(欧拉角): X={args[3]:.4f}, Y={args[4]:.4f}, Z={args[5]:.4f}")
    else:
        print(f"收到意外格式的相机数据，参数个数：{len(args)}: {args}")

# 处理其他可能的消息
def handle_default(unused_addr, *args):
    print(f"收到未知消息: {unused_addr} - {args}")

# 将处理函数绑定到地址
disp.map("/usercamera/Pose", handle_camera_pose)
disp.set_default_handler(handle_default)

# 创建接收服务器（用于监听VRChat发回的数据）
server = osc_server.ThreadingOSCUDPServer((LISTEN_IP, LISTEN_PORT), disp)
server_thread = threading.Thread(target=server.serve_forever)
server_thread.daemon = True

def start_osc_server():
    """启动OSC服务器"""
    try:
        print(f"启动OSC监听服务器于 {LISTEN_IP}:{LISTEN_PORT}")
        server_thread.start()
        return True
    except Exception as e:
        print(f"启动服务器时出错: {e}")
        return False

def request_camera_data():
    """向VRChat请求相机数据"""
    try:
        # 发送请求获取相机位姿
        # 注意: 发送None或空值来请求数据
        sender.send_message("/usercamera/Pose", None)
        print("已发送相机数据请求")
        return True
    except Exception as e:
        print(f"发送请求时出错: {e}")
        return False

def enable_camera():
    """确保相机已启用（设置为照片模式）"""
    try:
        sender.send_message("/usercamera/Mode", 1)  # 1 = 照片模式
        print("已尝试启用相机（照片模式）")
        return True
    except Exception as e:
        print(f"启用相机时出错: {e}")
        return False

def main():
    """主函数"""
    print("=" * 50)
    print("VRChat OSC相机数据获取工具")
    print("=" * 50)
    
    # 启动OSC服务器
    if not start_osc_server():
        return
    
    # 等待一秒让服务器完全启动
    time.sleep(1)
    
    # 启用相机
    enable_camera()
    
    # 初始请求
    request_camera_data()
    
    print("\n正在监听相机数据... 按Ctrl+C停止")
    print("确保:")
    print("1. VRChat正在运行")
    print("2. VRChat设置中的OSC已启用")
    print("3. VRChat的OSC输入端口设置为9000")
    print("4. VRChat的OSC输出端口设置为9001")
    
    try:
        # 主循环 - 定期请求数据
        request_interval = 5  # 每5秒请求一次
        last_request_time = time.time()
        
        while True:
            current_time = time.time()
            
            # 定期请求新数据
            if current_time - last_request_time > request_interval:
                request_camera_data()
                last_request_time = current_time
                
                # 显示数据年龄
                data_age = current_time - latest_camera_data["last_update"]
                if data_age > request_interval:
                    print(f"\n警告: 已{data_age:.1f}秒未收到相机数据")
                else:
                    print(f"\n数据更新于{data_age:.1f}秒前")
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n正在关闭...")
    finally:
        server.shutdown()
        print("已关闭OSC服务器")

if __name__ == "__main__":
    main()