import type { AxiosRequestConfig } from 'axios';
import { apiClient as sharedClient } from '@/services/api/client';

class APIClient {
  async get<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await sharedClient.get<T>(url, config);
    return response.data;
  }

  async post<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    const response = await sharedClient.post<T>(url, data, config);
    return response.data;
  }

  async put<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    const response = await sharedClient.put<T>(url, data, config);
    return response.data;
  }

  async delete<T>(url: string, config?: AxiosRequestConfig): Promise<T> {
    const response = await sharedClient.delete<T>(url, config);
    return response.data;
  }

  async patch<T>(url: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
    const response = await sharedClient.patch<T>(url, data, config);
    return response.data;
  }
}

export const apiClient = new APIClient();

// API endpoint definitions
export const API_ENDPOINTS = {
  // Authentication
  auth: {
    login: '/api/auth/login',
    register: '/api/auth/register',
    logout: '/api/auth/logout',
    me: '/api/auth/me',
  },

  // Research modes
  research: {
    query: '/api/research/query',
    analysis: '/api/research/analysis',
  },

  // Intelligent interaction
  interaction: {
    start: '/api/interaction/start',
    clarifications: (sessionId: string) => `/api/interaction/${sessionId}/clarifications`,
    select: (sessionId: string) => `/api/interaction/${sessionId}/select`,
    timeout: (sessionId: string) => `/api/interaction/${sessionId}/timeout`,
    custom_input: (sessionId: string) => `/api/interaction/${sessionId}/custom`,
    end_session: (sessionId: string) => `/api/interaction/${sessionId}/end`,
    session_status: (sessionId: string) => `/api/interaction/${sessionId}/status`,
  },

  // Tasks
  tasks: {
    list: '/api/tasks/list',
    detail: (id: string | number) => `/api/task/${id}`,
    progress: (id: string | number) => `/api/tasks/${id}/progress`,
    overview: '/api/tasks/overview',
    statistics: '/api/tasks/statistics',
    performance_metrics: '/api/tasks/performance_metrics',
    cost_analysis: '/api/tasks/cost_analysis',
  },

  // Literature
  literature: {
    list: '/api/literature',
    search: '/api/literature/search',
    upload: '/api/literature/upload',
    upload_batch: '/api/literature/upload-batch',
  },

  // Projects
  projects: {
    list: '/api/project/list',
    create: '/api/project/create',
    create_empty: '/api/project/create-empty',
    get: (id: number) => `/api/project/${id}`,
    delete: (id: number) => `/api/project/${id}`,
    update: (id: number) => `/api/project/${id}`,
    upload_files: (projectId: number) => `/api/project/${projectId}/upload-files`,
    index: (projectId: number) => `/api/project/${projectId}/index`,
    recent: '/api/project/list',
  },

  // Analysis
  analysis: {
    related_questions: '/api/analysis/related_questions',
  },

  // MCP Tools
  mcp: {
    tools: '/api/mcp/tools',
    run: '/api/mcp/run',
  },

  // System
  system: {
    health: '/health',
    status: '/api/system/status',
    capabilities: '/api/system/capabilities',
  },
};
