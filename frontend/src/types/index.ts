// Research相关类型
export type ResearchMode = 'rag' | 'deep' | 'auto';

export interface ResearchQuery {
  query: string;
  mode: ResearchMode;
  project_id: number;
  keywords?: string[];
  context_literature_ids?: number[];
  max_literature_count?: number;
  processing_method?: 'standard' | 'deep';
  auto_config?: {
    enable_ai_filtering?: boolean;
    enable_pdf_processing?: boolean;
    enable_structured_extraction?: boolean;
    batch_size?: number;
    max_concurrent_downloads?: number;
    collection_max_count?: number;
    sources?: string[];
  };
  agent?: string;
}

// Interaction相关类型
export interface InteractionSession {
  session_id: string;
  id?: string;
  user_id?: number;
  project_id?: number;
  context_type?: string;
  current_stage?: string;
  is_active?: boolean;
  interaction_history?: unknown[];
  created_at?: string;
  expires_at?: string;
}

export interface ClarificationOption {
  option_id: string;
  title: string;
  description: string;
  icon?: string;
  estimated_time?: string;
  estimated_results?: string;
  confidence_score?: number;
  implications?: string[];
  is_recommended?: boolean;
  metadata?: Record<string, unknown>;
}

export interface ClarificationCard {
  session_id: string;
  stage: string;
  question: string;
  options: ClarificationOption[];
  recommended_option_id?: string;
  timeout_seconds: number;
  custom_input_allowed: boolean;
  context?: Record<string, unknown>;
  created_at: string;
}

export interface InteractionStartResponse {
  success: boolean;
  session_id?: string;
  requires_clarification: boolean;
  clarification_card?: ClarificationCard;
  direct_result?: Record<string, unknown>;
  error?: string;
  error_code?: string;
}

export interface InteractionSelectionResponse {
  success: boolean;
  next_action: 'continue_workflow' | 'next_clarification' | 'complete_interaction';
  next_clarification_card?: ClarificationCard | null;
  workflow_result?: Record<string, unknown> | null;
  progress_update?: Record<string, unknown> | null;
  error?: string;
  error_code?: string;
}

export interface InteractionTimeoutResponse extends InteractionSelectionResponse {
  auto_selected: boolean;
  selected_option?: ClarificationOption;
}

export interface InteractionClarificationResponse {
  success: boolean;
  clarification_cards: ClarificationCard[];
  current_stage: string;
  interaction_history: unknown[];
  error?: string;
}

export interface InteractionSessionStatistics {
  total_rounds: number;
  user_selections: number;
  auto_selections: number;
  custom_inputs: number;
  average_response_time: number;
}

export interface InteractionSessionInfo {
  session_id: string;
  project_id?: number;
  context_type?: string;
  current_stage?: string;
  is_active?: boolean;
  created_at?: string;
  expires_at?: string;
}

export interface InteractionSessionStatusResponse {
  success: boolean;
  session: InteractionSessionInfo;
  statistics: InteractionSessionStatistics;
  error?: string;
}

// Task相关类型
export type TaskStatus = 'pending' | 'running' | 'processing' | 'completed' | 'failed' | 'cancelled';

export interface Task {
  /** Local identifier used by the frontend to reference the task */
  id: string;
  /** Backend task primary key (if already created) */
  backendTaskId?: number;
  /** Logical task type */
  type: 'literature_collection' | 'search_and_build_library' | 'experience_generation' | 'analysis' | 'auto_pipeline';
  status: TaskStatus;
  /** Overall progress percentage (0-100) */
  progress: number;
  title?: string;
  description?: string;
  message?: string;
  result?: unknown;
  error?: string;
  created_at?: string;
  updated_at?: string;
  estimated_time?: number;
}

export interface TaskProgressDetails extends Record<string, unknown> {
  files_processed?: number;
  success_count?: number;
  failed_count?: number;
}

export interface TaskProgress {
  task_id: string;
  stage: string;
  progress: number;
  status: 'pending' | 'processing' | 'completed' | 'failed';
  message: string;
  details?: TaskProgressDetails;
  step_result?: string | Record<string, unknown>;
  log?: string;
  timestamp: number;
  overall_progress: number;
  current_stage: number;
  estimated_time?: number;
}

// Literature相关类型
export interface Literature {
  id: number;
  title: string;
  authors: string[];
  abstract?: string;
  journal?: string;
  publication_year?: number;
  doi?: string;
  pdf_url?: string;
  citation_count?: number;
  quality_score?: number;
  is_downloaded: boolean;
  is_parsed: boolean;
  created_at: string;
  updated_at: string;
}

export interface LiteratureSegment {
  id: number;
  literature_id: number;
  segment_type: string;
  content: string;
  structured_data?: Record<string, unknown>;
  extraction_confidence?: number;
  section_title?: string;
}

// Project相关类型
export interface Project {
  id: number;
  name: string;
  description?: string;
  keywords?: string[];
  research_direction?: string;
  structure_template?: Record<string, unknown>;
  owner_id: number;
  created_at: string;
  updated_at: string;
}

// User相关类型
export interface User {
  id: number;
  email: string;
  username: string;
  is_active: boolean;
  created_at: string;
}

// API响应类型
export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  message?: string;
  error?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

// WebSocket事件类型
export interface WebSocketEvent {
  type: string;
  payload: unknown;
  timestamp: number;
}

export interface ProgressEvent extends WebSocketEvent {
  type: 'task_progress';
  payload: TaskProgress;
}

export interface InteractionEvent extends WebSocketEvent {
  type: 'interaction_update';
  payload: {
    session_id: string;
    action: string;
    data: Record<string, unknown>;
  };
}

// 研究结果类型
export interface ResearchSource {
  id: number | string;
  title?: string;
  authors?: string[];
  year?: number;
  journal?: string;
  doi?: string;
  confidence?: number;
  relevance?: string;
  segments?: Array<number | string>;
}

export interface ResearchExperienceSummary {
  id?: number;
  title?: string;
  experience_type?: string;
  research_domain?: string;
  content?: string;
  key_findings?: string[];
  practical_guidelines?: string[];
  quality_score?: number;
}

export interface ResearchResult {
  id: string;
  project_id: number;
  mode: ResearchMode;
  question: string;
  task_id?: number;
  status: 'pending' | 'processing' | 'completed' | 'error';
  timestamp: string;
  answer: string;
  detailed_analysis: string;
  key_findings: string[];
  confidence: number;
  sources: ResearchSource[];
  research_gaps: string[];
  next_questions: string[];
  methodology_suggestions: string[];
  literature_count: number;
  main_experiences?: ResearchExperienceSummary[];
  suggestions?: string[];
  metadata?: Record<string, unknown>;
  error_message?: string;
  // 兼容旧版字段
  query?: string;
  references?: Literature[];
  confidence_score?: number;
  processing_time?: number;
  created_at?: string;
}

// 主经验类型
export interface MainExperience {
  id: number;
  project_id: number;
  research_domain: string;
  content: string;
  iteration_count: number;
  completeness_score: number;
  created_at: string;
  updated_at: string;
}
