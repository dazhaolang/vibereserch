# Claude Code MCP 服务器注册和使用指南

本文档详细介绍了如何将 VibeReserch MCP 服务器注册到 Claude Code 并进行使用。

## 1. MCP 服务器概述

### 什么是 MCP (Model Context Protocol)
MCP 是一个标准化协议，允许大语言模型与外部工具和服务进行交互。Claude Code 通过 MCP 协议可以访问我们的科研文献智能分析平台功能。

### 我们的 MCP 服务器功能
- **collect_literature**: 采集科研文献并进行智能筛选
- **structure_literature**: 对文献进行轻结构化处理
- **generate_experience**: 基于结构化文献生成研究经验
- **query_knowledge**: 基于经验库和文献库进行智能问答
- **create_project**: 创建新的研究项目
- **get_project_status**: 获取项目状态和进度

## 2. 注册 MCP 服务器到 Claude Code

### 2.1 自动注册（推荐）
使用命令行自动注册：

```bash
# 在项目根目录执行
claude mcp add vibereserch-mcp-server python3 /home/wolf/vibereserch/app/mcp_server.py
```

### 2.2 手动配置
如果需要手动配置，可以编辑 Claude Code 配置文件：

**位置**: `~/.claude.json`

**配置内容**:
```json
{
  "projects": {
    "/home/wolf/vibereserch": {
      "mcpServers": {
        "vibereserch-mcp-server": {
          "type": "stdio",
          "command": "python3",
          "args": [
            "/home/wolf/vibereserch/app/mcp_server.py"
          ],
          "env": {}
        }
      }
    }
  }
}
```

### 2.3 使用 .mcpb 桌面扩展文件
我们还提供了一个 `.mcpb` 桌面扩展文件，可以更方便地分发和安装：

**文件**: `vibereserch-mcp-server.mcpb`

用户可以双击此文件自动安装 MCP 服务器到 Claude Code。

## 3. 验证注册状态

### 3.1 检查服务器列表
```bash
claude mcp list
```

预期输出应包含：
```
vibereserch-mcp-server: python3 /home/wolf/vibereserch/app/mcp_server.py - ✓ Connected
```

### 3.2 查看服务器详情
```bash
claude mcp get vibereserch-mcp-server
```

## 4. 使用 MCP 服务器

### 4.1 交互式使用
在 Claude Code 交互模式中，直接要求 Claude 使用相关功能：

```
请使用 create_project 创建一个名为"AI研究项目"的新项目
```

### 4.2 无头（Headless）使用
对于自动化脚本或批处理，可以使用无头模式：

```bash
echo '创建一个新的研究项目' | claude --print --dangerously-skip-permissions
```

### 4.3 权限管理
首次使用时，Claude Code 会要求授权 MCP 工具的使用：

- **允许所有工具**: 选择 "Allow" 以永久授权
- **临时授权**: 选择 "Allow once" 仅本次授权
- **跳过权限检查**: 使用 `--dangerously-skip-permissions` 标志

## 5. MCP 协议技术细节

### 5.1 协议版本
- **当前版本**: 2025-06-18
- **通信方式**: STDIO (标准输入输出)
- **格式**: JSON-RPC 2.0

### 5.2 服务器能力声明
```json
{
  "protocolVersion": "2025-06-18",
  "capabilities": {
    "tools": {},
    "logging": {}
  },
  "serverInfo": {
    "name": "vibereserch-mcp-server",
    "version": "1.0.0",
    "description": "科研文献智能分析平台MCP服务器"
  }
}
```

### 5.3 工具定义标准
每个工具都使用标准的 JSON Schema 定义：

```json
{
  "name": "collect_literature",
  "description": "采集科研文献并进行智能筛选",
  "inputSchema": {
    "type": "object",
    "properties": {
      "project_id": {"type": "integer", "description": "项目ID"},
      "user_id": {"type": "integer", "description": "用户ID"},
      "keywords": {
        "type": "array",
        "items": {"type": "string"},
        "description": "关键词列表"
      }
    },
    "required": ["project_id", "user_id"]
  }
}
```

## 6. 调试和故障排除

### 6.1 启用调试模式
```bash
claude --mcp-debug
```

### 6.2 常见问题

**问题**: MCP 服务器显示未连接
**解决**: 检查 Python 路径和服务器文件路径是否正确

**问题**: 权限被拒绝
**解决**: 使用 `--dangerously-skip-permissions` 或在交互模式中授权

**问题**: 工具调用失败
**解决**: 检查后端 API 服务是否正常运行

### 6.3 服务器健康检查
服务器提供健康检查端点，可通过以下方式验证：

1. **MCP 协议检查**: `claude mcp list`
2. **服务器进程检查**: 检查是否有 `python3 app/mcp_server.py` 进程运行
3. **功能测试**: 调用简单的 MCP 工具验证响应

## 7. 高级使用

### 7.1 环境变量配置
可以通过环境变量配置 MCP 服务器行为：

```bash
export MCP_TIMEOUT=30000        # MCP 服务器启动超时（毫秒）
export MCP_TOOL_TIMEOUT=60000   # MCP 工具调用超时（毫秒）
```

### 7.2 多项目配置
可以为不同项目配置不同的 MCP 服务器：

- **项目级配置**: 在项目 `.claude.json` 中配置
- **用户级配置**: 在全局 `~/.claude.json` 中配置
- **会话级配置**: 使用 `--mcp-config` 标志临时加载

### 7.3 集成到 CI/CD
可以将 MCP 服务器集成到自动化流程中：

```bash
# 自动化研究流程示例
echo "为项目收集相关文献并生成研究报告" | \
  claude --print --dangerously-skip-permissions > research_report.md
```

## 8. 安全考虑

### 8.1 权限控制
- 首次使用时总是要求用户授权
- 可以在 Claude Code 设置中管理工具权限
- 生产环境建议避免使用 `--dangerously-skip-permissions`

### 8.2 数据安全
- MCP 服务器通过 STDIO 通信，数据不会通过网络传输
- 所有数据处理都在本地服务器上进行
- 敏感数据不会发送到外部服务

## 9. 总结

通过以上步骤，我们成功地：

1. ✅ **注册了 MCP 服务器**: 使用 `claude mcp add` 命令成功注册
2. ✅ **验证了连接状态**: 通过 `claude mcp list` 确认服务器正常连接
3. ✅ **测试了工具功能**: 成功调用 `create_project` 和 `query_knowledge` 工具
4. ✅ **创建了分发文件**: 提供 `.mcpb` 桌面扩展文件便于分发
5. ✅ **完成了文档**: 提供完整的注册、使用和故障排除指南

我们的 VibeReserch MCP 服务器现在完全符合 Claude Code 的 MCP 协议标准，可以无缝集成到研究工作流中，为用户提供智能的文献分析和知识查询服务。

## 10. 后续发展

- **功能扩展**: 可以根据需要添加更多研究相关的 MCP 工具
- **性能优化**: 继续优化 MCP 服务器的响应速度和稳定性
- **社区分发**: 可以将 `.mcpb` 文件发布到 Claude Code MCP 服务器市场
- **集成测试**: 建立自动化测试流程确保 MCP 协议兼容性