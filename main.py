import asyncio
import json
import logging
from pythonosc import udp_client
from tornado import web, ioloop, websocket
import os
import time

# --- 配置 ---
HTTP_PORT = 8888
OSC_IP = "127.0.0.1"  # 修改为目标OSC服务器IP
OSC_PORT = 9000        # 修改为目标OSC服务器端口
# 新增配置：限制发送到OSC的频率 (秒)
OSC_SEND_INTERVAL = 1.0 / 60.0 # 例如，限制为每秒最多60次

# --- 初始化 ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# OSC客户端
osc_client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)

# 内存中存储相机参数 (包含范围)
camera_params = {
    "/usercamera/Zoom": {"value": 45.0, "min": 20.0, "max": 150.0},
    "/usercamera/Exposure": {"value": 0.0, "min": -10.0, "max": 4.0},
    "/usercamera/FocalDistance": {"value": 1.5, "min": 0.0, "max": 10.0},
    "/usercamera/Aperture": {"value": 15.0, "min": 1.4, "max": 32.0},
    "/usercamera/FlySpeed": {"value": 3.0, "min": 0.1, "max": 15.0},
    "/usercamera/TurnSpeed": {"value": 1.0, "min": 0.1, "max": 5.0},
    "/usercamera/SmoothingStrength": {"value": 5.0, "min": 0.1, "max": 10.0},
    "/usercamera/PhotoRate": {"value": 1.0, "min": 0.1, "max": 2.0},
    "/usercamera/Duration": {"value": 2.0, "min": 0.1, "max": 60.0},
}

# 存储所有活跃的WebSocket连接
websocket_connections = set()

# --- 读取HTML文件 ---
def get_html_content():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        logger.error(f"找不到文件: {html_path}")
        return "<h1>错误：index.html 文件未找到</h1>"
    except Exception as e:
        logger.error(f"读取 index.html 出错: {e}")
        return "<h1>读取页面出错</h1>"

INDEX_HTML = get_html_content()

# --- Tornado Handlers ---

class MainHandler(web.RequestHandler):
    """处理根路径请求，提供HTML控制页面"""
    def get(self):
        self.write(INDEX_HTML)

class WebSocketHandler(websocket.WebSocketHandler):
    """处理WebSocket连接"""
    def initialize(self):
        # 为每个连接实例化一个字典来存储节流相关数据
        self.osc_send_timers = {} # {address: IOLoop.call_later handle}
        self.pending_osc_values = {} # {address: value}

    def open(self):
        logger.info("WebSocket opened")
        websocket_connections.add(self)

    def send_osc_throttled(self, osc_address, new_value):
        """实际发送OSC消息的函数，由定时器调用"""
        # 检查值是否已更新（避免发送未改变的值）
        if camera_params[osc_address]["value"] != new_value:
            camera_params[osc_address]["value"] = new_value
            osc_client.send_message(osc_address, float(new_value))
            logger.debug(f"Sent OSC (throttled): {osc_address} -> {new_value}")
        
        # 清理定时器和待发送值
        self.osc_send_timers.pop(osc_address, None)
        self.pending_osc_values.pop(osc_address, None)

    def on_message(self, message):
        try:
            data = json.loads(message)
            osc_address = data.get("address")
            delta = data.get("delta")

            if osc_address in camera_params:
                param_info = camera_params[osc_address]
                current_value = param_info["value"]
                min_val = param_info["min"]
                max_val = param_info["max"]

                sensitivity = (max_val - min_val) / 500.0
                change = delta * sensitivity
                # 计算新值，但暂不应用
                new_value = current_value - change 

                limit_reached = None
                # 检查边界
                if new_value <= min_val and current_value == min_val:
                    limit_reached = "min"
                elif new_value >= max_val and current_value == max_val:
                    limit_reached = "max"
                else:
                    # 限制在范围内
                    new_value = max(min_val, min(max_val, new_value))
                    
                    # 不立即发送，而是进行节流处理
                    # 1. 更新待发送的值
                    self.pending_osc_values[osc_address] = new_value
                    
                    # 2. 如果没有为这个地址设置定时器，则设置一个
                    if osc_address not in self.osc_send_timers:
                        # 使用 IOLoop.call_later 来延迟发送
                        timer_handle = ioloop.IOLoop.current().call_later(
                            OSC_SEND_INTERVAL, 
                            lambda: self.send_osc_throttled(osc_address, self.pending_osc_values.get(osc_address, new_value))
                        )
                        self.osc_send_timers[osc_address] = timer_handle
                    # 如果已有定时器，则只需更新 pending_osc_values，
                    # 定时器到期时会发送最新的值

                # 如果达到极限，发送通知（这部分不需要节流）
                if limit_reached:
                    limit_message = json.dumps({
                        "address": osc_address,
                        "limit": limit_reached
                    })
                    self.write_message(limit_message)

            else:
                logger.warning(f"Unknown OSC address: {osc_address}")

        except json.JSONDecodeError:
            logger.error("Received invalid JSON message")
        except Exception as e:
            logger.error(f"Error processing message: {e}", exc_info=True)

    def on_close(self):
        logger.info("WebSocket closed")
        # 清理连接相关的定时器
        for timer_handle in self.osc_send_timers.values():
             # 尝试取消定时器，如果已经执行则忽略
            ioloop.IOLoop.current().remove_timeout(timer_handle) 
        self.osc_send_timers.clear()
        self.pending_osc_values.clear()
        websocket_connections.discard(self)

class ParamsHandler(web.RequestHandler):
    """API端点，用于获取当前参数状态"""
    def get(self):
        # 返回参数的深拷贝或转换，避免直接暴露内部结构
        # 这里简单处理，实际可能需要更安全的序列化
        response_data = {k: v.copy() for k, v in camera_params.items()}
        self.write(json.dumps(response_data))

# --- 应用启动 ---
def make_app():
    # 注意：WebSocketHandler 需要 initialize 方法时，传递参数给 initialize
    # 但这里我们不需要传递额外参数给 initialize，所以直接传递类
    return web.Application([
        (r"/", MainHandler),
        (r"/ws", WebSocketHandler), # Tornado 会自动调用 initialize()
        (r"/params", ParamsHandler),
    ], debug=True)

if __name__ == "__main__":
    app = make_app()
    app.listen(HTTP_PORT)
    logger.info(f"Server started at http://localhost:{HTTP_PORT}")
    logger.info(f"Sending OSC to {OSC_IP}:{OSC_PORT}")
    logger.info(f"OSC send throttled to max ~{1.0/OSC_SEND_INTERVAL:.0f} Hz per parameter")
    ioloop.IOLoop.current().start()



