#!/bin/bash

echo "=== 🔄 负载与断网恢复测试 ==="
echo "测试时间: $(date)"
echo

# 1. 获取JWT令牌
echo "📡 获取JWT令牌..."
TOKEN_RESPONSE=$(curl -s -X POST "http://154.12.50.153:8000/api/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "testpass123"}')

TOKEN=$(echo "$TOKEN_RESPONSE" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
    echo "❌ 无法获取JWT令牌"
    echo "响应: $TOKEN_RESPONSE"
    exit 1
fi

echo "✅ JWT令牌获取成功 (长度: ${#TOKEN} 字符)"
echo

# 2. 并发API调用测试
echo "🔥 并发API调用测试 (5个并发请求)..."
echo "测试端点: /api/user/profile"

for i in {1..5}; do
    {
        echo "请求 $i 开始: $(date '+%H:%M:%S.%3N')"
        RESPONSE=$(curl -s -w "HTTP_CODE:%{http_code},TIME:%{time_total}" \
            -H "Authorization: Bearer $TOKEN" \
            "http://154.12.50.153:8000/api/user/profile" 2>/dev/null)
        echo "请求 $i 完成: $(date '+%H:%M:%S.%3N') - $RESPONSE"
    } &
done

# 等待所有后台任务完成
wait
echo "✅ 并发请求测试完成"
echo

# 3. 项目列表并发测试
echo "📋 项目列表并发测试 (3个并发请求)..."
for i in {1..3}; do
    {
        echo "项目请求 $i 开始: $(date '+%H:%M:%S.%3N')"
        RESPONSE=$(curl -s -w "HTTP_CODE:%{http_code},TIME:%{time_total}" \
            -H "Authorization: Bearer $TOKEN" \
            "http://154.12.50.153:8000/api/project/list" 2>/dev/null)
        echo "项目请求 $i 完成: $(date '+%H:%M:%S.%3N') - $RESPONSE"
    } &
done

wait
echo "✅ 项目列表并发测试完成"
echo

# 4. WebSocket连接负载测试
echo "🔌 WebSocket连接状态检查..."
echo "后端日志中的WebSocket连接数量:"
echo "注意: 检查后端日志中是否显示多个并发WebSocket连接"
echo

# 5. 系统资源监控
echo "💻 系统资源使用情况:"
echo "内存使用:"
free -h | head -2
echo
echo "CPU负载:"
uptime
echo

echo "=== 负载测试完成 ==="
echo "📊 测试总结:"
echo "- 并发API请求: 完成"
echo "- 项目列表请求: 完成"
echo "- WebSocket连接: 需要观察后端日志"
echo "- 系统资源: 已记录"
echo
echo "⚠️  断网恢复测试需要手动执行:"
echo "1. 暂时断开网络连接 10 秒"
echo "2. 恢复网络连接"
echo "3. 观察WebSocket是否自动重连"
echo "4. 检查消息队列是否正常重发"