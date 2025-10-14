@echo off
chcp 65001 >nul
echo 安装依赖...
pip install -r requirements.txt

echo 打包可执行文件...
pyinstaller --noconfirm ble_tool.spec

echo.
echo 打包完成！可执行文件位于 dist\ble_tool.exe
echo.

pause