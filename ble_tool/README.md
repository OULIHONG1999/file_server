# BLE工具

这是一个基于Python和Flask的蓝牙低功耗(BLE)设备扫描和管理工具。该工具提供了两种操作模式：

1. **后端模式**：使用Python的Bleak库在服务器端扫描和连接BLE设备
2. **前端模式**：使用Web Bluetooth API在浏览器中直接访问本地蓝牙设备

## 功能特点

- 扫描附近的BLE设备
- 连接和断开BLE设备
- 浏览设备的服务和特征
- 发送数据到BLE设备
- 接收来自BLE设备的通知

## 安装依赖

```bash
pip install -r requirements.txt
```

## 运行应用

```bash
python app.py
```

应用将在 `http://127.0.0.1:12346` 上运行

## 访问界面

- 后端模式（使用服务器蓝牙）: `http://127.0.0.1:12346/`
- 前端模式（使用本地浏览器蓝牙）: `http://127.0.0.1:12346/web`

## 打包为可执行文件

```bash
pyinstaller --noconfirm ble_tool.spec
```

生成的可执行文件将位于 `dist/` 目录中。