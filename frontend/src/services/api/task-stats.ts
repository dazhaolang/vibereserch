import { apiClient } from './client';

export interface TaskStatusBreakdown {
  status: string;
  count: number;
}

export interface TaskStatisticsResponse {
  total_tasks: number;
  status_breakdown: TaskStatusBreakdown[];
  running_tasks: number[];
  recent_tasks: TaskSummary[];
  cost_summary: {
    total_token_usage: number;
    total_cost_estimate: number;
    models: Record<string, unknown>;
  };
}

export interface TaskSummary {
  id?: number;
  task_id?: number;
  title?: string;
  status?: string;
  task_type?: string;
  description?: string;
  progress_percentage?: number;
  created_at?: string;
  updated_at?: string;
}

export async function fetchTaskStatistics(params?: { projectId?: number; limitRecent?: number }): Promise<TaskStatisticsResponse> {
  const query: Record<string, unknown> = {};
  if (params?.projectId !== undefined) {
    query.project_id = params.projectId;
  }
  if (params?.limitRecent !== undefined) {
    query.limit_recent = params.limitRecent;
  }

  return (await apiClient.get<TaskStatisticsResponse>('/api/task/stats', {
    params: Object.keys(query).length ? query : undefined,
  })) as unknown as TaskStatisticsResponse;
}
