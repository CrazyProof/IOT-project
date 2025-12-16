#!/bin/bash
# 声波测距系统启动脚本 (Linux/macOS)

echo "========================================"
echo "    声波测距系统 - 启动菜单"
echo "========================================"
echo ""
echo "请选择要启动的程序:"
echo "  1. 锚节点应用 (固定设备)"
echo "  2. 目标设备应用 (移动设备)"
echo "  3. 单机测试"
echo "  4. 数据分析工具"
echo "  5. 安装依赖"
echo "  0. 退出"
echo ""
read -p "请输入选项 (0-5): " choice

case $choice in
    1)
        echo "启动锚节点应用..."
        python3 anchor_app.py
        ;;
    2)
        echo "启动目标设备应用..."
        python3 target_app.py
        ;;
    3)
        echo "启动单机测试..."
        python3 standalone_test.py
        ;;
    4)
        echo "启动数据分析工具..."
        python3 data_analyzer.py
        ;;
    5)
        echo "安装依赖包..."
        pip3 install -r requirements.txt
        echo "安装完成！"
        ;;
    0)
        echo "退出"
        ;;
    *)
        echo "无效选项"
        ;;
esac
