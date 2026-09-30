#!/bin/bash
# AI政策收集工具 - 启动脚本
# 使用方式: bash start.sh

echo "========================================"
echo "  🤖 AI政策收集工具"
echo "========================================"
echo ""

# 检查Python
if ! command -v python3 &>/dev/null; then
    echo "❌ 未找到 python3，请先安装 Python 3.8+"
    exit 1
fi

# 检查/安装依赖
echo "📦 检查依赖..."
pip3 install -r requirements.txt -q 2>&1 | grep -v "already satisfied"
echo "✅ 依赖检查完成"

echo ""
echo "🚀 启动服务..."
echo ""
echo "========================================"
echo "  🌐 本地访问: http://localhost:5000"
echo "  🌐 局域网访问: http://$(hostname -I 2>/dev/null | awk '{print $1}'):5000"
echo "  ⏰ 自动爬取: 每2小时"
echo "  📋 数据保留: 近7天活跃，历史数据可搜索"
echo "========================================"
echo ""

python3 app.py
