import { create } from 'zustand';
import { devtools } from 'zustand/middleware';
import { researchAPI } from '@/services/api/research';
import { normalizeResearchResult } from '@/utils/research';
import type { ResearchSource, ResearchResult } from '@/types';
import { useResearchShellStore, type ConversationMode, type LibraryStatus } from './research-shell.store';
import { startInteraction, submitInteractionSelection, type ClarificationCard } from '@/services/api/interaction';
import { wsManager } from '@/services/websocket/WebSocketManager';
import { useLibraryStore } from '@/stores/library.store';

interface ConversationEntry {
  id: string;
  role: 'user' | 'assistant' | 'system';
  mode: ConversationMode;
  content: string;
  createdAt: string;
  citations?: ResearchSource[];
  isError?: boolean;
  result?: ResearchResult;
}

interface ConversationState {
  messages: ConversationEntry[];
  isSending: boolean;
  error: string | null;
  lastLibraryStatus: LibraryStatus;
  clarificationCard: ClarificationCard | null;
  clarificationSessionId: string | null;
  clarificationQuestion: string | null;
  autoTasks: Record<string, TaskProgressMessage>;
  sendMessage: (input: string) => Promise<void>;
  launchClarification: (question: string) => Promise<void>;
  selectClarificationOption: (optionId: string) => Promise<void>;
  clearClarification: () => void;
  addMessage: (entry: ConversationEntry) => void;
  setAutoTask: (taskId: string, updates: TaskProgressMessage) => void;
  reset: () => void;
  setMessages: (messages: ConversationEntry[]) => void;
}

const generateId = () => {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto) {
    return crypto.randomUUID();
  }
  return `msg-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
};

const toErrorMessage = (error: unknown): string => {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  if (typeof error === 'string' && error.trim().length > 0) {
    return error;
  }
  return '请求失败，请稍后再试';
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

interface TaskProgressMessage {
  taskId: string;
  status?: string;
  progress?: number;
  message?: string;
}

const parseTaskProgress = (raw: unknown): TaskProgressMessage | null => {
  const source = isRecord(raw)
    ? (isRecord(raw.event) ? raw.event : raw)
    : null;

  if (!source) return null;

  const idValue = source.task_id ?? source.id ?? source.taskId;
  if (idValue === undefined) return null;

  const status = typeof source.status === 'string' ? source.status : undefined;
  const progress = typeof source.progress === 'number' ? source.progress : undefined;
  const message = typeof source.message === 'string'
    ? source.message
    : typeof source.description === 'string'
      ? source.description
      : undefined;

  return {
    taskId: String(idValue),
    status,
    progress,
    message,
  };
};

export type ConversationMessage = ConversationEntry;

const toLibraryStatus = (value: unknown): LibraryStatus | undefined => {
  if (typeof value !== 'string') {
    return undefined;
  }

  if (value === 'ready' || value === 'building' || value === 'merging' || value === 'error' || value === 'unselected') {
    return value;
  }

  return undefined;
};

export const useConversationStore = create<ConversationState>()(
  devtools((set) => ({
    messages: [],
    isSending: false,
    error: null,
    lastLibraryStatus: 'unselected',
    clarificationCard: null,
    clarificationSessionId: null,
    clarificationQuestion: null,
    autoTasks: {},

    setMessages: (messages) => set({ messages }),

    reset: () => {
      set({
        messages: [],
        isSending: false,
        error: null,
        clarificationCard: null,
        clarificationSessionId: null,
        clarificationQuestion: null,
        autoTasks: {},
      });
    },

    addMessage: (entry) => {
      set((state) => ({ messages: [...state.messages, entry] }));
    },

    setAutoTask: (taskId, updates) => {
      set((state) => ({
        autoTasks: {
          ...state.autoTasks,
          [taskId]: { ...state.autoTasks[taskId], ...updates },
        },
      }));
    },

    sendMessage: async (input: string) => {
      const trimmed = input.trim();
      if (!trimmed) {
        return;
      }

      const {
        mode,
        libraryId,
        libraryStatus,
        setSessionId,
      } = useResearchShellStore.getState();

      const requiresLibrary = mode !== 'auto';
      if (requiresLibrary && !libraryId) {
        set({ error: '请先选择一个文献库', lastLibraryStatus: libraryStatus });
        return;
      }

      if (requiresLibrary && libraryStatus !== 'ready') {
        set({ error: '当前文献库不可用，请稍后重试或选择其它文献库', lastLibraryStatus: libraryStatus });
        return;
      }

      const projectId = libraryId ?? 0;
      const timestamp = new Date().toISOString();
      const userMessage: ConversationMessage = {
        id: generateId(),
        role: 'user',
        mode,
        content: trimmed,
        createdAt: timestamp,
      };

      if (mode === 'auto') {
        const autoMessage: ConversationMessage = {
          id: generateId(),
          role: 'system',
          mode,
          content: '已启动自动研究流水线，系统正在规划任务…',
          createdAt: new Date().toISOString(),
        };
        set((state) => ({ messages: [...state.messages, autoMessage] }));
      }

      set((state) => ({
        messages: [...state.messages, userMessage],
        isSending: true,
        error: null,
        lastLibraryStatus: libraryStatus,
      }));

      try {
        const requestPayload: Parameters<typeof researchAPI.triggerResearch>[0] = {
          project_id: projectId,
          query: trimmed,
          mode,
        };

        if (mode === 'rag') {
          requestPayload.max_literature_count = 12;
        }

        if (mode === 'deep') {
          requestPayload.processing_method = 'standard';
        }

        const { payload } = await researchAPI.triggerResearch(requestPayload);

        let effectiveProjectId = projectId;
        let derivedStatus: LibraryStatus | undefined;

        let createdFlag = false;
        let candidateId: number | null = null;

        if (mode === 'auto' && isRecord(payload)) {
          const payloadRecord = payload;
          const possibleId = payloadRecord.project_id;
          if (typeof possibleId === 'number' && possibleId > 0) {
            candidateId = possibleId;
            effectiveProjectId = possibleId;

            const statusByRoot = toLibraryStatus(payloadRecord.project_status);
            const projectNode = isRecord(payloadRecord.project) ? payloadRecord.project : undefined;
            const statusByProject = projectNode ? toLibraryStatus(projectNode.status) : undefined;
            createdFlag = payloadRecord.created_new_project === true;

            derivedStatus = statusByRoot ?? statusByProject ?? (createdFlag ? 'building' : undefined);

            const shellState = useResearchShellStore.getState();
            if (candidateId !== libraryId) {
              shellState.setLibraryId(candidateId);
            }
            if (derivedStatus) {
              shellState.setLibraryStatus(derivedStatus);
            } else if (createdFlag) {
              shellState.setLibraryStatus('building');
            }

            const libraryState = useLibraryStore.getState();
            if (candidateId !== libraryId) {
              libraryState.setSelectedProject(candidateId);
            }
            void libraryState.loadCollections();
          }
        }

        const assistantId = generateId();
        const normalized = normalizeResearchResult(payload, {
          base: {
            id: assistantId,
            project_id: effectiveProjectId,
            mode,
            question: trimmed,
          },
          timestamp: new Date().toISOString(),
          fallbackAnswer: '暂未生成回答',
          fallbackAnalysis: '暂无详细分析',
          defaultConfidence: 0.75,
        });

        const assistantMessage: ConversationMessage = {
          id: assistantId,
          role: 'assistant',
          mode,
          content: normalized.answer || '暂无回答',
          createdAt: normalized.timestamp,
          citations: normalized.sources,
          result: normalized,
        };

        const automationSummary = mode === 'auto'
          ? {
              id: generateId(),
              role: 'system' as const,
              mode,
              content: normalized.metadata?.plan_summary
                ? String(normalized.metadata.plan_summary)
                : '自动流水线执行完成，您可以查看结果或继续提问。',
              createdAt: new Date().toISOString(),
            }
          : null;

        const metadata = normalized.metadata || {};
        if (mode === 'auto' && derivedStatus && !metadata.library_status) {
          metadata.library_status = derivedStatus;
          if (!normalized.metadata) {
            normalized.metadata = metadata;
          }
        }
        const sessionId = metadata && typeof metadata.session_id === 'string'
          ? metadata.session_id
          : undefined;
        if (sessionId) {
          setSessionId(sessionId);
        }

        const followUps: ConversationMessage[] = [];
        if (automationSummary) {
          followUps.push(automationSummary);
        }
        if (mode === 'auto' && candidateId && createdFlag) {
          followUps.push({
            id: generateId(),
            role: 'system',
            mode,
            content: `已为本次自动研究创建新的临时文献库（ID ${candidateId}），系统正在后台构建并合并数据。`,
            createdAt: new Date().toISOString(),
          });
        }
        if (mode === 'auto' && derivedStatus && derivedStatus !== 'ready') {
          followUps.push({
            id: generateId(),
            role: 'system',
            mode,
            content: derivedStatus === 'building'
              ? '文献库正在构建中，完成后将自动切换为可用状态。'
              : derivedStatus === 'merging'
                ? '文献库处于合并阶段，将在处理完成后更新内容。'
                : `文献库当前状态：${derivedStatus}`,
            createdAt: new Date().toISOString(),
          });
        }

        set((state) => ({
          messages: followUps.length > 0
            ? [...state.messages, assistantMessage, ...followUps]
            : [...state.messages, assistantMessage],
          isSending: false,
          error: null,
        }));
      } catch (error) {
        const message = toErrorMessage(error);
        const assistantMessage: ConversationMessage = {
          id: generateId(),
          role: 'assistant',
          mode,
          content: message,
          createdAt: new Date().toISOString(),
          isError: true,
        };

        set((state) => ({
          messages: [...state.messages, assistantMessage],
          isSending: false,
          error: message,
        }));
      }
    },

    launchClarification: async (question) => {
      const {
        mode,
        libraryId,
        libraryStatus,
        setSessionId,
      } = useResearchShellStore.getState();

      const requiresLibrary = mode !== 'auto';
      if (requiresLibrary && !libraryId) {
        set({ error: '请先选择文献库', lastLibraryStatus: libraryStatus });
        return;
      }

      if (requiresLibrary && libraryStatus !== 'ready') {
        set({ error: '当前文献库不可用，无法发起澄清', lastLibraryStatus: libraryStatus });
        return;
      }

      try {
        const response = await startInteraction({
          project_id: libraryId ?? 0,
          context_type: mode,
          user_input: question,
        });
        setSessionId(response.session_id ?? null);
        set({
          clarificationCard: response.clarification_card ?? null,
          clarificationSessionId: response.session_id ?? null,
          clarificationQuestion: question,
          error: null,
        });
        if (!response.clarification_card) {
          set((state) => ({
            messages: [...state.messages, {
              id: generateId(),
              role: 'system',
              mode,
              content: '系统已自动确认，无需澄清，继续研究流程。',
              createdAt: new Date().toISOString(),
            }],
          }));
        }
      } catch (error) {
        set({ error: toErrorMessage(error) });
      }
    },

    selectClarificationOption: async (optionId) => {
      const { clarificationSessionId, clarificationCard, clarificationQuestion } = useConversationStore.getState();
      const { mode } = useResearchShellStore.getState();
      if (!clarificationSessionId) {
        return;
      }
      try {
        await submitInteractionSelection(clarificationSessionId, optionId);
        set({ clarificationCard: null, clarificationSessionId: null });
        const selectedOption = clarificationCard?.options.find((opt) => opt.option_id === optionId);
        if (selectedOption) {
          const logMessage: ConversationEntry = {
            id: generateId(),
            role: 'system',
            mode,
            content: `已选择澄清选项：${selectedOption.title}`,
            createdAt: new Date().toISOString(),
          };
          set((state) => ({ messages: [...state.messages, logMessage] }));
        }
        if (clarificationQuestion) {
          const followup: ConversationEntry = {
            id: generateId(),
            role: 'assistant',
            mode,
            content: '澄清完成，您可以继续提问或执行新的指令。',
            createdAt: new Date().toISOString(),
          };
          set((state) => ({ messages: [...state.messages, followup], clarificationQuestion: null }));
        }
      } catch (error) {
        set({ error: toErrorMessage(error) });
      }
    },

    clearClarification: () => {
      set({ clarificationCard: null, clarificationSessionId: null, clarificationQuestion: null });
    },
  }))
);

const autoTaskEvents = ['task_progress', 'task_started', 'task_completed', 'task_failed'] as const;

const handleTaskEvent = (raw: unknown) => {
  const { mode } = useResearchShellStore.getState();
  if (mode !== 'auto') {
    return;
  }

  const parsed = parseTaskProgress(raw);
  if (!parsed) {
    return;
  }

  const { autoTasks, setAutoTask } = useConversationStore.getState();
  const previous = autoTasks[parsed.taskId];

  const changed = !previous
    || previous.status !== parsed.status
    || previous.progress !== parsed.progress
    || previous.message !== parsed.message;

  setAutoTask(parsed.taskId, parsed);

  if (!changed) {
    return;
  }

  const stageHints: Array<{ test: RegExp; hint: string }> = [
    { test: /search|搜索/i, hint: '正在搜索候选文献…' },
    { test: /filter|筛选/i, hint: '正在进行 AI 智能筛选…' },
    { test: /download|下载/i, hint: '批量下载 PDF 并解析内容…' },
    { test: /structure|结构化/i, hint: '执行轻结构化处理，整理文献要点…' },
    { test: /merge|合并/i, hint: '合并新旧文献库并更新索引…' },
    { test: /experience|经验/i, hint: '生成经验总结与洞察…' },
  ];

  const taskMessage = parsed.message;
  const stageHint = taskMessage
    ? stageHints.find((item) => item.test.test(taskMessage))?.hint
    : undefined;

  const statusHint = parsed.status
    ? {
        pending: '任务已排队等待执行…',
        running: '流水线正在运行…',
        processing: '正在处理中…',
        completed: '流水线已完成。',
        failed: '流水线执行失败，请查看任务中心。',
      }[parsed.status]
    : undefined;

  const parts: string[] = [];
  if (stageHint) {
    parts.push(stageHint);
  } else if (parsed.message) {
    parts.push(parsed.message);
  }

  if (statusHint) {
    parts.push(statusHint);
  } else if (parsed.status) {
    parts.push(`状态：${parsed.status}`);
  }

  if (typeof parsed.progress === 'number') {
    parts.push(`进度 ${Math.round(parsed.progress)}%`);
  }

  if (parts.length === 0) {
    return;
  }

  useConversationStore.getState().addMessage({
    id: generateId(),
    role: 'system',
    mode: 'auto',
    content: parts.join(' · '),
    createdAt: new Date().toISOString(),
  });
};

autoTaskEvents.forEach((event) => {
  wsManager.on(event, handleTaskEvent);
});
