import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { apiClient, API_ENDPOINTS } from '../api/client';
import { useAppStore } from '../store/app-store';
import { fetchTaskStatistics, type TaskStatisticsResponse } from '@/services/api/task-stats';

// Research API hooks
export interface ResearchQueryRequest {
  project_id: number;
  query: string;
  mode: 'rag' | 'deep' | 'auto';
  max_literature_count?: number;
  context_literature_ids?: number[];
  processing_method?: string;
  keywords?: string[];
  auto_config?: Record<string, unknown>;
  agent?: 'claude' | 'codex' | 'gemini';
}

export interface ResearchQueryResponse {
  mode: string;
  payload: Record<string, unknown>;
}

export interface ProjectSummary {
  id: number;
  name: string;
  title?: string;
  description?: string;
  literature_count?: number;
  created_at?: string;
  updated_at?: string;
}

export type RecentProject = ProjectSummary & {
  last_accessed_at?: string;
};

export const useResearchQuery = () => {
  const queryClient = useQueryClient();
  const { setLoading, addNotification } = useAppStore();

  return useMutation({
    mutationFn: (request: ResearchQueryRequest) =>
      apiClient.post<ResearchQueryResponse>(API_ENDPOINTS.research.query, request),
    onMutate: () => {
      setLoading('research', true);
    },
    onSuccess: () => {
      setLoading('research', false);
      addNotification({
        type: 'success',
        title: '研究任务启动',
        message: '研究任务已成功启动，可在任务中心查看进度',
      });
      void queryClient.invalidateQueries({ queryKey: ['tasks'] });
    },
    onError: (error: unknown) => {
      setLoading('research', false);
      let message = '启动研究任务时发生错误';
      if (isAxiosError(error)) {
        const detail = (error.response?.data as { detail?: string } | undefined)?.detail;
        if (detail) {
          message = detail;
        }
      }
      addNotification({ type: 'error', title: '研究任务失败', message });
    },
  });
};

// Intelligent interaction hooks
export interface InteractionStartRequest {
  user_input: string;
  project_id: number;
  context_data?: Record<string, unknown>;
}

export interface ClarificationOption {
  option_id: string;
  title: string;
  description: string;
  icon?: string;
  estimated_time?: string;
  estimated_results?: string;
  confidence_score: number;
  implications: string[];
  is_recommended: boolean;
}

export interface InteractionStartResponse {
  session_id: string;
  intent_analysis: {
    intent_confidence: number;
    ambiguity_score: number;
    clarification_needed: boolean;
    extracted_entities: Record<string, unknown>;
  };
  clarification_options?: ClarificationOption[];
  direct_action?: {
    action_type: string;
    parameters: Record<string, unknown>;
  };
}

export const useStartInteraction = () => {
  return useMutation({
    mutationFn: (request: InteractionStartRequest) =>
      apiClient.post<InteractionStartResponse>(API_ENDPOINTS.interaction.start, request),
  });
};

export const useSelectClarification = () => {
  return useMutation({
    mutationFn: ({ sessionId, optionId, selectionData }: { sessionId: string; optionId: string; selectionData?: Record<string, unknown> }) =>
      apiClient.post(
        API_ENDPOINTS.interaction.select(sessionId),
        {
          option_id: optionId,
          selection_data: selectionData ?? {},
          client_timestamp: new Date().toISOString(),
        }
      ),
  });
};

// Task management hooks
export interface TaskOverviewTask {
  id?: number;
  task_id?: number;
  title?: string;
  task_type?: string;
  description?: string;
  status?: string;
  created_at?: string;
  updated_at?: string;
}

export interface TaskOverviewCostSummary {
  total_cost_estimate: number;
  total_token_usage: number;
  models: Record<string, unknown>;
}

export interface TaskOverview {
  total_tasks: number;
  status_breakdown: Record<string, number>;
  running_task_ids: string[];
  cost_summary: TaskOverviewCostSummary;
  recent_tasks: TaskOverviewTask[];
}

const normalizeStatusBreakdown = (
  items: TaskStatisticsResponse['status_breakdown'],
): Record<string, number> => {
  return items.reduce<Record<string, number>>((acc, item) => {
    const key = typeof item.status === 'string' ? item.status.toLowerCase() : item.status;
    if (key) {
      acc[key] = item.count;
    }
    return acc;
  }, {});
};

const normalizeRecentTasks = (tasks: TaskStatisticsResponse['recent_tasks']): TaskOverviewTask[] =>
  tasks.map((task) => {
    const id = typeof task.id === 'number' ? task.id : task.task_id;
    const taskId = typeof task.task_id === 'number' ? task.task_id : task.id;
    const derivedTitle = typeof task.title === 'string'
      ? task.title
      : typeof task.task_type === 'string'
        ? task.task_type
        : id !== undefined
          ? `任务 ${id}`
          : '未命名任务';

    return {
      id,
      task_id: taskId,
      title: derivedTitle,
      task_type: task.task_type,
      description: task.description,
      status: task.status,
      created_at: task.created_at,
      updated_at: task.updated_at,
    };
  });

export const useTaskOverview = (projectId?: number) => {
  return useQuery<TaskOverview>({
    queryKey: ['tasks', 'overview', projectId],
    queryFn: async () => {
      const stats = await fetchTaskStatistics(projectId ? { projectId } : undefined);
      return {
        total_tasks: stats.total_tasks,
        status_breakdown: normalizeStatusBreakdown(stats.status_breakdown),
        running_task_ids: stats.running_tasks.map((id) => String(id)),
        cost_summary: {
          total_cost_estimate: stats.cost_summary.total_cost_estimate ?? 0,
          total_token_usage: stats.cost_summary.total_token_usage ?? 0,
          models: stats.cost_summary.models ?? {},
        },
        recent_tasks: normalizeRecentTasks(stats.recent_tasks),
      };
    },
    refetchInterval: 5000,
  });
};

export const useTaskStatistics = (projectId?: number) => {
  return useQuery<TaskStatisticsResponse>({
    queryKey: ['tasks', 'statistics', projectId],
    queryFn: () => fetchTaskStatistics(projectId ? { projectId } : undefined),
    refetchInterval: 10000,
  });
};

// Literature hooks
export interface LiteratureSearchRequest {
  query: string;
  project_id?: number;
  max_results?: number;
  search_mode?: 'semantic' | 'keyword' | 'ai_enhanced';
}

export const useLiteratureSearch = () => {
  return useMutation({
    mutationFn: (request: LiteratureSearchRequest) =>
      apiClient.post(API_ENDPOINTS.literature.search, request),
  });
};

export const useSuggestContextLiterature = (query: string) => {
  return useQuery({
    queryKey: ['literature', 'suggest', query],
    queryFn: () =>
      apiClient.post(API_ENDPOINTS.literature.search, {
        query,
        page: 1,
        size: 5,
      }),
    enabled: !!query && query.length > 3,
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
};

// Project hooks
export const useProjects = () => {
  return useQuery<ProjectSummary[]>({
    queryKey: ['projects'],
    queryFn: () => apiClient.get<ProjectSummary[]>(API_ENDPOINTS.projects.list),
  });
};

export const useRecentProjects = () => {
  return useQuery<RecentProject[]>({
    queryKey: ['projects', 'recent'],
    queryFn: () => apiClient.get<RecentProject[]>(API_ENDPOINTS.projects.recent),
    staleTime: 2 * 60 * 1000, // 2 minutes
  });
};

export const useCreateProject = () => {
  const queryClient = useQueryClient();
  const { addNotification } = useAppStore();

  return useMutation({
    mutationFn: (projectData: { name: string; description?: string }) =>
      apiClient.post(API_ENDPOINTS.projects.create, projectData),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['projects'] });
      addNotification({
        type: 'success',
        title: '项目创建成功',
        message: '新项目已成功创建',
      });
    },
    onError: (error: unknown) => {
      let message = '创建项目时发生错误';
      if (isAxiosError(error)) {
        const detail = (error.response?.data as { detail?: string } | undefined)?.detail;
        if (detail) {
          message = detail;
        }
      }
      addNotification({ type: 'error', title: '项目创建失败', message });
    },
  });
};

// System status hooks
export const useSystemStatus = () => {
  return useQuery({
    queryKey: ['system', 'status'],
    queryFn: () => apiClient.get(API_ENDPOINTS.system.status),
    refetchInterval: 30000, // Refresh every 30 seconds
  });
};

export const useSystemCapabilities = () => {
  return useQuery({
    queryKey: ['system', 'capabilities'],
    queryFn: () => apiClient.get(API_ENDPOINTS.system.capabilities),
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
};

// Authentication hooks
interface LoginSuccessResponse {
  access_token: string;
  token_type?: string;
  expires_in?: number;
  user?: {
    id: number;
    username: string;
    email: string;
    full_name?: string;
  };
  user_info?: {
    id: number;
    username: string;
    email: string;
    full_name?: string;
  };
}

export const useLogin = () => {
  const { setUser, setAuthenticated, addNotification } = useAppStore();

  return useMutation({
    mutationFn: ({ username, password }: { username: string; password: string }) =>
      apiClient.post<LoginSuccessResponse>(
        API_ENDPOINTS.auth.login,
        { username, password }
      ),
    onSuccess: (data) => {
      localStorage.setItem('access_token', data.access_token);
      const account = data.user ?? data.user_info;
      if (account) {
        setUser({
          id: account.id,
          username: account.username,
          email: account.email,
          full_name: account.full_name,
        });
      }
      setAuthenticated(true);
      addNotification({
        type: 'success',
        title: '登录成功',
        message: `欢迎回来，${account?.full_name || account?.username || '用户'}！`,
      });
    },
    onError: (error: unknown) => {
      let message = '用户名或密码错误';
      if (isAxiosError(error)) {
        const detail = (error.response?.data as { detail?: string } | undefined)?.detail;
        if (detail) {
          message = detail;
        }
      }
      addNotification({ type: 'error', title: '登录失败', message });
    },
  });
};

export const useLogout = () => {
  const { setUser, setAuthenticated, addNotification } = useAppStore();

  return useMutation({
    mutationFn: () => apiClient.post(API_ENDPOINTS.auth.logout),
    onSuccess: () => {
      localStorage.removeItem('access_token');
      setUser(null);
      setAuthenticated(false);
      addNotification({
        type: 'info',
        title: '已退出登录',
        message: '您已安全退出系统',
      });
    },
  });
};
