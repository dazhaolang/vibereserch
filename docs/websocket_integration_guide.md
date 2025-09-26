# WebSocket 集成指南

## 总览
本平台提供两类 WebSocket 接口：
- `ws://<host>/ws/global`：全局广播，用于获取系统级事件与活跃任务。
- `ws://<host>/ws/progress/{task_id}?token=<JWT>`：任务专用通道，推送实时进度、历史事件和心跳。
- `ws://<host>/ws/project/{project_id}/status?token=<JWT>`：项目级通道，聚合项目内任务动态。

所有端点都要求在查询参数中携带 `token`，值为当前登录用户的 JWT。后端在握手阶段执行校验，不合法的令牌会返回 `4001` 关闭码。

## 认证与心跳
- 握手成功后，服务器立即发送 `connection_established` 事件。
- 任务通道会紧接着推送最近 10 条历史事件以及当前状态，项目通道则返回活跃任务列表。
- 客户端每隔 30 秒会收到服务器 `heartbeat` 消息。若需要自定义保活，可发送 `{ "type": "ping", "timestamp": ... }`，服务器会以 `pong` 响应。

## 前端使用方式
平台自带 `WebSocketManager`（`frontend/src/services/websocket/WebSocketManager.ts`），负责：
1. 基于 `VITE_API_BASE_URL` 或 `VITE_WS_URL` 自动推导 WebSocket 地址。
2. 在本地存储中检测 `access_token`、`token` 或 `vibereserch-auth`，自动附加 `?token=<JWT>`。
3. 当登录前尚无令牌时会进入轮询，获取到令牌后自动重试连接。
4. 支持断线重连、候选地址轮换和消息分发（`task_progress`、`research_result` 等）。

典型用法：
```tsx
import { useEffect } from 'react';
import { wsManager } from '@/services/websocket/WebSocketManager';

export function useTaskProgress(taskId: string) {
  useEffect(() => {
    wsManager.connect(); // 令牌到位后会自动完成握手
    const unsubscribe = wsManager.subscribe('task_progress', (payload) => {
      if (payload?.task_id === taskId) {
        // TODO: 更新本地状态
      }
    });

    return () => {
      unsubscribe();
    };
  }, [taskId]);
}
```

> 注意：`wsManager.connect()` 可以在全局初始化时调用一次；当令牌尚未加载时，管理器会定期重试并在获得令牌后建立连接。

## 常见排查要点
- **401/4001 关闭**：检查前端是否存在 JWT，或后端 `JWT_SECRET_KEY` 与签发时不一致。
- **未收到进度**：确保任务通过 `stream_progress_service` 注册，且客户端监听 `task_progress` 或 `research_result`。
- **多标签页冲突**：WebSocket 在同一浏览器中每个标签页独立重连。若需要跨标签共享事件，可结合 `BroadcastChannel`。

## 相关环境变量
- `VITE_API_BASE_URL`：HTTP API 基址，WebSocket 地址会在此基础上转换为 `ws`/`wss`。
- `VITE_WS_URL`：显式指定 WebSocket 基址，适合生产环境前后端域名不一致的情况。
- `APP_ENV`：后端运行模式，会出现在 `/healthz` 响应中，便于调试。

如需扩展新消息类型，只需在后端推送时设置 `type` 字段，并在 `WebSocketManager.routeIncomingMessage` 中注册对应处理逻辑。
