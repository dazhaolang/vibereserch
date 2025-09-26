import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { projectAPI } from '@/services/api/project';

export interface Project {
  id: number;
  title: string;
  description?: string;
  created_at: string;
  updated_at?: string;
}

export interface Session {
  id: string;
  session_id?: string;
  project_id: number;
  user_id: number;
  created_at: string;
  last_activity: string;
  query?: string;
  context_data?: Record<string, unknown>;
}

interface AppState {
  // 项目上下文
  currentProject: Project | null;
  availableProjects: Project[];

  // 会话上下文
  currentSession: Session | null;

  // UI状态
  sidebarCollapsed: boolean;
  theme: 'light' | 'dark';

  // 动作
  setCurrentProject: (project: Project | null) => void;
  setAvailableProjects: (projects: Project[]) => void;
  updateAvailableProject: (projectId: number, updates: Partial<Project>) => void;
  setCurrentSession: (session: Session | null) => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  setTheme: (theme: 'light' | 'dark') => void;

  // 初始化
  initialize: () => Promise<void>;

  // 会话管理
  createSession: (projectId: number) => Session;
  restoreSession: (sessionId: string) => Session | null;
}

export const useAppStore = create<AppState>()(
  persist(
    (set, get) => ({
      // 初始状态
      currentProject: null,
      availableProjects: [],
      currentSession: null,
      sidebarCollapsed: false,
      theme: 'light',

      // 动作实现
      setCurrentProject: (project) => {
        set({ currentProject: project });

        // 项目切换时清空当前会话
        if (project) {
          get().createSession(project.id);
        } else {
          set({ currentSession: null });
        }
      },

      setAvailableProjects: (projects) => set({ availableProjects: projects }),

      updateAvailableProject: (projectId, updates) =>
        set((state) => ({
          availableProjects: state.availableProjects.map((project) =>
            project.id === projectId ? { ...project, ...updates } : project
          ),
        })),

      setCurrentSession: (session) => set({ currentSession: session }),

      setSidebarCollapsed: (collapsed) => set({ sidebarCollapsed: collapsed }),

      setTheme: (theme) => set({ theme }),

      // 初始化应用状态
      initialize: async () => {
        try {
          const projects = await projectAPI.getProjects();
          const normalizedProjects: Project[] = projects.map((project) => ({
            id: project.id,
            title: project.title,
            description: project.description ?? undefined,
            created_at: project.created_at,
            updated_at: project.updated_at ?? undefined,
          }));

          set({ availableProjects: normalizedProjects });

          // 尝试恢复会话
          const { currentProject } = get();
          if (!currentProject && normalizedProjects.length > 0) {
            get().setCurrentProject(normalizedProjects[0]);
          }

          const activeProject = get().currentProject;
          if (activeProject) {
            const storedSession = localStorage.getItem(`session_${activeProject.id}`);
            if (storedSession) {
              get().restoreSession(storedSession);
            } else {
              get().createSession(activeProject.id);
            }
          }
        } catch (error) {
          console.error('App initialization failed:', error);
        }
      },

      // 创建新会话
      createSession: (projectId: number) => {
        const session = {
          id: `local-${projectId}-${Date.now()}`,
          session_id: `local-${projectId}-${Date.now()}`,
          project_id: projectId,
          user_id: 0,
          created_at: new Date().toISOString(),
          last_activity: new Date().toISOString(),
          context_data: {},
        } as Session;

        set({ currentSession: session });
        localStorage.setItem(`session_${projectId}`, JSON.stringify(session));
        return session;
      },

      // 恢复会话
      restoreSession: (sessionId: string) => {
        try {
          const parsed = JSON.parse(sessionId) as Session;
          set({ currentSession: parsed });
          return parsed;
        } catch (error) {
          console.warn('Failed to parse stored session, creating a new one.', error);
          const { currentProject } = get();
          if (currentProject) {
            localStorage.removeItem(`session_${currentProject.id}`);
            return get().createSession(currentProject.id);
          }
          return null;
        }
      },
    }),
    {
      name: 'app-store',
      partialize: (state) => ({
        currentProject: state.currentProject,
        sidebarCollapsed: state.sidebarCollapsed,
        theme: state.theme,
      }),
    }
  )
);
