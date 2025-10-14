import webview
import threading
import time
import sys
import os

# 获取当前执行文件的目录
if getattr(sys, 'frozen', False):
    # 如果是打包后的exe文件
    application_path = os.path.dirname(sys.executable)
else:
    # 如果是Python脚本
    application_path = os.path.dirname(os.path.abspath(__file__))

# 将项目路径添加到Python路径中
sys.path.append(application_path)

# 直接导入Flask应用而不是动态导入
try:
    # 尝试直接导入app模块
    import app
except ImportError:
    # 如果直接导入失败，则尝试动态导入
    # 构造app.py的路径
    app_path = os.path.join(application_path, 'app.py')
    
    # 动态导入Flask应用
    import importlib.util
    spec = importlib.util.spec_from_file_location("app", app_path)
    app_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(app_module)
    app = app_module.app

import logging

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def start_server():
    """在单独的线程中启动Flask服务器"""
    app.app.run(host='127.0.0.1', port=12346, debug=False, use_reloader=False)

def main():
    # 在后台线程中启动Flask服务器
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # 等待服务器启动
    time.sleep(2)
    
    # 创建PyWebView窗口
    window = webview.create_window(
        "BLE工具",
        "http://127.0.0.1:12346/",
        width=1200,
        height=800,
        resizable=True,
        min_size=(800, 600)
    )
    
    # 启动GUI应用
    webview.start(debug=False)

if __name__ == '__main__':
    main()