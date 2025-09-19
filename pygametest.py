import pygame
import time
import sys

def main():
    # 初始化 pygame
    pygame.init()
    pygame.joystick.init()
    
    if pygame.joystick.get_count() == 0:
        print("未检测到手柄连接")
        pygame.quit()
        sys.exit()
    
    joystick = pygame.joystick.Joystick(0)
    joystick.init()
    
    print(f"检测到手柄: {joystick.get_name()}")
    print("按下 Ctrl+C 退出程序")
    print("-" * 50)
    
    # 按钮映射表
    button_names = {
        0: "A按钮",
        1: "B按钮", 
        2: "X按钮",
        3: "Y按钮",
        4: "RB(右肩键)",
        5: "LB(左肩键)",
        6: "SELECT(选择键)",
        7: "START(开始键)",
        8: "左摇杆按下",
        9: "右摇杆按下"
    }
    
    # 轴映射表
    axis_names = {
        0: "左摇杆 X轴",
        1: "左摇杆 Y轴",
        2: "右摇杆 X轴", 
        3: "右摇杆 Y轴",
        4: "左扳机键",
        5: "右扳机键"
    }
    
    # 存储上一次的状态
    prev_buttons = [False] * joystick.get_numbuttons()
    prev_axes = [0.0] * joystick.get_numaxes()
    prev_hats = [(0, 0)] * joystick.get_numhats()
    
    try:
        while True:
            # 处理事件队列
            pygame.event.pump()
            
            # 检查按钮变化
            for i in range(joystick.get_numbuttons()):
                current = joystick.get_button(i)
                if current != prev_buttons[i]:
                    button_name = button_names.get(i, f"按钮{i}")
                    if current:
                        print(f"按下: {button_name}")
                    else:
                        print(f"释放: {button_name}")
                    prev_buttons[i] = current
            
            # 检查轴变化（只在有显著变化时输出）
            for i in range(joystick.get_numaxes()):
                current = joystick.get_axis(i)
                # 只有当变化超过阈值时才输出
                if abs(current - prev_axes[i]) > 0.1:
                    axis_name = axis_names.get(i, f"轴{i}")
                    # 对于扳机键（轴4和5），通常默认值是-1，我们转换为0-1的范围
                    if i in [4, 5]:  # 扳机键
                        # 将扳机键值从[-1, 1]映射到[0, 1]
                        normalized_value = (current + 1) / 2
                        if normalized_value > 0.1:  # 忽略很小的值
                            print(f"{axis_name}: {normalized_value:.3f}")
                    else:  # 摇杆
                        if abs(current) > 0.1:  # 忽略接近中心的小值
                            print(f"{axis_name}: {current:.3f}")
                    prev_axes[i] = current
            
            # 检查方向键变化
            for i in range(joystick.get_numhats()):
                current = joystick.get_hat(i)
                if current != prev_hats[i]:
                    # 解释方向键的值
                    hat_directions = {
                        (0, 0): "中心",
                        (0, 1): "上",
                        (1, 1): "右上",
                        (1, 0): "右", 
                        (1, -1): "右下",
                        (0, -1): "下",
                        (-1, -1): "左下",
                        (-1, 0): "左",
                        (-1, 1): "左上"
                    }
                    direction = hat_directions.get(current, str(current))
                    print(f"方向键: {direction}")
                    prev_hats[i] = current
            
            time.sleep(0.02)  # 降低检查频率
            
    except KeyboardInterrupt:
        print("\n程序已退出")
    finally:
        pygame.quit()

if __name__ == "__main__":
    main()