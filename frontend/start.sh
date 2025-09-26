#!/bin/bash

# 前端启动脚本

echo "🚀 启动科研文献智能分析平台前端..."

# 检查是否在正确的目录
if [ ! -f "package.json" ]; then
    echo "❌ 错误：请在frontend目录下运行此脚本"
    exit 1
fi

# 检查node_modules是否存在
if [ ! -d "node_modules" ]; then
    echo "📦 安装依赖包..."
    npm install
    if [ $? -ne 0 ]; then
        echo "❌ 依赖安装失败"
        exit 1
    fi
fi

# 检查后端服务是否运行
BACKEND_URL=${BACKEND_URL:-http://localhost:8000}

echo "🔍 检查后端服务 (${BACKEND_URL})..."
curl -s "${BACKEND_URL}/healthz" > /dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "⚠️  警告：后端服务未运行在 ${BACKEND_URL}"
    echo "请先启动后端服务：cd .. && uvicorn app.main:app --host 0.0.0.0 --port 8000"
    read -p "是否继续启动前端？(y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo "✅ 启动开发服务器..."
echo "📱 访问地址：http://localhost:3000"
echo "📱 研究工作台：http://localhost:3000/workspace"
echo ""

# 启动开发服务器
npm run dev
