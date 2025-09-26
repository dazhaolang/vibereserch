import { apiClient } from './client';

export interface LiteratureItem {
  id: number;
  project_id?: number;
  title: string;
  authors: string[];
  abstract?: string;
  publication_year?: number;
  journal?: string;
  doi?: string;
  pmid?: string;
  keywords?: string[];
  is_parsed?: boolean;
  is_starred?: boolean;
  quality_score?: number;
  relevance_score?: number;
  status?: string;
  source_platform?: string;
  source?: 'pubmed' | 'arxiv' | 'google_scholar' | 'direct_upload' | 'other';
  citation_count?: number;
  pdf_url?: string;
  created_at?: string;
  updated_at?: string;
  tags?: string[];
  notes?: string;
}

export interface LiteratureListResponse {
  items: LiteratureItem[];
  total: number;
  page?: number;
  page_size?: number;
  has_more?: boolean;
}

export interface LiteratureCitationEntry {
  title?: string;
  authors?: string[];
  doi?: string;
  year?: number;
  url?: string;
  venue?: string;
  abstract?: string;
  referenceCount?: number;
  citationCount?: number;
  [key: string]: unknown;
}

export interface LiteratureCitationResponse {
  literature_id: number;
  title: string;
  citations: LiteratureCitationEntry[];
  references: LiteratureCitationEntry[];
  citation_count: number;
  reference_count: number;
  citation_graph: Record<string, unknown>;
  last_updated: string;
}

export interface LiteratureSearchParams {
  project_id?: number;
  query?: string;
  authors?: string[];
  year_start?: number;
  year_end?: number;
  keywords?: string[];
  page?: number;
  size?: number;
  sort_by?: 'relevance' | 'year' | 'quality' | 'created_at';
}

export async function fetchProjectLiterature(projectId: number, params?: { query?: string }): Promise<LiteratureListResponse> {
  if (params?.query) {
    const { data } = await apiClient.post<LiteratureListResponse>('/api/literature/search', {
      project_id: projectId,
      query: params.query,
      page: 1,
      size: 100
    });
    return data;
  }

  const { data } = await apiClient.get<LiteratureItem[]>(`/api/literature/project/${projectId}`);
  return { items: data, total: data.length };
}

export const literatureAPI = {
  // 获取文献列表
  async getLiterature(params?: LiteratureSearchParams) {
    const { data } = await apiClient.get<LiteratureListResponse>('/api/literature', { params });
    return data;
  },

  // 获取单个文献详情
  async getLiteratureById(id: number) {
    const { data } = await apiClient.get<LiteratureItem>(`/api/literature/${id}`);
    return data;
  },

  async getLiteratureCitations(
    id: number,
    params?: { include_references?: boolean; include_citations?: boolean; max_citations?: number }
  ): Promise<LiteratureCitationResponse> {
    const { data } = await apiClient.get<LiteratureCitationResponse>(
      `/api/literature/${id}/citations`,
      { params }
    );
    return data;
  },

  // 上传文献文件
  async uploadLiterature(file: File, projectId?: number) {
    const formData = new FormData();
    formData.append('file', file);
    if (projectId) {
      formData.append('project_id', projectId.toString());
    }

    const { data } = await apiClient.post<{ success: boolean; data: LiteratureItem }>(
      '/api/literature/upload',
      formData
    );
    return data;
  },

  // 批量上传文献
  async uploadBatchLiterature(files: File[], projectId?: number) {
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    if (projectId) {
      formData.append('project_id', projectId.toString());
    }

    const { data } = await apiClient.post<{ success: boolean; data: LiteratureItem[] }>(
      '/api/literature/upload-batch',
      formData
    );
    return data;
  },

  // 删除文献
  async deleteLiterature(id: number) {
    const { data } = await apiClient.delete<{ success: boolean }>(`/api/literature/${id}`);
    return data;
  },

  // 更新文献
  async updateLiterature(id: number, payload: Partial<LiteratureItem>) {
    const { data } = await apiClient.put<{ success: boolean; data: LiteratureItem }>(
      `/api/literature/${id}`,
      payload
    );
    return data;
  },

  // 添加标签
  async addTags(literatureId: number, tags: string[]) {
    const { data } = await apiClient.post<{ success: boolean; data: LiteratureItem }>(
      `/api/literature/${literatureId}/tags`,
      { tags }
    );
    return data;
  },

  // 添加笔记
  async addNote(literatureId: number, note: string) {
    const { data } = await apiClient.post<{ success: boolean; data: LiteratureItem }>(
      `/api/literature/${literatureId}/note`,
      { note }
    );
    return data;
  },
  async searchWithAI(params: { query: string; project_id?: number; max_results?: number }) {
    const { data } = await apiClient.post<{
      success: boolean;
      papers: Array<Record<string, unknown>>;
      total_count: number;
      query: string;
    }>('/api/literature/ai-search', {
      query: params.query,
      project_id: params.project_id,
      max_results: params.max_results ?? 20,
    });
    return data;
  },

  async batchAdd(projectId: number, literature: Array<Record<string, unknown>>) {
    const { data } = await apiClient.post<{
      success: boolean;
      message: string;
      added_count: number;
      skipped_count: number;
    }>(`/api/literature/project/${projectId}/batch-add`, {
      literature,
    });
    return data;
  },

  // 批量操作API
  async batchStar(ids: number[], starred: boolean) {
    const { data } = await apiClient.post<{ success: boolean; updated: number }>('/api/literature/batch/star', {
      literature_ids: ids,
      starred,
    });
    return data;
  },

  async batchArchive(ids: number[], archived: boolean) {
    const { data } = await apiClient.post<{ success: boolean; updated: number }>('/api/literature/batch/archive', {
      literature_ids: ids,
      archived,
    });
    return data;
  },

  async batchSetTags(ids: number[], action: 'add' | 'remove' | 'replace', tags: string[]) {
    const { data } = await apiClient.post<{ success: boolean; updated: number }>('/api/literature/batch/tags', {
      literature_ids: ids,
      action,
      tags,
    });
    return data;
  },

  async batchDelete(ids: number[]) {
    const { data } = await apiClient.post<{ success: boolean; deleted: number }>('/api/literature/batch/delete', {
      literature_ids: ids,
    });
    return data;
  },

  async exportLiterature(ids: number[], options: {
    format: 'csv' | 'bibtex' | 'json';
    fields: string[];
    includeAbstract: boolean;
    includeKeywords: boolean;
  }) {
    const { data } = await apiClient.post<{ success: boolean; downloadUrl: string }>('/api/literature/batch/export', {
      literature_ids: ids,
      ...options,
    });
    return data;
  }
};

export default literatureAPI;
