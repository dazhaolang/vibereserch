import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { wsManager } from '@/services/websocket/WebSocketManager';

interface AuthState {
  accessToken: string | null;
  userId: number | null;
  setCredentials: (token: string, userId: number) => void;
  clear: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      userId: null,
      setCredentials: (token, userId) => {
        localStorage.setItem('access_token', token);
        localStorage.setItem('token', token);
        set({ accessToken: token, userId });
        wsManager.refreshConnection(token);
      },
      clear: () => {
        localStorage.removeItem('access_token');
        localStorage.removeItem('token');
        set({ accessToken: null, userId: null });
        wsManager.disconnect();
      }
    }),
    {
      name: 'vibereserch-auth'
    }
  )
);
