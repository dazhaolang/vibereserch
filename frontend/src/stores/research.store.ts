import { create, type StateCreator } from 'zustand';
import { devtools, subscribeWithSelector } from 'zustand/middleware';
import { researchAPI } from '@/services/api/research';
import { fetchTasks, type TaskItem } from '@/services/api/tasks';
import {
  startInteraction,
  submitInteractionSelection,
  submitInteractionTimeout,
  submitInteractionCustomInput,
  type StartInteractionResponse,
} from '@/services/api/interaction';
import { wsManager } from '@/services/websocket/WebSocketManager';
import { normalizeResearchResult } from '@/utils/research';
import type {
  ClarificationCard,
  ClarificationOption,
  InteractionSelectionResponse,
  InteractionSession,
  InteractionTimeoutResponse,
  ResearchMode,
  ResearchResult,
  Task,
  TaskStatus,
} from '@/types';

const allowedAgents = ['claude', 'codex', 'gemini'] as const;
const allowedTaskStatuses: TaskStatus[] = ['pending', 'running', 'processing', 'completed', 'failed', 'cancelled'];
const allowedTaskTypes: Task['type'][] = [
  'literature_collection',
  'search_and_build_library',
  'experience_generation',
  'analysis',
  'auto_pipeline',
];
const allowedModes: ResearchMode[] = ['rag', 'deep', 'auto'];

type ResearchAgent = (typeof allowedAgents)[number];

interface PendingAutoQuery {
  query: string;
  projectId: number;
  mode: ResearchMode;
}

interface AutoPipelineOptions {
  keywords?: string[];
  autoConfig?: Record<string, unknown>;
  agent?: ResearchAgent;
}

type SubmitQueryResult =
  | { mode: 'auto'; interaction?: StartInteractionResponse; tasks?: Task[]; result?: ResearchResult }
  | { mode: 'rag'; result: ResearchResult }
  | { mode: 'deep'; task_id?: number };

interface ResearchStoreData {
  currentQuery: string | null;
  currentMode: ResearchMode;
  currentSession: InteractionSession | null;
  currentCard: ClarificationCard | null;
  clarificationHistory: Array<{
    id: string;
    time: string;
    type: 'auto-select' | 'select-option' | 'custom-input' | 'timeout';
    option?: ClarificationOption;
    input?: string;
  }>;
  activeTasks: Task[];
  results: ResearchResult[];
  history: ResearchResult[];
  isLoading: boolean;
  isHistoryLoading: boolean;
  error: string | null;
  pendingAutoQuery: PendingAutoQuery | null;
  lastAgentPlan?: unknown;
  lastAgent: ResearchAgent | null;
}

interface ResearchStoreActions {
  submitQuery: (query: string, mode: ResearchMode, projectId: number) => Promise<SubmitQueryResult>;
  updateSession: (session: InteractionSession | null) => void;
  updateCard: (card: ClarificationCard | null) => void;
  selectOption: (sessionId: string, optionId: string) => Promise<void>;
  submitCustomInput: (sessionId: string, input: string) => Promise<void>;
  handleTimeout: (sessionId: string) => Promise<void>;
  pushClarificationEvent: (event: ResearchStoreData['clarificationHistory'][number]) => void;
  addTask: (task: Task) => void;
  updateTask: (taskId: string, updates: Partial<Task>) => void;
  removeTask: (taskId: string) => void;
  addResult: (result: ResearchResult) => void;
  loadHistory: (projectId?: number) => Promise<void>;
  clearResults: () => void;
  setError: (error: string | null) => void;
  reset: () => void;
  syncTasks: (projectId?: number) => Promise<void>;
}

type ResearchState = ResearchStoreData & ResearchStoreActions;

const createInitialState = (): ResearchStoreData => ({
  currentQuery: null,
  currentMode: 'auto',
  currentSession: null,
  currentCard: null,
  clarificationHistory: [],
  activeTasks: [],
  results: [],
  history: [],
  isLoading: false,
  isHistoryLoading: false,
  error: null,
  pendingAutoQuery: null,
  lastAgentPlan: undefined,
  lastAgent: null,
});

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const safeErrorMessage = (error: unknown, fallback: string): string => {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  if (typeof error === 'string' && error.trim().length > 0) {
    return error;
  }
  return fallback;
};

const normalizeAgent = (value: unknown): ResearchAgent | undefined => {
  if (typeof value !== 'string') {
    return undefined;
  }
  const lower = value.toLowerCase();
  return allowedAgents.find((agent) => agent === lower);
};

const buildTaskFromItem = (item: TaskItem): Task => ({
  id: String(item.id),
  backendTaskId: item.id,
  type: normalizeTaskType(item.task_type),
  status: normalizeTaskStatus(item.status) ?? 'pending',
  progress: clampProgress(item.progress_percentage) ?? 0,
  title: item.title,
  description: item.description,
  message: item.current_step ?? undefined,
  created_at: item.created_at,
  updated_at: item.updated_at,
});

const ensureStringArray = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.filter((item): item is string => typeof item === 'string' && item.trim().length > 0).map((item) => item.trim());
  }
  if (typeof value === 'string' && value.trim()) {
    return value
      .split(',')
      .map((item) => item.trim())
      .filter((item) => item.length > 0);
  }
  return [];
};

const normalizeTaskType = (value: unknown): Task['type'] => {
  if (typeof value !== 'string') {
    return 'auto_pipeline';
  }
  const lower = value.toLowerCase();
  return allowedTaskTypes.find((type) => type === lower) ?? 'auto_pipeline';
};

const clampProgress = (value: unknown): number | undefined => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return undefined;
  }
  return Math.min(100, Math.max(0, value));
};

const normalizeTaskStatus = (value: unknown): TaskStatus | undefined => {
  if (typeof value !== 'string') {
    return undefined;
  }
  const lower = value.toLowerCase();
  if (lower === 'in_progress') {
    return 'processing';
  }
  return allowedTaskStatuses.find((status) => status === lower);
};

const deriveTaskKey = (task: Task): string =>
  task.backendTaskId !== undefined ? String(task.backendTaskId) : task.id;

const parseClarificationCard = (input: unknown): ClarificationCard | null => {
  if (!isRecord(input)) {
    return null;
  }

  const optionsRaw = Array.isArray(input.options) ? input.options : [];
  const options: ClarificationOption[] = optionsRaw.map((option) => {
    const record = isRecord(option) ? option : {};
    return {
      option_id: String(record.option_id ?? record.id ?? ''),
      title: typeof record.title === 'string'
        ? record.title
        : typeof record.label === 'string'
          ? record.label
          : '',
      description: typeof record.description === 'string' ? record.description : '',
      icon: typeof record.icon === 'string' ? record.icon : undefined,
      estimated_time: typeof record.estimated_time === 'string' ? record.estimated_time : undefined,
      estimated_results: typeof record.estimated_results === 'string' ? record.estimated_results : undefined,
      confidence_score: typeof record.confidence_score === 'number' ? record.confidence_score : undefined,
      implications: ensureStringArray(record.implications),
      is_recommended: Boolean(record.is_recommended),
      metadata: isRecord(record.metadata) ? record.metadata : undefined,
    };
  });

  return {
    session_id: String(input.session_id ?? ''),
    stage: String(input.stage ?? ''),
    question: String(input.question ?? ''),
    options,
    recommended_option_id: typeof input.recommended_option_id === 'string' ? input.recommended_option_id : undefined,
    timeout_seconds: typeof input.timeout_seconds === 'number' ? input.timeout_seconds : 5,
    custom_input_allowed: input.custom_input_allowed !== false,
    context: isRecord(input.context) ? input.context : undefined,
    created_at: typeof input.created_at === 'string' ? input.created_at : new Date().toISOString(),
  };
};

const parseTaskFromPayload = (raw: unknown, index: number): Task | null => {
  if (!isRecord(raw)) {
    return null;
  }

  const backendTaskId = raw.task_id ?? raw.id;
  const key = backendTaskId !== undefined ? String(backendTaskId) : `auto-${Date.now()}-${index}`;
  const progress = clampProgress(raw.progress) ?? 0;
  const status = normalizeTaskStatus(raw.status) ?? 'pending';

  return {
    id: key,
    backendTaskId: typeof backendTaskId === 'number' ? backendTaskId : undefined,
    type: normalizeTaskType(raw.type),
    status,
    progress,
    title: typeof raw.title === 'string' ? raw.title : undefined,
    description: typeof raw.description === 'string' ? raw.description : undefined,
    message: typeof raw.message === 'string' ? raw.message : undefined,
    result: raw.result,
    error: typeof raw.error === 'string' ? raw.error : typeof raw.error_message === 'string' ? raw.error_message : undefined,
    created_at: typeof raw.created_at === 'string' ? raw.created_at : undefined,
    updated_at: typeof raw.updated_at === 'string' ? raw.updated_at : undefined,
    estimated_time: typeof raw.estimated_time === 'number' ? raw.estimated_time : undefined,
  };
};

const parseTaskList = (payload: Record<string, unknown>): Task[] => {
  const rawTasks = Array.isArray(payload.tasks)
    ? payload.tasks
    : Array.isArray(payload.active_tasks)
      ? payload.active_tasks
      : [];

  return rawTasks
    .map((task, index) => parseTaskFromPayload(task, index))
    .filter((task): task is Task => Boolean(task));
};

const mergeTasks = (incoming: Task[], existing: Task[]): Task[] => {
  if (incoming.length === 0) {
    return existing;
  }

  const incomingKeys = new Set(incoming.map(deriveTaskKey));
  const preserved = existing.filter((task) => !incomingKeys.has(deriveTaskKey(task)));
  return [...incoming, ...preserved];
};

const insertResult = (results: ResearchResult[], result: ResearchResult): ResearchResult[] => {
  const filtered = results.filter((item) => item.id !== result.id);
  return [result, ...filtered];
};

const shouldCaptureResult = (result: ResearchResult): boolean => {
  const hasAnswer = typeof result.answer === 'string' && result.answer.trim().length > 0;
  return (
    hasAnswer ||
    result.key_findings.length > 0 ||
    result.sources.length > 0 ||
    result.research_gaps.length > 0 ||
    result.next_questions.length > 0
  );
};

const extractAutoOptions = (metadata?: Record<string, unknown>): AutoPipelineOptions => {
  if (!metadata) {
    return {};
  }

  const keywordsValue = metadata.keywords ?? metadata.search_keywords;
  const agentValue = metadata.agent ?? metadata.agent_name;
  const autoConfigValue = metadata.auto_config ?? metadata.config;

  const options: AutoPipelineOptions = {};
  const keywords = ensureStringArray(keywordsValue);
  if (keywords.length > 0) {
    options.keywords = keywords;
  }

  const normalizedAgent = normalizeAgent(agentValue);
  if (normalizedAgent) {
    options.agent = normalizedAgent;
  }

  if (isRecord(autoConfigValue)) {
    options.autoConfig = autoConfigValue;
  }

  return options;
};

const parseTaskProgressEvent = (raw: unknown): { taskId: string; updates: Partial<Task> } | null => {
  const source = isRecord(raw)
    ? (isRecord(raw.event) ? raw.event : raw)
    : null;

  if (!source) {
    return null;
  }

  const taskIdValue = source.task_id ?? source.id ?? source.taskId;
  if (taskIdValue === undefined) {
    return null;
  }

  const taskId = String(taskIdValue);
  const updates: Partial<Task> = {};

  const status = normalizeTaskStatus(source.status);
  if (status) {
    updates.status = status;
  }

  const progress = clampProgress(source.progress);
  if (progress !== undefined) {
    updates.progress = progress;
  }

  const message = typeof source.message === 'string'
    ? source.message
    : typeof source.description === 'string'
      ? source.description
      : undefined;
  if (message) {
    updates.message = message;
  }

  const error = typeof source.error === 'string'
    ? source.error
    : typeof source.error_message === 'string'
      ? source.error_message
      : undefined;
  if (error) {
    updates.error = error;
  }

  const eta = typeof source.estimated_time === 'number' ? source.estimated_time : undefined;
  if (eta !== undefined) {
    updates.estimated_time = eta;
  }

  return { taskId, updates };
};

const parseResearchResultEvent = (raw: unknown, fallbackQuestion: string): ResearchResult | null => {
  const container = isRecord(raw) ? raw : null;
  const payload = container && isRecord(container.payload) ? container.payload : container;
  if (!payload) {
    return null;
  }

  const modeValue = typeof payload.mode === 'string' ? payload.mode.toLowerCase() : undefined;
  if (!modeValue || !allowedModes.includes(modeValue as ResearchMode)) {
    return null;
  }
  const mode = modeValue as ResearchMode;

  const projectIdValue = payload.project_id ?? payload.projectId;
  const projectId = typeof projectIdValue === 'number'
    ? projectIdValue
    : typeof projectIdValue === 'string'
      ? Number.parseInt(projectIdValue, 10)
      : NaN;
  if (!Number.isFinite(projectId)) {
    return null;
  }

  const idValue = payload.id ?? payload.result_id ?? payload.task_id ?? `result-${Date.now()}`;
  const id = String(idValue);

  const question = typeof payload.question === 'string'
    ? payload.question
    : typeof payload.query === 'string'
      ? payload.query
      : fallbackQuestion;

  return normalizeResearchResult(payload, {
    base: {
      id,
      project_id: projectId,
      mode,
      question,
    },
    timestamp: typeof payload.timestamp === 'string' ? payload.timestamp : undefined,
    fallbackAnswer: typeof payload.answer === 'string' ? payload.answer : '',
    metadata: {
      ...(isRecord(payload.metadata) ? payload.metadata : {}),
      task_id: typeof payload.task_id === 'number' ? payload.task_id : undefined,
    },
  });
};

const extractCardFromInteractionEvent = (raw: unknown): ClarificationCard | null => {
  if (!isRecord(raw)) {
    return null;
  }

  const action = typeof raw.action === 'string'
    ? raw.action
    : typeof raw.type === 'string'
      ? raw.type
      : undefined;

  if (action !== 'new_card') {
    return null;
  }

  const payload = raw.card ?? raw.data ?? raw.clarification_card;
  return parseClarificationCard(payload);
};

const subscribeToTasks = (tasks: Task[]) => {
  tasks
    .filter((task) => task.backendTaskId !== undefined)
    .forEach((task) => {
      wsManager.subscribeToTask(String(task.backendTaskId));
    });
};

const createResearchStore: StateCreator<ResearchState> = (set, get) => {
  const fetchBackendResult = async (backendTaskId: number) => {
    try {
      const rawResult = await researchAPI.getResearchResult(String(backendTaskId));
      if (!rawResult) {
        return;
      }

      const rawMode = typeof rawResult.mode === 'string' ? rawResult.mode.toLowerCase() : 'auto';
      const mode = allowedModes.includes(rawMode as ResearchMode)
        ? (rawMode as ResearchMode)
        : 'auto';

      const overallConfidenceRaw = rawResult.confidence_metrics?.overall_confidence;
      const overallConfidence = typeof overallConfidenceRaw === 'number'
        ? overallConfidenceRaw
        : typeof overallConfidenceRaw === 'string'
          ? Number.parseFloat(overallConfidenceRaw)
          : undefined;

      const normalized = normalizeResearchResult(rawResult, {
        base: {
          id: String(rawResult.id ?? backendTaskId),
          project_id: rawResult.project_id,
          mode,
          question: typeof rawResult.query === 'string' && rawResult.query.trim().length > 0
            ? rawResult.query
            : get().currentQuery ?? '自动研究',
        },
        timestamp: rawResult.completed_at ?? rawResult.created_at ?? undefined,
        fallbackAnswer: rawResult.main_answer ?? '',
        metadata: {
          ...(isRecord(rawResult.metadata) ? rawResult.metadata : {}),
          task_id: rawResult.task_id ?? backendTaskId,
        },
        defaultConfidence: Number.isFinite(overallConfidence) ? (overallConfidence as number) : undefined,
      });

      if (!shouldCaptureResult(normalized)) {
        return;
      }

      set((state) => ({
        ...state,
        results: insertResult(state.results, normalized),
      }));
    } catch (error) {
      console.warn('获取研究结果失败', error);
    }
  };

  const loadHistory = async (projectId?: number) => {
    set((state) => ({
      ...state,
      isHistoryLoading: true,
      error: null,
    }));

    try {
      const historyResponse = await researchAPI.getResearchHistory({ project_id: projectId, size: 50 });
      const normalizedItems = historyResponse.items.map((item) => {
        const modeValue = typeof item.mode === 'string' ? item.mode.toLowerCase() : 'auto';
        const mode = allowedModes.includes(modeValue as ResearchMode)
          ? (modeValue as ResearchMode)
          : 'auto';

        const projectIdForItem = typeof item.project_id === 'number'
          ? item.project_id
          : projectId ?? 0;

        const overallConfidence = (() => {
          const raw = item.confidence_metrics?.overall_confidence;
          if (typeof raw === 'number') {
            return raw;
          }
          if (typeof raw === 'string') {
            const parsed = Number.parseFloat(raw);
            return Number.isFinite(parsed) ? parsed : undefined;
          }
          return undefined;
        })();

        return normalizeResearchResult(item, {
          base: {
            id: String(item.id ?? item.task_id ?? Date.now()),
            project_id: projectIdForItem,
            mode,
            question: typeof item.query === 'string' && item.query.trim().length > 0
              ? item.query
              : '研究任务',
          },
          timestamp: item.completed_at ?? item.created_at ?? undefined,
          fallbackAnswer: item.main_answer ?? '',
          metadata: {
            ...(isRecord(item.metadata) ? item.metadata : {}),
            task_id: item.task_id,
          },
          defaultConfidence: overallConfidence,
        });
      });

      set((state) => ({
        ...state,
        history: normalizedItems,
        isHistoryLoading: false,
      }));
    } catch (error) {
      console.warn('加载研究历史失败', error);
      set((state) => ({
        ...state,
        isHistoryLoading: false,
      }));
    }
  };

  const syncTasks = async (projectId?: number) => {
    try {
      const items = await fetchTasks(projectId ? { project_id: projectId } : undefined);
      const normalized = items.map(buildTaskFromItem);
      set((state) => ({
        ...state,
        activeTasks: mergeTasks(normalized, state.activeTasks),
      }));
      subscribeToTasks(normalized);
    } catch (error) {
      console.warn('同步任务列表失败', error);
    }
  };

  const pushClarificationEvent = (event: ResearchStoreData['clarificationHistory'][number]) => {
    set((state) => ({
      ...state,
      clarificationHistory: [event, ...state.clarificationHistory].slice(0, 20),
    }));
  };

  const runAutoPipeline = async (
    query: string,
    projectId: number,
    options?: AutoPipelineOptions
  ): Promise<SubmitQueryResult> => {
    set((state) => ({
      ...state,
      isLoading: true,
      error: null,
    }));

    try {
      const response = await researchAPI.triggerResearch({
        project_id: projectId,
        query,
        mode: 'auto',
        keywords: options?.keywords,
        auto_config: options?.autoConfig,
        agent: options?.agent,
      });

      if (!response || response.mode !== 'auto') {
        throw new Error('自动模式调用返回异常');
      }

      const payload = isRecord(response.payload) ? response.payload : {};
      const tasks = parseTaskList(payload);
      const agentPlan = payload.agent_plan;
      const normalizedAgent = normalizeAgent(payload.agent) ?? options?.agent ?? null;

      const normalizedResult = normalizeResearchResult(payload, {
        base: {
          id: `auto-${Date.now()}`,
          project_id: projectId,
          mode: 'auto',
          question: query,
        },
        timestamp: typeof payload.timestamp === 'string' ? payload.timestamp : undefined,
        fallbackAnswer: typeof payload.answer === 'string' ? payload.answer : '自动流水线执行完成',
        fallbackAnalysis: typeof payload.detailed_analysis === 'string'
          ? payload.detailed_analysis
          : '智能体已完成任务编排和执行',
        defaultConfidence: 0.8,
        metadata: {
          agent: normalizedAgent ?? undefined,
          keywords: options?.keywords,
          task_id: typeof payload.task_id === 'number' ? payload.task_id : undefined,
        },
      });

      set((state) => ({
        ...state,
        pendingAutoQuery: null,
        currentCard: null,
        isLoading: false,
        lastAgentPlan: agentPlan ?? state.lastAgentPlan,
        lastAgent: normalizedAgent ?? state.lastAgent,
        activeTasks: mergeTasks(tasks, state.activeTasks),
        results: shouldCaptureResult(normalizedResult)
          ? insertResult(state.results, normalizedResult)
          : state.results,
      }));

      subscribeToTasks(tasks);

      return {
        mode: 'auto',
        tasks,
        result: shouldCaptureResult(normalizedResult) ? normalizedResult : undefined,
      };
    } catch (error) {
      const message = safeErrorMessage(error, '自动模式执行失败');
      set((state) => ({
        ...state,
        isLoading: false,
        error: message,
      }));
      throw new Error(message);
    }
  };

  const processInteractionOutcome = async (
    response: InteractionSelectionResponse | InteractionTimeoutResponse,
    optionMetadata?: Record<string, unknown>
  ) => {
    if (!response?.success) {
      const message = response?.error || '交互处理失败';
      set((state) => ({
        ...state,
        isLoading: false,
        error: message,
      }));
      return;
    }

    if (response.next_clarification_card && response.next_action === 'next_clarification') {
      set((state) => ({
        ...state,
        currentCard: parseClarificationCard(response.next_clarification_card),
        isLoading: false,
      }));
      return;
    }

    const pending = get().pendingAutoQuery;
    if (pending) {
      const autoOptions = extractAutoOptions(optionMetadata);
      await runAutoPipeline(pending.query, pending.projectId, autoOptions);
    } else {
      set((state) => ({
        ...state,
        isLoading: false,
        currentCard: null,
      }));
    }
  };

  return {
    ...createInitialState(),

    syncTasks,
    pushClarificationEvent,
    loadHistory,

    submitQuery: async (query: string, mode: ResearchMode, projectId: number) => {
      set((state) => ({
        ...state,
        isLoading: true,
        error: null,
        currentQuery: query,
        currentMode: mode,
      }));

      try {
        if (mode === 'auto') {
          try {
            const interaction = await startInteraction({
              project_id: projectId,
              context_type: 'search',
              user_input: query,
              additional_context: {},
            });

            if (!interaction.success) {
              throw new Error(interaction.error || '智能交互初始化失败');
            }

            set((state) => ({
              ...state,
              pendingAutoQuery: { query, projectId, mode },
              isLoading: false,
              currentSession: interaction.session_id
                ? {
                    session_id: interaction.session_id,
                    project_id: projectId,
                    context_type: 'search',
                    created_at: new Date().toISOString(),
                    is_active: true,
                  }
                : state.currentSession,
              currentCard: parseClarificationCard(interaction.clarification_card),
            }));

            if (interaction.session_id) {
              wsManager.subscribeToSession(interaction.session_id);
            }

            if (interaction.requires_clarification && interaction.clarification_card) {
              return { mode: 'auto', interaction };
            }

            return await runAutoPipeline(query, projectId);
          } catch (interactionError) {
            console.warn('智能交互启动失败，回退至直接自动流程', interactionError);
            return await runAutoPipeline(query, projectId);
          }
        }

        const response = await researchAPI.triggerResearch({
          query,
          mode,
          project_id: projectId,
        });

        if (!response || !response.mode) {
          throw new Error('研究服务未返回有效结果');
        }

        const responseMode = response.mode;
        const payload = isRecord(response.payload) ? response.payload : {};

        if (responseMode === 'rag') {
          const normalized = normalizeResearchResult(payload, {
            base: {
              id: `result-${Date.now()}`,
              project_id: projectId,
              mode: 'rag',
              question: query,
            },
            timestamp: typeof payload.timestamp === 'string' ? payload.timestamp : undefined,
            fallbackAnswer: typeof payload.answer === 'string' ? payload.answer : '',
          });

          set((state) => ({
            ...state,
            results: insertResult(state.results, normalized),
            isLoading: false,
          }));

          return { mode: 'rag', result: normalized };
        }

        if (responseMode === 'deep') {
          const taskId = typeof payload.task_id === 'number' ? payload.task_id : undefined;
          const description = typeof payload.message === 'string' ? payload.message : '深度研究任务已启动';

          if (taskId) {
            const trackedTask: Task = {
              id: `task-${taskId}`,
              backendTaskId: taskId,
              type: 'experience_generation',
              status: 'pending',
              progress: 0,
              title: '深度研究经验生成',
              description,
            };

            set((state) => ({
              ...state,
              activeTasks: mergeTasks([trackedTask], state.activeTasks),
              isLoading: false,
            }));

            wsManager.subscribeToTask(String(taskId));
          } else {
            set((state) => ({
              ...state,
              isLoading: false,
            }));
          }

          return { mode: 'deep', task_id: taskId };
        }

        throw new Error(`暂不支持的研究模式: ${responseMode}`);
      } catch (error) {
        const message = safeErrorMessage(error, '提交查询失败');
        set((state) => ({
          ...state,
          isLoading: false,
          error: message,
        }));
        throw new Error(message);
      }
    },

    updateSession: (session: InteractionSession | null) => {
      set((state) => ({
        ...state,
        currentSession: session,
      }));
      if (session?.session_id) {
        wsManager.subscribeToSession(session.session_id);
      }
    },

    updateCard: (card: ClarificationCard | null) => {
      set((state) => ({
        ...state,
        currentCard: card,
      }));
    },

    selectOption: async (sessionId: string, optionId: string) => {
      const card = get().currentCard;
      if (!card) {
        return;
      }

      set((state) => ({
        ...state,
        isLoading: true,
        error: null,
      }));

      try {
        const selectedOption = card.options.find((option) => option.option_id === optionId);
        const response = await submitInteractionSelection(sessionId, optionId);
        await processInteractionOutcome(response, selectedOption?.metadata);
      } catch (error) {
        const message = safeErrorMessage(error, '选项提交失败');
        set((state) => ({
          ...state,
          error: message,
          isLoading: false,
        }));
      }
    },

    submitCustomInput: async (sessionId: string, input: string) => {
      set((state) => ({
        ...state,
        isLoading: true,
        error: null,
      }));

      try {
        const response = await submitInteractionCustomInput(sessionId, input);
        await processInteractionOutcome(response);
      } catch (error) {
        const message = safeErrorMessage(error, '自定义输入提交失败');
        set((state) => ({
          ...state,
          error: message,
          isLoading: false,
        }));
      }
    },

    handleTimeout: async (sessionId: string) => {
      const card = get().currentCard;
      if (!card?.recommended_option_id) {
        return;
      }

      set((state) => ({
        ...state,
        isLoading: true,
        error: null,
      }));

      try {
        const recommendedOption = card.options.find((option) => option.option_id === card.recommended_option_id);
        const response = await submitInteractionTimeout(sessionId);
        await processInteractionOutcome(response, recommendedOption?.metadata);
      } catch (error) {
        const message = safeErrorMessage(error, '自动选择失败');
        set((state) => ({
          ...state,
          error: message,
          isLoading: false,
        }));
      }
    },

    addTask: (task: Task) => {
      set((state) => ({
        ...state,
        activeTasks: mergeTasks([task], state.activeTasks),
      }));
      if (task.backendTaskId !== undefined) {
        wsManager.subscribeToTask(String(task.backendTaskId));
      }
    },

    updateTask: (taskId: string, updates: Partial<Task>) => {
      const existingTask = get().activeTasks.find((task) => {
        const key = deriveTaskKey(task);
        return key === taskId || task.id === taskId;
      });

      set((state) => ({
        ...state,
        activeTasks: state.activeTasks.map((task) => {
          const key = deriveTaskKey(task);
          if (key === taskId || task.id === taskId) {
            return { ...task, ...updates };
          }
          return task;
        }),
      }));

      const nextStatus = updates.status ?? existingTask?.status;
      const backendId = existingTask?.backendTaskId;
      if (backendId && nextStatus === 'completed') {
        void fetchBackendResult(backendId);
      }
    },

    removeTask: (taskId: string) => {
      set((state) => ({
        ...state,
        activeTasks: state.activeTasks.filter((task) => {
          const key = deriveTaskKey(task);
          return key !== taskId && task.id !== taskId;
        }),
      }));

      wsManager.unsubscribeFromTask(taskId);
    },

    addResult: (result: ResearchResult) => {
      set((state) => ({
        ...state,
        results: insertResult(state.results, result),
      }));
    },

    clearResults: () => {
      set((state) => ({
        ...state,
        results: [],
      }));
    },

    setError: (error: string | null) => {
      set((state) => ({
        ...state,
        error,
      }));
    },

    reset: () => {
      const state = get();
      state.activeTasks.forEach((task) => {
        wsManager.unsubscribeFromTask(deriveTaskKey(task));
      });
      if (state.currentSession?.session_id) {
        wsManager.unsubscribeFromSession(state.currentSession.session_id);
      }

      set(createInitialState());
    },
  };
};

export const useResearchStore = create<ResearchState>()(
  devtools(
    subscribeWithSelector(createResearchStore),
    { name: 'research-store' }
  )
);

wsManager.on('task_progress', (raw) => {
  const update = parseTaskProgressEvent(raw);
  if (!update) {
    return;
  }
  useResearchStore.getState().updateTask(update.taskId, update.updates);
});

wsManager.on('interaction_update', (raw) => {
  const card = extractCardFromInteractionEvent(raw);
  if (!card) {
    return;
  }
  useResearchStore.getState().updateCard(card);
});

wsManager.on('research_result', (raw) => {
  const state = useResearchStore.getState();
  const result = parseResearchResultEvent(raw, state.currentQuery ?? '');
  if (!result) {
    return;
  }
  state.addResult(result);
});
