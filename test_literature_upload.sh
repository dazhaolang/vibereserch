#!/bin/bash

echo "=== 📚 文献上传解析流程测试 ==="
echo "测试时间: $(date)"
echo

# 1. 获取JWT令牌
echo "🔑 获取JWT令牌..."
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

# 2. 检查是否有测试PDF文件
if [ -f "sample.pdf" ]; then
    echo "📄 找到测试PDF文件: sample.pdf"
    FILE_SIZE=$(wc -c < sample.pdf)
    echo "文件大小: $FILE_SIZE 字节"
else
    echo "⚠️  未找到 sample.pdf 文件，创建测试PDF..."
    # 创建一个简单的文本文件作为测试
    echo "This is a test document for literature upload functionality." > test_document.txt
    echo "✅ 创建测试文档: test_document.txt"
fi

# 3. 测试文献上传端点发现
echo "🔍 测试文献相关API端点..."

# 检查文献列表端点
echo "📋 测试文献列表端点..."
RESPONSE=$(curl -s -w "HTTP_CODE:%{http_code}" \
    -H "Authorization: Bearer $TOKEN" \
    "http://154.12.50.153:8000/api/literature/list" 2>/dev/null)
echo "文献列表响应: $RESPONSE"
echo

# 检查文献上传端点
echo "📤 测试文献上传端点发现..."
UPLOAD_ENDPOINTS=(
    "/api/literature/upload"
    "/api/literature/upload/file"
    "/api/file/upload"
    "/api/upload/literature"
    "/api/project/8/literature/upload"
)

for endpoint in "${UPLOAD_ENDPOINTS[@]}"; do
    echo "测试端点: $endpoint"
    RESPONSE=$(curl -s -w "HTTP_CODE:%{http_code}" \
        -H "Authorization: Bearer $TOKEN" \
        "http://154.12.50.153:8000$endpoint" 2>/dev/null)
    echo "响应: $RESPONSE"
    echo
done

# 4. 尝试OPTIONS请求发现支持的方法
echo "🔧 使用OPTIONS请求发现支持的方法..."
for endpoint in "${UPLOAD_ENDPOINTS[@]}"; do
    echo "OPTIONS $endpoint:"
    RESPONSE=$(curl -s -X OPTIONS \
        -H "Authorization: Bearer $TOKEN" \
        -w "HTTP_CODE:%{http_code},METHODS:%{header_allow}" \
        "http://154.12.50.153:8000$endpoint" 2>/dev/null)
    echo "响应: $RESPONSE"
    echo
done

# 5. 检查Celery任务状态
echo "⚙️  检查后台任务处理状态..."
TASKS_RESPONSE=$(curl -s -w "HTTP_CODE:%{http_code}" \
    -H "Authorization: Bearer $TOKEN" \
    "http://154.12.50.153:8000/api/task/stats" 2>/dev/null)
echo "任务统计: $TASKS_RESPONSE"
echo

# 6. 检查上传目录权限
echo "📁 检查上传目录..."
if [ -d "uploads" ]; then
    echo "✅ uploads目录存在"
    echo "目录权限: $(ls -ld uploads)"
    echo "目录内容: $(ls -la uploads/ 2>/dev/null || echo '空目录')"
else
    echo "⚠️  uploads目录不存在"
fi
echo

echo "=== 文献上传测试完成 ==="
echo "📊 测试总结:"
echo "- JWT认证: 成功"
echo "- API端点发现: 完成"
echo "- 方法检测: 完成"
echo "- 目录检查: 完成"
echo
echo "⚠️  注意事项:"
echo "1. 需要确定正确的文献上传API端点"
echo "2. 可能需要multipart/form-data上传"
echo "3. 需要检查后端日志确认处理流程"