import asyncio
import json
import logging
import os
from flask import Flask, render_template, request, jsonify
from flask import request
from bleak import BleakScanner, BleakClient
import json
import threading
import uuid

app = Flask(__name__)

# 全局变量
connected_device = None
connected_client = None
found_devices = []
device_services = []
scan_thread = None
is_scanning = False

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# 主页路由 - 传统BLE版本
@app.route('/')
def index():
    return render_template('ble_tool.html')


# Bluetooth支持测试页面
@app.route('/bluetooth_test')
def bluetooth_test():
    return render_template('bluetooth_test.html')


# 扫描BLE设备
@app.route('/scan', methods=['POST'])
def scan_devices():
    global scan_thread, is_scanning

    if is_scanning:
        return jsonify({'status': 'error', 'message': '扫描已在进行中'}), 400

    # 在单独的线程中运行扫描
    scan_thread = threading.Thread(target=run_scan)
    scan_thread.start()

    return jsonify({'status': 'success', 'message': '开始扫描设备'})


# 获取扫描结果
@app.route('/devices', methods=['GET'])
def get_devices():
    global found_devices
    devices_data = []
    for device in found_devices:
        devices_data.append({
            'name': device.name or "N/A",
            'address': device.address,
            'rssi': getattr(device, 'rssi', 'N/A')
        })
    return jsonify({'devices': devices_data})


# 连接设备
@app.route('/connect', methods=['POST'])
def connect_device():
    global connected_device, connected_client

    data = request.get_json()
    device_address = data.get('address')

    if not device_address:
        return jsonify({'status': 'error', 'message': '设备地址不能为空'}), 400

    # 在单独的线程中运行连接
    connect_thread = threading.Thread(target=run_connect, args=(device_address,))
    connect_thread.start()

    return jsonify({'status': 'success', 'message': '正在连接设备'})


# 断开连接
@app.route('/disconnect', methods=['POST'])
def disconnect_device():
    global connected_device, connected_client

    if connected_client and connected_client.is_connected:
        disconnect_thread = threading.Thread(target=run_disconnect)
        disconnect_thread.start()
        return jsonify({'status': 'success', 'message': '正在断开连接'})
    else:
        return jsonify({'status': 'error', 'message': '当前没有连接的设备'}), 400


# 获取服务和特征
@app.route('/services', methods=['GET'])
def get_services():
    global connected_client, device_services

    if not connected_client or not connected_client.is_connected:
        return jsonify({'status': 'error', 'message': '设备未连接'}), 400

    # 如果已经获取过服务信息，直接返回
    if device_services:
        return jsonify({'status': 'success', 'services': device_services})

    # 在单独的线程中获取服务
    services_thread = threading.Thread(target=run_get_services)
    services_thread.start()

    return jsonify({'status': 'success', 'message': '正在获取服务信息'})


# 为指定特征启动通知
@app.route('/start_notify', methods=['POST'])
def start_notify():
    global connected_client

    if not connected_client or not connected_client.is_connected:
        return jsonify({'status': 'error', 'message': '设备未连接'}), 400

    data = request.get_json()
    characteristic_uuid = data.get('characteristic_uuid')

    if not characteristic_uuid:
        return jsonify({'status': 'error', 'message': '特征UUID不能为空'}), 400

    # 在单独的线程中启动通知
    notify_thread = threading.Thread(
        target=run_start_notifications,
        args=(characteristic_uuid,)
    )
    notify_thread.start()

    return jsonify({'status': 'success', 'message': '正在启动通知监听'})


# 发送数据
@app.route('/send', methods=['POST'])
def send_data():
    global connected_client

    data = request.get_json()
    service_uuid = data.get('service_uuid')
    characteristic_uuid = data.get('characteristic_uuid')
    text_data = data.get('text_data')
    data_format = data.get('format', 'text')  # 'text' 或 'hex'

    if not all([service_uuid, characteristic_uuid, text_data]):
        return jsonify({'status': 'error', 'message': '缺少必要参数'}), 400

    if not connected_client or not connected_client.is_connected:
        return jsonify({'status': 'error', 'message': '设备未连接'}), 400

    # 在单独的线程中发送数据
    send_thread = threading.Thread(
        target=run_send_data,
        args=(service_uuid, characteristic_uuid, text_data, data_format)
    )
    send_thread.start()

    return jsonify({'status': 'success', 'message': '正在发送数据'})


# 健康检查端点
@app.route('/health')
def health():
    return jsonify({'status': 'ok', 'message': '服务运行正常'})


# 异步运行扫描的函数
def run_scan():
    global found_devices, is_scanning

    # 黑名单关键词
    BLACKLISTED_KEYWORDS = ["Unknown", "NULL"]

    is_scanning = True
    try:
        # 使用asyncio运行异步函数，并获取RSSI信息
        devices_with_adv = asyncio.run(BleakScanner.discover(timeout=5.0, return_adv=True))
        # 提取设备对象并添加RSSI信息
        found_devices = []

        # 定义设备包装类
        class DeviceWithRSSI:
            def __init__(self, device, rssi):
                self.name = device.name
                self.address = device.address
                self.details = device.details
                self.rssi = rssi

        for addr, (device, adv_data) in devices_with_adv.items():
            device_name = device.name or ""

            # 更严格的过滤条件：
            # 1. 设备名称存在且不为空
            # 2. 设备名称长度大于2（过滤掉过于简短的无效名称）
            # 3. 设备名称不是"N/A"
            # 4. 不包含黑名单关键词
            if (device_name and
                    len(device_name.strip()) > 2 and
                    device_name != "N/A" and
                    not any(keyword in device_name for keyword in BLACKLISTED_KEYWORDS)):
                found_devices.append(DeviceWithRSSI(device, adv_data.rssi))

        logger.info(f"发现 {len(found_devices)} 个设备")
    except Exception as e:
        logger.error(f"扫描设备时出错: {str(e)}")
    finally:
        is_scanning = False


# 异步运行连接的函数
def run_connect(device_address):
    global connected_device, connected_client

    try:
        # 创建客户端并连接
        connected_client = BleakClient(device_address)
        asyncio.run(connected_client.connect())
        connected_device = device_address
        logger.info(f"成功连接到设备: {device_address}")
    except Exception as e:
        logger.error(f"连接设备时出错: {str(e)}")
        connected_client = None
        connected_device = None


# 异步运行断开连接的函数
def run_disconnect():
    global connected_device, connected_client

    try:
        if connected_client and connected_client.is_connected:
            asyncio.run(connected_client.disconnect())
            logger.info("设备已断开连接")
        else:
            logger.warning("没有连接的设备")
    except Exception as e:
        logger.error(f"断开连接时出错: {str(e)}")
    finally:
        connected_client = None
        connected_device = None
        device_services = []  # 清空服务信息


# 异步获取服务信息
def run_get_services():
    global connected_client

    try:
        # 等待一段时间确保服务发现完成
        import time
        time.sleep(2)

        # 直接访问已发现的服务
        services = connected_client.services

        services_data = []
        for service in services:
            service_info = {
                'uuid': str(service.uuid),
                'description': service.description,
                'characteristics': []
            }
            for char in service.characteristics:
                char_info = {
                    'uuid': str(char.uuid),
                    'description': char.description,
                    'properties': char.properties
                }
                service_info['characteristics'].append(char_info)
            services_data.append(service_info)

        # 将服务信息保存到全局变量，供后续使用
        global device_services
        device_services = services_data

        logger.info(f"获取到 {len(services_data)} 个服务")
        for service in services_data:
            logger.info(f"服务: {service['uuid']}")
            for char in service['characteristics']:
                logger.info(f"  特征: {char['uuid']}, 属性: {char['properties']}")
    except Exception as e:
        logger.error(f"获取服务信息时出错: {str(e)}")


# 异步发送数据
def run_send_data(service_uuid, characteristic_uuid, text_data, data_format):
    global connected_client

    try:
        # 根据格式转换数据
        if data_format == 'hex':
            # 将十六进制字符串转换为字节
            byte_data = bytes.fromhex(text_data)
        else:
            # 将文本转换为UTF-8字节
            byte_data = text_data.encode('utf-8')

        # 发送数据
        asyncio.run(connected_client.write_gatt_char(characteristic_uuid, byte_data))
        logger.info(f"成功发送数据到特征 {characteristic_uuid}")
    except ValueError as e:
        logger.error(f"数据格式错误: {str(e)}")
    except Exception as e:
        logger.error(f"发送数据时出错: {str(e)}")


# 异步启动通知
def run_start_notifications(characteristic_uuid):
    global connected_client

    try:
        def notification_handler(sender, data):
            # 在单独的线程中处理通知，避免阻塞
            threading.Thread(target=handle_notification, args=(sender, data)).start()

        asyncio.run(connected_client.start_notify(characteristic_uuid, notification_handler))
        logger.info(f"已启动对特征 {characteristic_uuid} 的通知监听")
    except Exception as e:
        logger.error(f"启动通知时出错: {str(e)}")


# 处理通知数据
def handle_notification(sender, data):
    try:
        # 尝试解码为UTF-8文本
        try:
            text_data = data.decode('utf-8')
            logger.info(f"收到来自特征 {sender} 的通知: {text_data}")
        except UnicodeDecodeError:
            # 如果无法解码为文本，则以十六进制显示
            hex_data = data.hex()
            logger.info(f"收到来自特征 {sender} 的通知 (hex): {hex_data}")
    except Exception as e:
        logger.error(f"处理通知数据时出错: {str(e)}")


if __name__ == '__main__':
    # 从环境变量获取端口，默认为12346
    port = int(os.environ.get('PORT', 12346))
    app.run(debug=False, host='127.0.0.1', port=port)