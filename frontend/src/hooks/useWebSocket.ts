import { useEffect, useRef, useCallback } from 'react';
import { wsManager } from '@/services/websocket/WebSocketManager';

type WSHandler = (...args: unknown[]) => void;

export function useWebSocket() {
  const handlersRef = useRef<Map<string, WSHandler>>(new Map());

  const subscribe = useCallback((event: string, handler: WSHandler) => {
    wsManager.subscribe(event, handler);
    handlersRef.current.set(event, handler);

    return () => {
      wsManager.unsubscribe(event, handler);
      handlersRef.current.delete(event);
    };
  }, []);

  const unsubscribe = useCallback((event: string, handler?: WSHandler) => {
    const targetHandler = handler ?? handlersRef.current.get(event);
    if (!targetHandler) {
      return;
    }
    wsManager.unsubscribe(event, targetHandler);
    handlersRef.current.delete(event);
  }, []);

  const send = useCallback((event: string, data?: Record<string, unknown>) => {
    wsManager.send(event, data);
  }, []);

  useEffect(() => {
    const handlersMap = handlersRef.current;
    return () => {
      handlersMap.forEach((handler, event) => {
        wsManager.unsubscribe(event, handler);
      });
      handlersMap.clear();
    };
  }, []);

  const status = wsManager.getConnectionStatus();

  return {
    subscribe,
    unsubscribe,
    send,
    isConnected: status.connected,
    connectionStatus: status,
  };
}
