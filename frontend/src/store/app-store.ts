import { create } from 'zustand';
import { devtools, persist } from 'zustand/middleware';

export interface User {
  id: number;
  username: string;
  email: string;
  full_name?: string;
  avatar?: string;
}

export interface Task {
  id: number;
  project_id: number;
  task_type: string;
  title: string;
  status: string;
  progress_percentage: number;
  current_step?: string;
  created_at: string;
  updated_at?: string;
  cost_estimate?: number;
  token_usage?: number;
  error_message?: string;
}

export type ResearchContext = Record<string, unknown>;

export interface ResearchSession {
  mode: 'auto' | 'deep' | 'rag';
  sessionId: string;
  query: string;
  context: ResearchContext;
  startTime: Date;
}

export interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  timestamp: Date;
  read: boolean;
}

type TaskBuckets = {
  active: Task[];
  completed: Task[];
  failed: Task[];
};

export interface AppState {
  user: User | null;
  isAuthenticated: boolean;
  currentSession: ResearchSession | null;
  tasks: TaskBuckets;
  websocket: {
    connected: boolean;
    lastUpdate: Date | null;
  };
  ui: {
    sidebarCollapsed: boolean;
    currentTheme: 'light' | 'dark';
    notifications: Notification[];
    loading: {
      global: boolean;
      tasks: boolean;
      research: boolean;
    };
  };

  setUser: (user: User | null) => void;
  setAuthenticated: (authenticated: boolean) => void;
  setCurrentSession: (session: ResearchSession | null) => void;
  setTasks: (tasks: Task[]) => void;
  updateTask: (task: Task) => void;
  addTask: (task: Task) => void;
  removeTask: (taskId: number) => void;
  setWebSocketStatus: (connected: boolean) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setTheme: (theme: 'light' | 'dark') => void;
  addNotification: (notification: Omit<Notification, 'id' | 'timestamp' | 'read'>) => void;
  markNotificationRead: (id: string) => void;
  clearNotifications: () => void;
  setLoading: (key: keyof AppState['ui']['loading'], loading: boolean) => void;
}

const categorizeTasks = (tasks: Task[]): TaskBuckets => {
  const normalized = tasks.map((task) => ({
    ...task,
    status: task.status?.toLowerCase?.() ?? task.status,
  }));

  return {
    active: normalized.filter((task) => ['pending', 'running'].includes(task.status)),
    completed: normalized.filter((task) => task.status === 'completed'),
    failed: normalized.filter((task) => task.status === 'failed'),
  };
};

export const useAppStore = create<AppState>()(
  devtools(
    persist(
      (set) => ({
        user: null,
        isAuthenticated: false,
        currentSession: null,
        tasks: {
          active: [],
          completed: [],
          failed: [],
        },
        websocket: {
          connected: false,
          lastUpdate: null,
        },
        ui: {
          sidebarCollapsed: false,
          currentTheme: 'dark',
          notifications: [],
          loading: {
            global: false,
            tasks: false,
            research: false,
          },
        },

        setUser: (user) => set({ user }),
        setAuthenticated: (authenticated) => set({ isAuthenticated: authenticated }),
        setCurrentSession: (session) => set({ currentSession: session }),

        setTasks: (tasks) => set({ tasks: categorizeTasks(tasks) }),

        updateTask: (updatedTask) => set((state) => {
          const merged = [
            ...state.tasks.active,
            ...state.tasks.completed,
            ...state.tasks.failed,
          ];
          const index = merged.findIndex((task) => task.id === updatedTask.id);
          if (index >= 0) {
            merged[index] = updatedTask;
          } else {
            merged.push(updatedTask);
          }
          return { tasks: categorizeTasks(merged) };
        }),

        addTask: (task) => set((state) => {
          const merged = [
            ...state.tasks.active,
            ...state.tasks.completed,
            ...state.tasks.failed,
            task,
          ];
          return { tasks: categorizeTasks(merged) };
        }),

        removeTask: (taskId) => set((state) => ({
          tasks: categorizeTasks(
            [
              ...state.tasks.active,
              ...state.tasks.completed,
              ...state.tasks.failed,
            ].filter((task) => task.id !== taskId)
          ),
        })),

        setWebSocketStatus: (connected) => set((state) => ({
          websocket: {
            connected,
            lastUpdate: connected ? new Date() : state.websocket.lastUpdate,
          },
        })),

        setSidebarCollapsed: (collapsed) => set((state) => ({
          ui: { ...state.ui, sidebarCollapsed: collapsed },
        })),

        setTheme: (theme) => set((state) => ({
          ui: { ...state.ui, currentTheme: theme },
        })),

        addNotification: (notification) => set((state) => ({
          ui: {
            ...state.ui,
            notifications: [
              ...state.ui.notifications,
              {
                ...notification,
                id: Math.random().toString(36).slice(2),
                timestamp: new Date(),
                read: false,
              },
            ],
          },
        })),

        markNotificationRead: (id) => set((state) => ({
          ui: {
            ...state.ui,
            notifications: state.ui.notifications.map((notification) =>
              notification.id === id ? { ...notification, read: true } : notification
            ),
          },
        })),

        clearNotifications: () => set((state) => ({
          ui: { ...state.ui, notifications: [] },
        })),

        setLoading: (key, loading) => set((state) => ({
          ui: {
            ...state.ui,
            loading: {
              ...state.ui.loading,
              [key]: loading,
            },
          },
        })),
      }),
      {
        name: 'app-store',
        partialize: (state) => ({
          tasks: state.tasks,
          currentSession: state.currentSession,
        }),
      }
    )
  )
);
