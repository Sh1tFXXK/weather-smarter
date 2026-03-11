# Windows 快速启动脚本
@echo off
chcp 65001 > nul
cls

echo.
echo ╔════════════════════════════════════════════════╗
echo ║   天气智能服务系统 - 快速启动                   ║
echo ║   Weather Smart Service System                 ║
echo ╚════════════════════════════════════════════════╝
echo.

REM 检查Python是否安装
python --version > nul 2>&1
if errorlevel 1 (
    echo ❌ 错误: 未检测到Python，请先安装Python 3.8+
    pause
    exit /b 1
)

REM 创建虚拟环境
if not exist venv (
    echo 📦 正在创建虚拟环境...
    python -m venv venv
    if errorlevel 1 (
        echo ❌ 虚拟环境创建失败
        pause
        exit /b 1
    )
    echo ✓ 虚拟环境创建成功
) else (
    echo ✓ 虚拟环境已存在
)

REM 激活虚拟环境
echo.
echo 🔌 正在激活虚拟环境...
call venv\Scripts\activate.bat

REM 安装依赖
echo.
echo 📚 正在安装依赖包...
pip install -r requirements.txt -q
if errorlevel 1 (
    echo ❌ 依赖安装失败
    pause
    exit /b 1
)
echo ✓ 依赖安装完成

REM 启动应用
echo.
echo 🚀 正在启动应用...
echo.
echo ════════════════════════════════════════════════
echo   应用已启动！请在浏览器中打开:
echo   🌐 http://localhost:5000
echo ════════════════════════════════════════════════
echo.

python app.py

pause
