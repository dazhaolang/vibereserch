import { apiClient } from './client';

export interface ResearchRequestPayload {
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

export interface ResearchResult {
  id: string;
  project_id: number;
  query: string;
  mode: 'rag' | 'deep' | 'auto';
  task_id?: number;
  status: 'pending' | 'processing' | 'completed' | 'error';
  progress?: number;
  created_at: string;
  completed_at?: string;
  error_message?: string;
  main_answer?: string;
  literature_sources?: Array<{
    id: string;
    title: string;
    authors: string[];
    year: number;
    relevance_score: number;
    key_findings: string;
    doi?: string;
  }>;
  experience_books?: Array<{
    id: string;
    title: string;
    summary: string;
    confidence_score: number;
    iterations: number;
    key_insights: string[];
  }>;
  experiment_suggestions?: Array<{
    id: string;
    name: string;
    objective: string;
    methodology: string;
    expected_outcome: string;
    difficulty: 'easy' | 'medium' | 'hard';
    resources_needed: string[];
  }>;
  confidence_metrics?: {
    overall_confidence: number;
    literature_coverage: number;
    consistency_score: number;
    novelty_score: number;
  };
  metadata?: Record<string, unknown>;
}

export interface ResearchHistoryItem {
  id?: number | string;
  task_id?: number;
  project_id: number;
  mode?: string;
  query?: string;
  status?: string;
  created_at?: string;
  completed_at?: string;
  main_answer?: string;
  confidence_metrics?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface ResearchHistory {
  items: ResearchHistoryItem[];
  total: number;
  page: number;
  size: number;
}

export interface ResearchTemplate {
  id: string;
  name: string;
  description: string;
  mode: 'rag' | 'deep' | 'auto';
  default_query?: string;
  default_keywords?: string[];
  config?: Record<string, unknown>;
  created_at: string;
  is_public?: boolean;
}

export interface ResearchExport {
  format: 'pdf' | 'docx' | 'markdown' | 'json';
  include_sources?: boolean;
  include_experience?: boolean;
  include_experiments?: boolean;
  include_metadata?: boolean;
  include_raw_payload?: boolean;
}

interface ResearchTriggerResponse {
  mode: string;
  payload: Record<string, unknown>;
}

export const researchAPI = {
  // 触发研究任务
  async triggerResearch(payload: ResearchRequestPayload) {
    const { data } = await apiClient.post<ResearchTriggerResponse>('/api/research/query', payload);
    return data;
  },

  // 获取研究结果
  async getResearchResult(taskId: string) {
    const { data } = await apiClient.get<ResearchResult>(`/api/research/result/${taskId}`);
    return data;
  },

  // 获取研究历史
  async getResearchHistory(params?: {
    project_id?: number;
    mode?: 'rag' | 'deep' | 'auto';
    status?: string;
    page?: number;
    size?: number;
    sort_by?: 'created_at' | 'relevance' | 'confidence';
  }) {
    const { data } = await apiClient.get<ResearchHistory>('/api/research/history', { params });
    return data;
  },

  // 停止研究任务
  async stopResearch(taskId: string) {
    const { data } = await apiClient.post<{
      success: boolean;
      message: string;
    }>(`/api/research/stop/${taskId}`);
    return data;
  },

  // 重新运行研究
  async retryResearch(taskId: string, modifications?: Record<string, unknown>) {
    const { data } = await apiClient.post<{
      success: boolean;
      new_task_id: string;
      message: string;
    }>(`/api/research/retry/${taskId}`, modifications ?? {});
    return data;
  },

  // 保存研究模板
  async saveTemplate(template: Omit<ResearchTemplate, 'id' | 'created_at'>) {
    const { data } = await apiClient.post<{
      success: boolean;
      data: ResearchTemplate;
    }>('/api/research/templates', template);
    return data;
  },

  // 获取研究模板列表
  async getTemplates(params?: { is_public?: boolean; page?: number; size?: number }) {
    const { data } = await apiClient.get<{
      items: ResearchTemplate[];
      total: number;
    }>('/api/research/templates', { params });
    return data;
  },

  // 应用研究模板
  async applyTemplate(templateId: string, projectId: number, query?: string) {
    const { data } = await apiClient.post<{
      success: boolean;
      task_id: string;
    }>(`/api/research/templates/${templateId}/apply`, {
      project_id: projectId,
      query,
    });
    return data;
  },

  // 导出研究结果
  async exportResult(taskId: string, options: ResearchExport) {
    const { data: blobData } = await apiClient.post<Blob>(`/api/research/export/${taskId}`, options, {
      responseType: 'blob'
    });

    // 创建下载链接
    const exportBlob = blobData instanceof Blob ? blobData : new Blob([blobData]);
    const url = window.URL.createObjectURL(exportBlob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `research_${taskId}.${options.format}`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  },

  // 获取研究任务状态
  async getTaskStatus(taskId: string) {
    const { data } = await apiClient.get<{
      status: 'pending' | 'processing' | 'completed' | 'error';
      progress: number;
      message?: string;
      estimated_time?: number;
    }>(`/api/research/status/${taskId}`);
    return data;
  },

  // 批量研究
  async batchResearch(requests: ResearchRequestPayload[]) {
    const { data } = await apiClient.post<{
      success: boolean;
      task_ids: string[];
      message: string;
    }>('/api/research/batch', { requests });
    return data;
  },

  async analyzeQuery(payload: { query: string; project_id: number; context?: Record<string, unknown> }) {
    const { data } = await apiClient.post<{
      recommended_mode: string;
      sub_questions: string[];
      complexity_score: number;
      estimated_resources: Record<string, unknown>;
      reasoning: string;
      suggested_keywords: string[];
      processing_suggestions: Record<string, unknown>;
    }>('/api/research/analysis', payload);
    return data;
  },

  // 获取研究建议
  async getSuggestions(projectId: number, context?: string) {
    const { data } = await apiClient.post<{
      suggestions: Array<{
        query: string;
        mode: 'rag' | 'deep' | 'auto';
        rationale: string;
        estimated_time: string;
      }>;
    }>('/api/research/suggestions', {
      project_id: projectId,
      context,
    });
    return data;
  },

  // 评价研究结果
  async rateResult(taskId: string, rating: number, feedback?: string) {
    const { data } = await apiClient.post<{
      success: boolean;
      message: string;
    }>(`/api/research/rate/${taskId}`, {
      rating,
      feedback,
    });
    return data;
  },

  // 分享研究结果
  async shareResult(taskId: string, emails: string[], message?: string, options?: Partial<ResearchExport> & { ttl_minutes?: number }) {
    const { data } = await apiClient.post<{
      success: boolean;
      share_url: string;
      expires_at: string;
      token: string;
    }>(`/api/research/share/${taskId}`, {
      emails,
      message,
      ...options,
    });
    return data;
  },

  async getSharedResult(token: string) {
    const { data } = await apiClient.get<{
      success: boolean;
      task_id: number;
      expires_at: string;
      payload: {
        task?: Record<string, unknown>;
        result?: Record<string, unknown>;
        raw_payload?: Record<string, unknown>;
      };
      share_url: string;
      emails: string[];
      message?: string;
    }>(`/api/research/share/token/${token}`);
    return data;
  },

  // 克隆研究任务
  async cloneResearch(taskId: string, targetProjectId?: number) {
    const { data } = await apiClient.post<{
      success: boolean;
      new_task_id: string;
      message: string;
    }>(`/api/research/clone/${taskId}`, {
      target_project_id: targetProjectId,
    });
    return data;
  }
};

// 保持向后兼容
export const triggerResearch = (payload: ResearchRequestPayload) => researchAPI.triggerResearch(payload);

export default researchAPI;
