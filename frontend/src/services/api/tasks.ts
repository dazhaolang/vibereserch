import { apiClient } from './client';

export interface TaskProgress {
  step_name: string;
  step_description?: string;
  progress_percentage: number;
  step_result?: Record<string, unknown>;
  step_metrics?: Record<string, unknown>;
  started_at?: string;
  completed_at?: string;
}

export interface TaskItem {
  id: number;
  project_id: number;
  task_type: string;
  title: string;
  description?: string;
  status: string;
  progress_percentage: number;
  current_step?: string;
  created_at: string;
  updated_at?: string;
}

export interface TaskDetail extends TaskItem {
  config?: Record<string, unknown>;
  input_data?: Record<string, unknown>;
  result?: Record<string, unknown>;
  error_message?: string;
  token_usage?: number;
  cost_estimate?: number;
  cost_breakdown?: Record<string, unknown>;
  estimated_duration?: number;
  actual_duration?: number;
  started_at?: string;
  completed_at?: string;
  progress_logs: TaskProgress[];
}

interface TaskListResponse {
  tasks: TaskDetail[];
}

export interface TaskExtractionResult {
  id: number;
  task_id: number;
  extraction_type: string;
  content: string;
  confidence_score?: number;
  created_at: string;
  metadata?: Record<string, unknown> | null;
}

export interface LiteratureRelatedTask {
  id: number;
  title: string;
  description?: string;
  status: string;
  task_type: string;
  progress?: number | null;
  created_at: string;
  updated_at?: string | null;
  result_url?: string | null;
  error_message?: string | null;
  extraction_results: TaskExtractionResult[];
  estimated_duration?: number | null;
  actual_duration?: number | null;
}

export interface LiteratureTaskLinkageResponse {
  literature_id: number;
  tasks: LiteratureRelatedTask[];
}

export async function fetchTasks(params?: { project_id?: number; status?: string }): Promise<TaskItem[]> {
  const data = (await apiClient.get<TaskListResponse>('/api/task', { params })) as unknown as TaskListResponse;
  return data.tasks.map((task) => ({
    id: task.id,
    project_id: task.project_id,
    task_type: task.task_type,
    title: task.title,
    description: task.description,
    status: task.status,
    progress_percentage: task.progress_percentage,
    current_step: task.current_step,
    created_at: task.created_at,
    updated_at: task.updated_at,
  }));
}

export async function fetchTaskDetail(taskId: number): Promise<TaskDetail> {
  return (await apiClient.get<TaskDetail>(`/api/task/${taskId}`)) as unknown as TaskDetail;
}

export interface TaskCancelResponse {
  success: boolean;
  message: string;
}

export async function cancelTask(taskId: number): Promise<TaskCancelResponse> {
  return (await apiClient.post<TaskCancelResponse>(`/api/task/${taskId}/cancel`)) as unknown as TaskCancelResponse;
}

export async function retryTask(taskId: number, force = false): Promise<TaskDetail> {
  return (await apiClient.post<TaskDetail>(`/api/task/${taskId}/retry`, { force })) as unknown as TaskDetail;
}

export async function fetchLiteratureRelatedTasks(literatureId: number): Promise<LiteratureTaskLinkageResponse> {
  return (await apiClient.get<LiteratureTaskLinkageResponse>(`/api/task/literature/${literatureId}`)) as unknown as LiteratureTaskLinkageResponse;
}
