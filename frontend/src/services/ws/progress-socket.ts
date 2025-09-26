import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';

interface ProgressEvent {
  task_id: string;
  type: string;
  progress?: number;
  current_step?: string;
  result?: unknown;
  error?: string;
  timestamp?: string;
}

interface SocketState {
  connected: boolean;
  events: Record<string, ProgressEvent[]>;
  sockets: Map<string, WebSocket>;
  connect: (taskId: string, token?: string) => void;
  disconnect: (taskId: string) => void;
}

const noopStorage = {
  getItem: () => null,
  setItem: () => undefined,
  removeItem: () => undefined,
  clear: () => undefined,
  key: () => null,
  length: 0,
} as Storage;

export const useProgressSocket = create<SocketState>()(
  persist(
    (set, get) => ({
      connected: false,
      events: {},
      sockets: new Map(),
      connect: (taskId, token) => {
        if (typeof window === 'undefined') return;
        if (get().sockets.has(taskId)) return;

        const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
        const host = window.location.host;
        const url = token ? `/ws/progress/${taskId}?token=${token}` : `/ws/progress/${taskId}`;
        const ws = new WebSocket(`${protocol}://${host}${url}`);

        ws.onopen = () => {
          set((state) => {
            const sockets = new Map(state.sockets);
            sockets.set(taskId, ws);
            return {
              ...state,
              connected: true,
              sockets,
            };
          });
        };

        ws.onmessage = (event) => {
          if (typeof event.data !== 'string') {
            return;
          }

          let payload: ProgressEvent;
          try {
            payload = JSON.parse(event.data) as ProgressEvent;
          } catch (error) {
            console.warn('无法解析的进度消息', error);
            return;
          }

          set((state) => {
            const sockets = state.sockets;
            if (!sockets.has(taskId)) {
              return state;
            }
            const nextEvents = { ...state.events };
            const list = nextEvents[taskId] ? [...nextEvents[taskId], payload] : [payload];
            nextEvents[taskId] = list.slice(-80);
            return {
              ...state,
              events: nextEvents,
            };
          });
        };

        ws.onerror = () => {
          ws.close();
        };

        ws.onclose = () => {
          set((state) => {
            const sockets = new Map(state.sockets);
            sockets.delete(taskId);
            return {
              ...state,
              sockets,
              connected: sockets.size > 0,
            };
          });
        };
      },
      disconnect: (taskId) => {
        const sockets = get().sockets;
        const ws = sockets.get(taskId);
        ws?.close();
      },
    }),
    {
      name: 'progress-events',
      storage: createJSONStorage(() => (typeof window === 'undefined' ? noopStorage : sessionStorage)),
      partialize: (state) => ({ events: state.events }),
    }
  )
);
