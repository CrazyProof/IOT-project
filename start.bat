@echo off
chcp 65001 >nul
echo ========================================
echo     声波测距系统 - 启动菜单
echo ========================================
echo.
echo 请选择要启动的程序:
echo   1. 锚节点应用 (固定设备)
echo   2. 目标设备应用 (移动设备)
echo   3. 单机测试
echo   4. 数据分析工具
echo   5. 安装依赖
echo   0. 退出
echo.
set /p choice=请输入选项 (0-5): 

if "%choice%"=="1" goto anchor
if "%choice%"=="2" goto target
if "%choice%"=="3" goto standalone
if "%choice%"=="4" goto analyzer
if "%choice%"=="5" goto install
if "%choice%"=="0" goto end

echo 无效选项，请重新运行
goto end

:anchor
echo 启动锚节点应用...
python anchor_app.py
goto end

:target
echo 启动目标设备应用...
python target_app.py
goto end

:standalone
echo 启动单机测试...
python standalone_test.py
goto end

:analyzer
echo 启动数据分析工具...
python data_analyzer.py
goto end

:install
echo 安装依赖包...
pip install -r requirements.txt
echo 安装完成！
pause
goto end

:end
