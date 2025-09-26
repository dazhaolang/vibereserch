/**
 * 项目管理API服务 - 基于真实后端API
 */

import { apiClient } from './client';

export type ProjectStatus = 'empty' | 'active' | 'completed' | 'archived' | 'pending' | 'processing' | 'unknown';

interface RawProject {
  id: number;
  name?: string;
  title?: string;
  description?: string | null;
  research_direction?: string | null;
  keywords?: string[] | null;
  research_categories?: string[] | null;
  status?: string | null;
  literature_sources?: Record<string, unknown> | null;
  max_literature_count?: number | null;
  structure_template?: Record<string, unknown> | null;
  extraction_prompts?: Record<string, unknown> | null;
  owner_id: number;
  created_at: string;
  updated_at?: string | null;
  literature_count?: number | null;
  literature?: Array<unknown> | null;
  progress_percentage?: number | null;
}

export interface Project {
  id: number;
  name: string;
  title: string;
  description?: string;
  research_direction?: string;
  keywords: string[];
  research_categories?: string[];
  status: ProjectStatus;
  literature_sources?: Record<string, unknown>;
  max_literature_count: number;
  structure_template?: Record<string, unknown>;
  extraction_prompts?: Record<string, unknown>;
  owner_id: number;
  created_at: string;
  updated_at?: string;
  literature_count: number;
  progress_percentage?: number;
}

export interface ProjectSummary {
  id: number;
  name: string;
  title?: string;
  description?: string;
  literature_count: number;
  progress_percentage?: number;
  status: ProjectStatus;
}

export interface CreateEmptyProjectPayload {
  name: string;
  description?: string;
  category?: string;
}

export interface CreateProjectPayload {
  name: string;
  description?: string;
  research_direction: string;
  keywords: string[];
  research_categories: string[];
  max_literature_count?: number;
  literature_sources?: string[];
  structure_template?: Record<string, unknown>;
  extraction_prompts?: Record<string, unknown>;
}

export interface DetermineDirectionPayload {
  user_input: string;
  conversation_history?: Array<{
    role: 'user' | 'assistant';
    content: string;
  }>;
}

export interface DetermineDirectionResponse {
  suggested_direction: string;
  keywords: string[];
  research_categories: string[];
  confidence: number;
  follow_up_questions: string[];
}

export interface UploadedFile {
  filename: string;
  file_path: string;
  size: number;
}

export interface UploadFilesResponse {
  message: string;
  uploaded_files: UploadedFile[];
  extraction_result?: {
    research_direction?: string;
    keywords?: string[];
    research_categories?: string[];
  };
}

export interface ProjectIndexingResponse {
  message: string;
  total_files: number;
  indexed_successfully: number;
  failed: number;
  indexing_results: Array<{
    filename: string;
    status: 'success' | 'failed';
    error?: string;
  }>;
}

const castProjectStatus = (status?: string | null): ProjectStatus => {
  if (!status) {
    return 'unknown';
  }
  const normalized = status.toLowerCase();
  if (['empty', 'active', 'completed', 'archived'].includes(normalized)) {
    return normalized as ProjectStatus;
  }
  if (['pending', 'processing', 'running'].includes(normalized)) {
    return normalized === 'running' ? 'processing' : (normalized as ProjectStatus);
  }
  return 'unknown';
};

const normalizeProject = (project: RawProject): Project => {
  const keywords = Array.isArray(project.keywords) ? project.keywords : [];
  const researchCategories = Array.isArray(project.research_categories)
    ? project.research_categories
    : undefined;
  const literatureCount = typeof project.literature_count === 'number'
    ? project.literature_count
    : Array.isArray(project.literature)
      ? project.literature.length
      : 0;

  return {
    id: project.id,
    name: project.name ?? project.title ?? '未命名项目',
    title: project.title ?? project.name ?? '未命名项目',
    description: project.description ?? undefined,
    research_direction: project.research_direction ?? undefined,
    keywords,
    research_categories: researchCategories,
    status: castProjectStatus(project.status),
    literature_sources: project.literature_sources ?? undefined,
    max_literature_count: project.max_literature_count ?? 0,
    structure_template: project.structure_template ?? undefined,
    extraction_prompts: project.extraction_prompts ?? undefined,
    owner_id: project.owner_id,
    created_at: project.created_at,
    updated_at: project.updated_at ?? undefined,
    literature_count: literatureCount,
    progress_percentage: project.progress_percentage ?? undefined,
  };
};

export const projectAPI = {
  // 创建空项目
  async createEmptyProject(payload: CreateEmptyProjectPayload): Promise<Project> {
    const { data } = await apiClient.post<RawProject>('/api/project/create-empty', payload);
    return normalizeProject(data);
  },

  // 创建完整项目
  async createProject(payload: CreateProjectPayload): Promise<Project> {
    const { data } = await apiClient.post<RawProject>('/api/project/create', payload);
    return normalizeProject(data);
  },

  // 获取用户所有项目
  async getProjects(): Promise<Project[]> {
    const { data } = await apiClient.get<RawProject[]>('/api/project/list');
    return data.map(normalizeProject);
  },

  // 获取项目详情
  async getProject(id: number): Promise<Project> {
    const { data } = await apiClient.get<RawProject>(`/api/project/${id}`);
    return normalizeProject(data);
  },

  // 智能确定研究方向
  async determineDirection(payload: DetermineDirectionPayload): Promise<DetermineDirectionResponse> {
    const { data } = await apiClient.post<DetermineDirectionResponse>('/api/project/determine-direction', payload);
    return data;
  },

  // 上传项目文件
  async uploadFiles(projectId: number, files: File[]): Promise<UploadFilesResponse> {
    const formData = new FormData();
    files.forEach((file) => {
      formData.append('files', file);
    });

    const { data } = await apiClient.post<UploadFilesResponse>(
      `/api/project/${projectId}/upload-files`,
      formData
    );
    return data;
  },

  // 索引项目文件
  async indexFiles(projectId: number): Promise<ProjectIndexingResponse> {
    const { data } = await apiClient.post<ProjectIndexingResponse>(`/api/project/${projectId}/index`);
    return data;
  },

  // 删除项目
  async deleteProject(id: number): Promise<{ message: string }> {
    const { data } = await apiClient.delete<{ message: string }>(`/api/project/${id}`);
    return data;
  },

  // 更新项目
  async updateProject(id: number, payload: Partial<CreateProjectPayload>): Promise<Project> {
    const { data } = await apiClient.put<RawProject>(`/api/project/${id}`, payload);
    return normalizeProject(data);
  }
};

// 向后兼容的导出
export async function fetchProjects(): Promise<ProjectSummary[]> {
  const projects = await projectAPI.getProjects();
  return projects.map(p => ({
    id: p.id,
    name: p.name,
    title: p.title,
    description: p.description,
    literature_count: p.literature_count,
    progress_percentage: p.progress_percentage,
    status: p.status
  }));
}

export default projectAPI;
