import React, { useState, useCallback, useEffect, useMemo } from 'react';
import {
  Layout,
  Row,
  Col,
  Card,
  Space,
  Spin,
  message,
  notification,
  Button,
  Statistic,
  Tag,
  List,
  Collapse,
  Typography,
  Empty,
} from 'antd';
import { AnimatePresence, motion } from 'framer-motion';
import { SmartQueryInput } from '@/components/workspace/SmartQueryInput';
import { ModeSelector } from '@/components/workspace/ModeSelector';
import { ProjectSelector } from '@/components/workspace/ProjectSelector';
import type { Project } from '@/components/workspace/ProjectSelector';
import { ProgressPanel } from '@/components/workspace/ProgressPanel';
import { InteractionCards } from '@/components/interaction/InteractionCards';
import { ResearchResultPanel } from '@/components/research/ResearchResultPanel';
import { useResearchStore } from '@/stores/research.store';
import { useAppStore } from '@/stores/app.store';
import { cancelTask as cancelTaskRequest, retryTask as retryTaskRequest } from '@/services/api/tasks';
import { projectAPI } from '@/services/api/project';
import { useWebSocket } from '@/hooks/useWebSocket';
import type { AutoModeConfig } from '@/components/workspace/AutoModeControlPanel';
import type { DeepModeConfig } from '@/components/workspace/DeepModeControlPanel';
import { normalizeResearchResult } from '@/utils/research';
import type { ResearchMode, ResearchResult, Task } from '@/types';

type ResearchStoreSnapshot = ReturnType<typeof useResearchStore.getState>;
type ClarificationHistoryEntry = ResearchStoreSnapshot['clarificationHistory'][number];

interface ResearchWorkspaceProps {
  projectId?: number;
  hideProjectSelector?: boolean;
}

const modeLabelMap: Record<ResearchMode, string> = {
  rag: 'RAG 模式',
  deep: '深度研究',
  auto: '全自动调度',
};

const modeTagColor: Record<ResearchMode, string> = {
  rag: 'green',
  deep: 'blue',
  auto: 'purple',
};

const getTaskStatusMeta = (status: string) => {
  const normalized = typeof status === 'string' ? status.toLowerCase() : '';
  switch (normalized) {
    case 'running':
    case 'processing':
      return { label: '执行中', color: 'blue' as const };
    case 'pending':
      return { label: '排队中', color: 'gold' as const };
    case 'completed':
      return { label: '已完成', color: 'green' as const };
    case 'failed':
    case 'error':
      return { label: '失败', color: 'red' as const };
    case 'paused':
      return { label: '已暂停', color: 'orange' as const };
    default:
      return { label: status || '未知', color: 'default' as const };
  }
};

const renderModeTag = (mode: ResearchMode) => (
  <Tag color={modeTagColor[mode]}>{modeLabelMap[mode]}</Tag>
);

const renderTaskStatusTag = (status: string) => {
  const meta = getTaskStatusMeta(status);
  return <Tag color={meta.color}>{meta.label}</Tag>;
};

const { Text } = Typography;
const { Panel } = Collapse;

const formatDisplayDate = (value?: string | Date | null) => {
  if (!value) return undefined;
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) {
    return undefined;
  }
  return date.toLocaleString();
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

interface TaskProgressEvent {
  task_id?: string | number;
  progress?: number;
  message?: string;
}

const parseTaskProgressEvent = (raw: unknown): TaskProgressEvent | null => {
  if (!isRecord(raw)) {
    return null;
  }
  const taskId = raw.task_id ?? raw.taskId ?? raw.id;
  const progress = raw.progress ?? raw.progress_percentage ?? raw.percent;
  const message = typeof raw.message === 'string' ? raw.message : undefined;
  const normalizedProgress = typeof progress === 'number' ? progress : undefined;
  if (typeof taskId !== 'string' && typeof taskId !== 'number' && normalizedProgress === undefined && !message) {
    return null;
  }
  return {
    task_id: typeof taskId === 'number' || typeof taskId === 'string' ? taskId : undefined,
    progress: normalizedProgress,
    message,
  };
};

const extractTaskId = (value: unknown): string | undefined => {
  if (typeof value === 'string') {
    return value;
  }
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value);
  }
  return undefined;
};

interface ParsedResearchResult {
  result: ResearchResult;
  taskId?: string;
}

const parseResearchResultEvent = (
  raw: unknown,
  defaults: {
    fallbackQuestion: string;
    fallbackMode: ResearchMode;
    fallbackProjectId?: number;
  }
): ParsedResearchResult | null => {
  if (!isRecord(raw)) {
    return null;
  }

  const payload = isRecord(raw.payload) ? raw.payload : raw;
  const modeValue = typeof payload.mode === 'string' ? payload.mode.toLowerCase() : defaults.fallbackMode;
  const allowedModes: ResearchMode[] = ['auto', 'deep', 'rag'];
  const normalizedMode = allowedModes.includes(modeValue as ResearchMode)
    ? (modeValue as ResearchMode)
    : defaults.fallbackMode;

  const projectIdCandidate = payload.project_id ?? payload.projectId ?? defaults.fallbackProjectId;
  const projectId = typeof projectIdCandidate === 'number'
    ? projectIdCandidate
    : typeof projectIdCandidate === 'string'
      ? Number.parseInt(projectIdCandidate, 10)
      : defaults.fallbackProjectId;
  if (projectId === undefined || Number.isNaN(projectId)) {
    return null;
  }

  const question = typeof payload.question === 'string'
    ? payload.question
    : typeof payload.query === 'string'
      ? payload.query
      : defaults.fallbackQuestion;

  const idValue = payload.id ?? payload.result_id ?? payload.task_id ?? `result-${Date.now()}`;
  const normalizedResult = normalizeResearchResult(payload, {
    base: {
      id: String(idValue),
      project_id: projectId,
      mode: normalizedMode,
      question,
    },
    timestamp: typeof payload.timestamp === 'string' ? payload.timestamp : undefined,
  });

  const taskId = extractTaskId(payload.task_id ?? payload.taskId ?? raw.task_id ?? raw.taskId);

  return { result: normalizedResult, taskId };
};

const getExperienceCount = (raw: unknown): number | null => {
  if (!isRecord(raw)) {
    return null;
  }
  const count = raw.experience_count ?? raw.count;
  if (typeof count === 'number' && Number.isFinite(count)) {
    return count;
  }
  return null;
};

interface QueryOptions {
  attachments?: number[];
  deepConfig?: DeepModeConfig | null;
  autoConfig?: AutoModeConfig | null;
}

const { Content } = Layout;

export const ResearchWorkspace: React.FC<ResearchWorkspaceProps> = ({ projectId, hideProjectSelector = false }) => {
  const [mode, setMode] = useState<ResearchMode>('auto');
  const [currentResult, setCurrentResult] = useState<ResearchResult | null>(null);
  const [showResult, setShowResult] = useState(false);

  // 使用App Store管理项目和会话上下文
  const currentProject = useAppStore((state) => state.currentProject);
  const currentSession = useAppStore((state) => state.currentSession);
  const currentSessionQuery = useAppStore((state) => state.currentSession?.query);
  const setCurrentProject = useAppStore((state) => state.setCurrentProject);
  const availableProjects = useAppStore((state) => state.availableProjects);
  const initialize = useAppStore((state) => state.initialize);

  const currentCard = useResearchStore((state) => state.currentCard);
  const activeTasks = useResearchStore((state) => state.activeTasks);
  const results = useResearchStore((state) => state.results);
  const isLoading = useResearchStore((state) => state.isLoading);
  const error = useResearchStore((state) => state.error);
  const submitQuery = useResearchStore((state) => state.submitQuery);
  const reset = useResearchStore((state) => state.reset);
  const syncTasks = useResearchStore((state) => state.syncTasks);
  const updateTask = useResearchStore((state) => state.updateTask);
  const clarificationHistory = useResearchStore((state) => state.clarificationHistory);

  const totalTasks = activeTasks.length;

  const taskSummary = useMemo(() => {
    let running = 0;
    let pending = 0;
    let completed = 0;
    let failed = 0;

    activeTasks.forEach((task) => {
      const status = typeof task.status === 'string' ? task.status.toLowerCase() : '';
      if (status === 'running' || status === 'processing') {
        running += 1;
      } else if (status === 'pending') {
        pending += 1;
      } else if (status === 'completed') {
        completed += 1;
      } else if (status === 'failed' || status === 'error') {
        failed += 1;
      }
    });

    return { running, pending, completed, failed };
  }, [activeTasks]);

  const latestResult = results[0] ?? null;
  const latestConfidence = latestResult
    ? Math.round(Math.min(Math.max((latestResult.confidence ?? 0) * 100, 0), 100))
    : null;
  const latestAnswerPreview = latestResult?.answer
    ? latestResult.answer.replace(/\s+/g, ' ').slice(0, 80)
    : null;

  const handleSelectResult = useCallback((item: ResearchResult) => {
    setCurrentResult(item);
    setShowResult(true);
  }, []);

  const renderTaskHeader = useCallback((task: Task) => {
    const progressValue = typeof (task as { progress?: number }).progress === 'number'
      ? Math.round(((task as { progress?: number }).progress ?? 0))
      : typeof (task as { progress_percentage?: number }).progress_percentage === 'number'
        ? Math.round(((task as { progress_percentage?: number }).progress_percentage ?? 0))
        : 0;

    return (
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          width: '100%',
          paddingRight: 8,
        }}
      >
        <Space direction="vertical" size={0}>
          <Text strong>{task.title || `任务 ${task.id}`}</Text>
          {task.message && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              {task.message}
            </Text>
          )}
        </Space>
        <Space size={12} align="center">
          {renderTaskStatusTag(task.status)}
          <Text type="secondary">{progressValue}%</Text>
        </Space>
      </div>
    );
  }, []);

  const { subscribe, unsubscribe, isConnected } = useWebSocket();

  const rawSessionMode = (currentSession as { mode?: string })?.mode;
  const normalizedSessionMode = typeof rawSessionMode === 'string'
    ? (rawSessionMode.toLowerCase() as ResearchMode)
    : undefined;
  const sessionModeValue: ResearchMode = normalizedSessionMode && ['auto', 'deep', 'rag'].includes(normalizedSessionMode)
    ? normalizedSessionMode
    : mode;

  const sessionQueryDisplay = (currentSession as { query?: string })?.query ?? currentSessionQuery ?? '';
  const sessionIdentifier = (currentSession as { session_id?: string; sessionId?: string; id?: string })?.session_id
    ?? (currentSession as { session_id?: string; sessionId?: string; id?: string })?.sessionId
    ?? (currentSession as { session_id?: string; sessionId?: string; id?: string })?.id
    ?? undefined;
  const sessionStartedAt = formatDisplayDate(
    (currentSession as { startTime?: Date })?.startTime ?? (currentSession as { created_at?: string })?.created_at ?? null
  );
  const projectCreatedAt = currentProject?.created_at ? formatDisplayDate(currentProject.created_at) : undefined;

  // WebSocket事件订阅
  useEffect(() => {
    const rawQuery = currentSessionQuery;
    const fallbackQuestion =
      typeof rawQuery === 'string' && rawQuery.trim().length > 0 ? rawQuery : '研究任务';

    const handleTaskProgress = (...args: unknown[]) => {
      const payload: unknown = args[0];
      const progressEvent = parseTaskProgressEvent(payload);
      if (!progressEvent || progressEvent.progress === undefined) {
        return;
      }
      notification.info({
        message: '任务进度更新',
        description: `${progressEvent.message ?? '处理中'} - ${progressEvent.progress}%`,
        placement: 'bottomRight',
      });
    };

    const handleResearchResult = (...args: unknown[]) => {
      const payload: unknown = args[0];
      const parsed = parseResearchResultEvent(payload, {
        fallbackQuestion,
        fallbackMode: mode,
        fallbackProjectId: currentProject?.id,
      });

      if (!parsed) {
        return;
      }

      setCurrentResult(parsed.result);
      setShowResult(true);

      const notificationKey = `result-${parsed.taskId ?? parsed.result.id}`;
      notification.success({
        key: notificationKey,
        message: '研究完成',
        description: (
          <div>
            <p>研究结果已生成，请查看结果面板</p>
            {parsed.taskId && (
              <Button
                type="link"
                size="small"
                onClick={() => {
                  setShowResult(true);
                  setCurrentResult(parsed.result);
                  setTimeout(() => {
                    const resultPanel = document.querySelector('.research-result-panel');
                    if (resultPanel) {
                      resultPanel.scrollIntoView({ behavior: 'smooth' });
                    }
                  }, 100);
                  notification.destroy(notificationKey);
                }}
              >
                跳转到结果 →
              </Button>
            )}
          </div>
        ),
        placement: 'topRight',
        duration: 8,
      });

      if (parsed.taskId) {
        void fetch(`/api/tasks/${parsed.taskId}/result`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            result_id: parsed.result.id,
            status: 'completed_with_result',
          }),
        }).catch((error) => {
          console.error('Failed to update task result link:', error);
        });
      }
    };

    const handleInteractionUpdate = (...args: unknown[]) => {
      const payload: unknown = args[0];
      console.log('Interaction update:', payload);
    };

    const handleExperienceGenerated = (...args: unknown[]) => {
      const payload: unknown = args[0];
      const count = getExperienceCount(payload);
      notification.success({
        message: '经验生成完成',
        description: `已生成 ${count ?? 0} 条研究经验`,
        placement: 'topRight',
      });
    };

    subscribe('task_progress', handleTaskProgress);
    subscribe('research_result', handleResearchResult);
    subscribe('interaction_update', handleInteractionUpdate);
    subscribe('experience_generated', handleExperienceGenerated);

    return () => {
      unsubscribe('task_progress', handleTaskProgress);
      unsubscribe('research_result', handleResearchResult);
      unsubscribe('interaction_update', handleInteractionUpdate);
      unsubscribe('experience_generated', handleExperienceGenerated);
      reset();
    };
  }, [subscribe, unsubscribe, reset, currentSessionQuery, mode, currentProject?.id]);

  useEffect(() => {
    void initialize();
  }, [initialize]);

  useEffect(() => {
    void initialize();
  }, [initialize]);

  useEffect(() => {
    if (!projectId) {
      return;
    }
    const numericId = Number(projectId);
    if (Number.isNaN(numericId)) {
      return;
    }
    if (currentProject && currentProject.id === numericId) {
      return;
    }
    const existing = availableProjects.find((project) => project.id === numericId);
    if (existing) {
      setCurrentProject(existing);
      return;
    }
    void projectAPI.getProject(numericId)
      .then((project) => {
        setCurrentProject({
          id: project.id,
          title: project.title,
          description: project.description ?? undefined,
          created_at: project.created_at,
          updated_at: project.updated_at ?? undefined,
        });
      })
      .catch((error) => {
        console.error('Failed to load project context', error);
      });
  }, [projectId, availableProjects, currentProject, setCurrentProject]);

  useEffect(() => {
    void syncTasks(currentProject?.id);
  }, [syncTasks, currentProject?.id]);

  const handleQuerySubmit = useCallback(async (query: string, _options?: QueryOptions) => {
    void _options;
    if (!currentProject) {
      void message.error('请先选择一个项目');
      return;
    }

    try {
      await submitQuery(query, mode, currentProject.id);
      void message.success('研究查询已提交');
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '提交失败';
      void message.error(errorMessage);
    }
  }, [mode, currentProject, submitQuery]);

  const handleProjectChange = useCallback((_selectedId: number, project: Project) => {
    if (hideProjectSelector) {
      return;
    }
    setCurrentProject(project);
    void message.success(`已切换到项目: ${project.title}`);

    // 清理当前研究状态
    reset();
    setCurrentResult(null);
    setShowResult(false);
  }, [setCurrentProject, reset, hideProjectSelector]);

  const handleModeChange = useCallback((newMode: ResearchMode) => {
    setMode(newMode);

    // 根据模式显示不同的提示
    const modeMessages: Record<ResearchMode, string> = {
      rag: 'RAG模式：从现有知识库中检索相关内容',
      deep: '深度研究模式：生成专属研究经验',
      auto: '全自动模式：AI智能调度完整研究流程',
    };
    void message.info(modeMessages[newMode]);
  }, []);

  const handleCancelTask = useCallback(async (task: Task) => {
    if (task.backendTaskId === undefined) {
      void message.warning('任务尚未生成后台记录，请稍候重试');
      return;
    }

    try {
      const response = await cancelTaskRequest(task.backendTaskId);
      updateTask(String(task.backendTaskId ?? task.id), {
        status: 'cancelled',
      });
      void message.success(response?.message ?? '任务已取消');
      await syncTasks(currentProject?.id);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '取消任务失败';
      void message.error(errorMessage);
    }
  }, [currentProject?.id, syncTasks, updateTask]);

  const handleRetryTask = useCallback(async (task: Task) => {
    if (task.backendTaskId === undefined) {
      void message.warning('任务尚未完成初始化，无法重试');
      return;
    }

    try {
      await retryTaskRequest(task.backendTaskId, true);
      void message.success('任务已重新排队');
      await syncTasks(currentProject?.id);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '重试任务失败';
      void message.error(errorMessage);
    }
  }, [currentProject?.id, syncTasks]);

  const renderHistoryItem = useCallback((item: ClarificationHistoryEntry) => {
    const timeText = formatDisplayDate(item.time) ?? item.time;
    if (item.type === 'select-option' && item.option) {
      return (
        <List.Item
          key={item.id}
          actions={[
            <Button
              key="copy"
              size="small"
              onClick={() => {
                void navigator.clipboard.writeText(item.option?.title ?? '');
              }}
            >
              复制
            </Button>,
          ]}
        >
          <List.Item.Meta
            title={(
              <Space size={8}>
                <Tag color="blue">选择</Tag>
                <Text>{item.option?.title}</Text>
              </Space>
            )}
            description={timeText}
          />
          {item.option?.description && (
            <Text type="secondary">{item.option.description}</Text>
          )}
        </List.Item>
      );
    }

    if (item.type === 'custom-input') {
      return (
        <List.Item
          key={item.id}
          actions={[
            <Button
              key="copy"
              size="small"
              onClick={() => {
                void navigator.clipboard.writeText(item.input ?? '');
              }}
            >
              复制
            </Button>,
          ]}
        >
          <List.Item.Meta
            title={(
              <Space size={8}>
                <Tag color="purple">自定义</Tag>
                <Text>{(item.input ?? '').slice(0, 40)}{item.input && item.input.length > 40 ? '…' : ''}</Text>
              </Space>
            )}
            description={timeText}
          />
        </List.Item>
      );
    }

    if (item.type === 'auto-select' && item.option) {
      return (
        <List.Item key={item.id}>
          <List.Item.Meta
            title={(
              <Space size={8}>
                <Tag color="green">自动推荐</Tag>
                <Text>{item.option?.title}</Text>
              </Space>
            )}
            description={timeText}
          />
        </List.Item>
      );
    }

    return (
      <List.Item key={item.id}>
        <List.Item.Meta
          title={(
            <Space size={8}>
              <Tag>超时</Tag>
              <Text>系统自动处理</Text>
            </Space>
          )}
          description={timeText}
        />
      </List.Item>
    );
  }, []);

  return (
    <Layout className="min-h-screen bg-gray-50">
      <Content className="p-4 md:p-6">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
        >
          <Space direction="vertical" size="large" style={{ width: '100%' }}>
            <Card className="shadow-sm border-0">
              <Row gutter={[24, 16]}>
                <Col xs={12} md={6}>
                  <Statistic title="活跃任务" value={totalTasks} />
                </Col>
                <Col xs={12} md={6}>
                  <Statistic title="执行中" value={taskSummary.running} suffix="项" />
                </Col>
                <Col xs={12} md={6}>
                  <Statistic title="已完成" value={taskSummary.completed} suffix="项" />
                </Col>
                <Col xs={12} md={6}>
                  <Statistic
                    title="最新置信度"
                    value={latestConfidence ?? '--'}
                    suffix={latestConfidence !== null ? '%' : undefined}
                  />
                </Col>
              </Row>
              <Space direction="vertical" size={4} style={{ marginTop: 16 }}>
                {currentProject ? (
                  <Text type="secondary">
                    当前项目：<Text strong>{currentProject.title}</Text>
                  </Text>
                ) : (
                  <Text type="secondary">当前尚未选择项目</Text>
                )}
                {latestAnswerPreview && (
                  <Text type="secondary">
                    最新结果：{latestAnswerPreview}
                    {latestAnswerPreview.length >= 80 && '...'}
                  </Text>
                )}
              </Space>
            </Card>

            <Row gutter={[24, 24]}>
              <Col xs={24} xl={16}>
                <Space direction="vertical" size="large" style={{ width: '100%' }}>
                  <Card className="shadow-sm border-0">
                    <div className="flex justify-between items-center flex-wrap gap-4">
                      <div>
                        <h2 className="text-2xl font-bold m-0">研究工作台</h2>
                        {currentProject && (
                          <p className="text-gray-500 m-0 mt-1">
                            当前项目: {currentProject.title}
                          </p>
                        )}
                      </div>
                      <Space wrap>
                        {hideProjectSelector ? (
                          currentProject ? <Tag color="geekblue">{currentProject.title}</Tag> : null
                        ) : (
                          <ProjectSelector
                            value={currentProject?.id}
                            onChange={handleProjectChange}
                          />
                        )}
                        <ModeSelector value={mode} onChange={handleModeChange} />
                      </Space>
                    </div>
                  </Card>

                  <Card className="shadow-lg border-0">
                    <SmartQueryInput
                      onSubmit={handleQuerySubmit}
                      mode={mode}
                      disabled={isLoading}
                      placeholder={
                        mode === 'rag'
                          ? '输入您想从知识库中查询的问题...'
                          : mode === 'deep'
                          ? '输入需要深度研究的科研问题...'
                          : '输入您的研究问题，AI将自动编排研究流程...'
                      }
                    />
                  </Card>

                  <AnimatePresence mode="wait">
                    {currentCard && currentSession && (
                      <motion.div
                        key="interaction"
                        initial={{ opacity: 0, scale: 0.95 }}
                        animate={{ opacity: 1, scale: 1 }}
                        exit={{ opacity: 0, scale: 0.95 }}
                        transition={{ duration: 0.3 }}
                      >
                        <InteractionCards
                          sessionId={currentSession.session_id ?? currentSession.id}
                          card={currentCard}
                        />
                      </motion.div>
                    )}
                  </AnimatePresence>

                  <AnimatePresence mode="wait">
                    {(() => {
                      const displayResult = currentResult || results[0];
                      if (!showResult && !displayResult) {
                        return null;
                      }
                      if (!displayResult) {
                        return null;
                      }
                      return (
                        <motion.div
                          key="results"
                          initial={{ opacity: 0, y: 20 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -20 }}
                          transition={{ duration: 0.3 }}
                        >
                          <ResearchResultPanel
                            result={displayResult}
                            onExport={() => {
                              void message.info('导出功能开发中...');
                            }}
                            onShare={() => {
                              void message.info('分享功能开发中...');
                            }}
                            onRegenerateExperience={() => {
                              void message.info('正在重新生成经验...');
                            }}
                          />
                        </motion.div>
                      );
                    })()}
                  </AnimatePresence>

                  {error && (
                    <Card className="shadow-sm border-red-200 bg-red-50">
                      <div className="text-red-600">{error}</div>
                    </Card>
                  )}
                </Space>
              </Col>

              <Col xs={24} xl={8}>
                <Space direction="vertical" size="large" style={{ width: '100%' }}>
                  <Card title="当前项目" className="shadow-sm border-0">
                    {currentProject ? (
                      <Space direction="vertical" size={6} style={{ width: '100%' }}>
                        <Text strong>{currentProject.title}</Text>
                        {currentProject.description && (
                          <Text type="secondary">{currentProject.description}</Text>
                        )}
                        {projectCreatedAt && (
                          <Text type="secondary">创建于：{projectCreatedAt}</Text>
                        )}
                      </Space>
                    ) : (
                      <Empty description="尚未选择项目" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    )}
                  </Card>

                  <Card title="当前会话" className="shadow-sm border-0">
                    {currentSession ? (
                      <Space direction="vertical" size={6} style={{ width: '100%' }}>
                        <Space size={8} align="center">
                          <Text type="secondary">模式：</Text>
                          {renderModeTag(sessionModeValue)}
                        </Space>
                        <Text>问题：{sessionQueryDisplay || '尚未记录'}</Text>
                        {sessionIdentifier && (
                          <Text type="secondary">会话 ID：{sessionIdentifier}</Text>
                        )}
                        {sessionStartedAt && (
                          <Text type="secondary">启动时间：{sessionStartedAt}</Text>
                        )}
                      </Space>
                    ) : (
                      <Empty description="尚未启动会话" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    )}
                  </Card>

                  <Card title="澄清历史" className="shadow-sm border-0">
                    {clarificationHistory.length ? (
                      <List
                        size="small"
                        dataSource={clarificationHistory}
                        renderItem={renderHistoryItem}
                      />
                    ) : (
                      <Empty description="暂无澄清记录" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    )}
                  </Card>

                  <Card title="任务进度" className="shadow-sm border-0">
                    {activeTasks.length ? (
                      <Collapse accordion ghost>
                        {activeTasks.map((task) => (
                          <Panel header={renderTaskHeader(task)} key={task.id}>
                            <ProgressPanel
                              task={task}
                              onCancel={() => handleCancelTask(task)}
                              onRetry={() => handleRetryTask(task)}
                            />
                          </Panel>
                        ))}
                      </Collapse>
                    ) : (
                      <Empty description="暂无运行中的任务" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    )}
                  </Card>

                  <Card title="最近研究结果" className="shadow-sm border-0">
                    {results.length ? (
                      <List
                        dataSource={results.slice(0, 5)}
                        renderItem={(item) => (
                          <List.Item
                            key={item.id}
                            onClick={() => handleSelectResult(item)}
                            style={{ cursor: 'pointer' }}
                            actions={[
                              <Tag key="confidence" color="blue">
                                {Math.round(Math.min(Math.max((item.confidence ?? 0) * 100, 0), 100))}%
                              </Tag>,
                            ]}
                          >
                            <List.Item.Meta
                              title={(
                                <Space size={8}>
                                  {renderModeTag(item.mode)}
                                  <Text>{item.question}</Text>
                                </Space>
                              )}
                              description={formatDisplayDate(item.timestamp) ?? item.timestamp}
                            />
                          </List.Item>
                        )}
                      />
                    ) : (
                      <Empty description="暂无研究结果" image={Empty.PRESENTED_IMAGE_SIMPLE} />
                    )}
                  </Card>

                  <Card className="shadow-sm border-0" size="small">
                    <div className="flex items-center justify-between">
                      <span className="text-gray-600">实时连接</span>
                      <div className="flex items-center gap-2">
                        <div
                          className={`w-2 h-2 rounded-full ${
                            isConnected ? 'bg-green-500' : 'bg-red-500'
                          } animate-pulse`}
                        />
                        <span className="text-sm">
                          {isConnected ? '已连接' : '未连接'}
                        </span>
                      </div>
                    </div>
                  </Card>

                  {isLoading && activeTasks.length === 0 && (
                    <Card className="shadow-sm border-0">
                      <div className="text-center py-8">
                        <Spin size="large" />
                        <div className="mt-4 text-gray-600">AI正在处理您的请求...</div>
                      </div>
                    </Card>
                  )}
                </Space>
              </Col>
            </Row>
          </Space>
        </motion.div>
      </Content>
    </Layout>
  );
};

export default ResearchWorkspace;
