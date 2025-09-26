import { useEffect, useMemo, useState, useCallback } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Alert, Button, Divider, Drawer, Empty, List, Modal, Spin, Tag, Typography, Space, message } from 'antd';
import { MotionFade } from '@/animations/motion-fade';
import { PerplexityShell } from '@/components/shell/PerplexityShell';
import { ModeCards } from '@/components/research/mode-cards';
import { useResearchShellStore, type ConversationMode, type LibraryStatus } from '@/stores/research-shell.store';
import type { ProjectSummary } from '@/services/api/project';
import { motion } from 'framer-motion';
import { shallow } from 'zustand/shallow';
import styles from './research-console.module.css';
import { useConversationStore } from '@/stores/conversation.store';
import { ConversationTimeline } from '@/components/conversation/ConversationTimeline';
import { ConversationComposer } from '@/components/conversation/ConversationComposer';
import { ConversationClarification } from '@/components/conversation/ConversationClarification';
import { useLibraryStore } from '@/stores/library.store';
import { useResearchStore } from '@/stores/research.store';
import { LibrarySelectorDialog } from '@/components/library-overview/LibrarySelectorDialog';
import { ResearchResultPanel } from '@/components/research/ResearchResultPanel';
import { researchAPI } from '@/services/api/research';
import type { ResearchResult } from '@/types';

const { Text } = Typography;

const libraryStatusMeta: Record<LibraryStatus, { label: string; color: string }> = {
  unselected: { label: '未选择', color: 'default' },
  ready: { label: '可用', color: 'blue' },
  building: { label: '构建中', color: 'processing' },
  merging: { label: '合并中', color: 'gold' },
  error: { label: '异常', color: 'red' },
};

const inferStatusFromProject = (project?: ProjectSummary | null): LibraryStatus => {
  if (!project) {
    return 'unselected';
  }
  if (project.status === 'processing' || project.status === 'pending') {
    return 'building';
  }
  if (project.status === 'completed' || project.status === 'active') {
    return 'ready';
  }
  if (project.status === 'archived') {
    return 'ready';
  }
  if (project.status === 'unknown') {
    return 'ready';
  }
  return 'ready';
};

export function ResearchConsole() {
  const location = useLocation();
  const navigate = useNavigate();
  const {
    mode,
    setMode,
    libraryId,
    setLibraryId,
    libraryStatus,
    setLibraryStatus,
  } = useResearchShellStore(
    (state) => ({
      mode: state.mode,
      setMode: state.setMode,
      libraryId: state.libraryId,
      setLibraryId: state.setLibraryId,
      libraryStatus: state.libraryStatus,
      setLibraryStatus: state.setLibraryStatus,
    }),
    shallow,
  );

  const {
    messages,
    isSending,
    error,
    sendMessage,
    reset,
  } = useConversationStore(
    (state) => ({
      messages: state.messages,
      isSending: state.isSending,
      error: state.error,
      sendMessage: state.sendMessage,
      reset: state.reset,
    }),
    shallow,
  );

  const {
    projects,
    isProjectsLoading,
    loadCollections,
    setSelectedProject,
  } = useLibraryStore((state) => ({
    projects: state.projects,
    isProjectsLoading: state.isProjectsLoading,
    loadCollections: state.loadCollections,
    setSelectedProject: state.setSelectedProject,
  }), shallow);

  const {
    results: researchResults,
    syncTasks,
    history,
    isHistoryLoading,
    loadHistory,
  } = useResearchStore((state) => ({
    results: state.results,
    syncTasks: state.syncTasks,
    history: state.history,
    isHistoryLoading: state.isHistoryLoading,
    loadHistory: state.loadHistory,
  }), shallow);

  const [selectorOpen, setSelectorOpen] = useState(false);
  const [autoPrompted, setAutoPrompted] = useState(false);

  const selectedProject = useMemo(
    () => projects.find((project) => project.id === libraryId) ?? null,
    [libraryId, projects],
  );

  const rawProgress = selectedProject?.progress_percentage as unknown;
  const numericProgress = typeof rawProgress === 'number' ? rawProgress : undefined;
  const formattedProgress = typeof numericProgress === 'number' ? `${Math.round(numericProgress)}%` : '—';
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyDetailOpen, setHistoryDetailOpen] = useState(false);
  const [selectedHistory, setSelectedHistory] = useState<ResearchResult | null>(null);
  const [messageApi, contextHolder] = message.useMessage();
  const [sharePreview, setSharePreview] = useState<{ token: string; loading: boolean; payload?: unknown; error?: string } | null>(null);

  const locationState = location.state as { forcedMode?: ConversationMode } | undefined;

  useEffect(() => {
    if (!libraryId && projects.length > 0) {
      const defaultProject = projects[0];
      setLibraryId(defaultProject.id);
      setLibraryStatus(inferStatusFromProject(defaultProject));
      setSelectedProject(defaultProject.id);
    }
  }, [libraryId, projects, setLibraryId, setLibraryStatus, setSelectedProject]);

  useEffect(() => {
    if (selectedProject) {
      const inferred = inferStatusFromProject(selectedProject);
      if (libraryStatus === 'unselected' || libraryStatus === 'ready') {
        setLibraryStatus(inferred);
      }
    }
  }, [libraryStatus, selectedProject, setLibraryStatus]);

  useEffect(() => {
    if (libraryId) {
      void syncTasks(libraryId);
    }
  }, [libraryId, syncTasks]);

  useEffect(() => {
    if (historyOpen) {
      void loadHistory(libraryId ?? undefined);
    }
  }, [historyOpen, libraryId, loadHistory]);

  const parseNumeric = (value: unknown): number | null => {
    if (typeof value === 'number' && Number.isFinite(value)) {
      return value;
    }
    if (typeof value === 'string') {
      const match = value.match(/\d+/);
      if (match) {
        const parsed = Number.parseInt(match[0], 10);
        return Number.isFinite(parsed) ? parsed : null;
      }
    }
    return null;
  };

  const extractTaskId = useCallback((result: ResearchResult): number | null => {
    const metadata = result.metadata ?? {};
    const candidate = result.task_id ?? metadata.task_id ?? metadata.taskId ?? metadata.taskID;
    const fromMetadata = parseNumeric(candidate);
    if (fromMetadata !== null) {
      return fromMetadata;
    }
    return parseNumeric(result.id);
  }, []);

  const handleExportResult = useCallback(async (result: ResearchResult) => {
    const taskId = extractTaskId(result);
    if (!taskId) {
      void messageApi.warning('无法导出结果：缺少任务 ID');
      return;
    }
    try {
      await researchAPI.exportResult(String(taskId), {
        format: 'json',
        include_sources: true,
        include_metadata: true,
      });
      void messageApi.success('已开始下载导出文件');
    } catch (error) {
      console.error(error);
      void messageApi.error('导出失败，请稍后重试');
    }
  }, [extractTaskId, messageApi]);

  const handleShareResult = useCallback(async (result: ResearchResult) => {
    const taskId = extractTaskId(result);
    if (!taskId) {
      void messageApi.warning('无法分享结果：缺少任务 ID');
      return;
    }
    try {
      const response = await researchAPI.shareResult(String(taskId), []);
      setSharePreview({ token: response.token, loading: true });
      try {
        const shared = await researchAPI.getSharedResult(response.token);
        setSharePreview({ token: response.token, loading: false, payload: shared.payload });
        // eslint-disable-next-line no-console
        console.info('Shared research preview', shared.payload);
      } catch (previewError) {
        console.warn('Failed to load share preview', previewError);
        setSharePreview({ token: response.token, loading: false, error: '分享数据预览失败' });
      }
      const shareUrl = response.share_url;
      const expiresAt = response.expires_at ? new Date(response.expires_at).toLocaleString() : null;
      if (shareUrl) {
        try {
          await navigator.clipboard.writeText(shareUrl);
          void messageApi.success(`分享链接已复制到剪贴板${expiresAt ? `（有效期至 ${expiresAt}）` : ''}`);
        } catch (copyError) {
          console.warn(copyError);
          void messageApi.success(`已生成分享链接${expiresAt ? `，有效期至 ${expiresAt}` : ''}`);
        }
      } else {
        void messageApi.success('已生成分享链接');
      }
    } catch (error) {
      console.error(error);
      void messageApi.error('分享失败，请稍后重试');
      setSharePreview(null);
    }
  }, [extractTaskId, messageApi]);

  const handleRegenerateResult = useCallback(async (result: ResearchResult) => {
    const taskId = extractTaskId(result);
    if (!taskId) {
      void messageApi.warning('无法重新生成：缺少任务 ID');
      return;
    }
    try {
      await researchAPI.retryResearch(String(taskId), { force: true });
      void messageApi.success('已重新排队后台任务');
      void syncTasks(result.project_id);
    } catch (error) {
      console.error(error);
      void messageApi.error('重新生成失败，请稍后重试');
    }
  }, [extractTaskId, messageApi, syncTasks]);

  useEffect(() => {
    if (locationState?.forcedMode) {
      setMode(locationState.forcedMode);
    }
  }, [locationState?.forcedMode, setMode]);

  useEffect(() => {
    reset();
  }, [mode, reset]);

  const disabledModes: ConversationMode[] = [];
  if (!libraryId) {
    disabledModes.push('rag', 'deep');
  }
  if (libraryStatus === 'building' || libraryStatus === 'merging') {
    disabledModes.push('deep');
  }

  useEffect(() => {
    if (projects.length === 0 && !isProjectsLoading) {
      void loadCollections();
    }
  }, [projects.length, isProjectsLoading, loadCollections]);

  const handleLibraryChange = useCallback((value: number | null) => {
    reset();
    setLibraryId(value ?? null);
    if (value === null) {
      setLibraryStatus('unselected');
      setSelectedProject(null);
    } else {
      const project = projects.find((item) => item.id === value) ?? null;
      if (project) {
        setLibraryStatus(inferStatusFromProject(project));
      }
      setSelectedProject(value);
    }
  }, [projects, reset, setLibraryId, setLibraryStatus, setSelectedProject]);

  const ensureSelectorOpen = useCallback(() => {
    setSelectorOpen(true);
    if (projects.length === 0 && !isProjectsLoading) {
      void loadCollections();
    }
  }, [projects.length, isProjectsLoading, loadCollections]);

  useEffect(() => {
    if (libraryId) {
      setAutoPrompted(false);
      return;
    }

    if (mode !== 'auto' && !autoPrompted && !isProjectsLoading) {
      setSelectorOpen(true);
      setAutoPrompted(true);
      if (projects.length === 0) {
        void loadCollections();
      }
    }
  }, [libraryId, mode, autoPrompted, isProjectsLoading, projects.length, loadCollections]);

  const librarySwitcher = (
    <div className={styles.librarySwitcher}>
      <span className={styles.libraryLabel}>文献库</span>
      {isProjectsLoading && projects.length === 0 ? (
        <Spin size="small" />
      ) : projects.length > 0 ? (
        <Button
          type="default"
          onClick={() => ensureSelectorOpen()}
          className={styles.libraryButton}
        >
          <span className={styles.libraryButtonText}>
            {selectedProject ? selectedProject.name : '选择文献库'}
          </span>
        </Button>
      ) : (
        <motion.div layout className={styles.emptyLibraryMessage}>
          <Text type="secondary">暂无文献库</Text>
          <Button type="link" size="small" onClick={() => navigate('/library')}>
            新建文献库
          </Button>
        </motion.div>
      )}
      <div className={styles.libraryStatusRow}>
        <Tag color={libraryStatusMeta[libraryStatus].color}>{libraryStatusMeta[libraryStatus].label}</Tag>
        {selectedProject ? (
          <Text type="secondary" className={styles.libraryMetrics}>
            {selectedProject.literature_count} 篇 · 进度{' '}
            {formattedProgress}
          </Text>
        ) : null}
      </div>
    </div>
  );

  const contextPanel = (
    <div className={styles.contextPanel}>
      <h3>文献库概览</h3>
      {selectedProject ? (
        <ul className={styles.contextList}>
          <li>
            <Text className={styles.contextLabel}>名称</Text>
            <Text>{selectedProject.name}</Text>
          </li>
          <li>
            <Text className={styles.contextLabel}>文献数量</Text>
            <Text>{selectedProject.literature_count}</Text>
          </li>
          <li>
            <Text className={styles.contextLabel}>当前状态</Text>
            <Tag color={libraryStatusMeta[libraryStatus].color}>{libraryStatusMeta[libraryStatus].label}</Tag>
          </li>
          <li>
            <Text className={styles.contextLabel}>构建进度</Text>
            <Text>{formattedProgress}</Text>
          </li>
        </ul>
      ) : (
        <Empty description="选择文献库以查看上下文" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      )}
      <Divider dashed style={{ margin: '16px 0' }}>
        最新研究结果
      </Divider>
      {researchResults.length > 0 ? (
        <ul className={styles.resultsList}>
          {researchResults.slice(0, 3).map((item) => (
            <li
              key={item.id}
              className={styles.resultItem}
              onClick={() => {
                setSelectedHistory(item);
                setHistoryDetailOpen(true);
              }}
              style={{ cursor: 'pointer' }}
            >
              <div className={styles.resultHeader}>
                <Tag color={item.mode === 'auto' ? 'blue' : item.mode === 'deep' ? 'gold' : 'green'}>
                  {item.mode.toUpperCase()}
                </Tag>
                <Text type="secondary" className={styles.resultTime}>
                  {item.timestamp ? new Date(item.timestamp).toLocaleString() : '时间未知'}
                </Text>
              </div>
              <Text strong className={styles.resultQuestion}>
                {item.question}
              </Text>
              {item.answer ? (
                <Text type="secondary" className={styles.resultPreview}>
                  {item.answer.replace(/\s+/g, ' ').slice(0, 80)}
                  {item.answer.length > 80 ? '…' : ''}
                </Text>
              ) : null}
            </li>
          ))}
        </ul>
      ) : (
        <Text type="secondary">尚无研究结果，尝试发起一次自动研究。</Text>
      )}
      <Button
        type="link"
        size="small"
        onClick={() => {
          if (libraryId) {
            void loadHistory(libraryId);
          } else {
            void loadHistory();
          }
          setHistoryOpen(true);
        }}
      >
        查看全部历史
      </Button>
      <div className={styles.contextFooter}>
        <Button type="default" block onClick={() => navigate('/library')}>
          管理文献库
        </Button>
      </div>
    </div>
  );

  const requiresLibrary = mode !== 'auto';
  const composerDisabled = requiresLibrary && (!libraryId || libraryStatus !== 'ready');

  const conversation = (
    <div className={styles.conversationArea}>
      {error ? (
        <Alert
          type="error"
          showIcon
          message="生成回答时出现问题"
          description={error}
          style={{ marginBottom: 12 }}
        />
      ) : null}
      <ConversationClarification
        projects={projects}
        selectedProjectId={libraryId}
        onProjectChange={handleLibraryChange}
      />
      <ConversationTimeline
        messages={messages}
        isLoading={isSending}
        emptyHint={
          requiresLibrary
            ? '选择文献库并提问，系统会结合文献给出回答。'
            : '输入研究目标，系统将自动开展研究任务。'
        }
      />
      <ConversationComposer
        mode={mode}
        libraryStatus={libraryStatus}
        isSending={isSending}
        disabled={composerDisabled}
        onSend={async (text) => {
          await sendMessage(text);
        }}
      />
    </div>
  );

  const handleDialogSelect = useCallback((id: number | null) => {
    handleLibraryChange(id);
  }, [handleLibraryChange]);

  const handleDialogClose = useCallback(() => {
    setSelectorOpen(false);
  }, []);

  const handleDialogCreate = useCallback(() => {
    setSelectorOpen(false);
    navigate('/library');
  }, [navigate]);

  return (
    <>
      {contextHolder}
      <MotionFade>
        <PerplexityShell
          librarySwitcher={librarySwitcher}
          modeBar={<ModeCards activeMode={mode} onChange={setMode} disabledModes={disabledModes} />}
          conversation={conversation}
          contextPanel={contextPanel}
        />
      </MotionFade>
      <LibrarySelectorDialog
        open={selectorOpen}
        onClose={handleDialogClose}
        onSelect={handleDialogSelect}
        onCreateNew={handleDialogCreate}
      />
      <Drawer
        title="研究历史"
        open={historyOpen}
        width={420}
        onClose={() => setHistoryOpen(false)}
      >
        {isHistoryLoading ? (
          <div style={{ textAlign: 'center', padding: 24 }}>
            <Spin />
          </div>
        ) : history.length > 0 ? (
          <List
            dataSource={history}
            renderItem={(item) => (
              <List.Item
                onClick={() => {
                  setSelectedHistory(item);
                  setHistoryDetailOpen(true);
                }}
                style={{ cursor: 'pointer' }}
              >
                <List.Item.Meta
                  title={
                    <Space size={8}>
                      <Tag color={item.mode === 'auto' ? 'blue' : item.mode === 'deep' ? 'gold' : 'green'}>
                        {item.mode.toUpperCase()}
                      </Tag>
                      <span>{item.question}</span>
                    </Space>
                  }
                  description={
                    <span>
                      {item.timestamp ? new Date(item.timestamp).toLocaleString() : '时间未知'} · 可信度 {Math.round((item.confidence ?? 0) * 100)}%
                    </span>
                  }
                />
              </List.Item>
            )}
          />
        ) : (
          <Empty description="暂无历史记录" />
        )}
      </Drawer>
      <Modal
        title="历史研究详情"
        open={historyDetailOpen}
        width={960}
        destroyOnClose
        onCancel={() => {
          setHistoryDetailOpen(false);
          setSelectedHistory(null);
        }}
        footer={null}
      >
        {selectedHistory ? (
          <ResearchResultPanel
            result={selectedHistory}
            onExport={handleExportResult}
            onShare={handleShareResult}
            onRegenerateExperience={handleRegenerateResult}
          />
        ) : null}
        {sharePreview && (
          <div style={{ marginTop: 16 }}>
            <Alert
              type={sharePreview.error ? 'error' : sharePreview.loading ? 'info' : 'success'}
              message={sharePreview.error ? '分享预览失败' : sharePreview.loading ? '正在加载分享预览' : '分享预览已记录'}
              description={
                sharePreview.error
                  ? sharePreview.error
                  : sharePreview.payload
                    ? '详细内容已输出到浏览器控制台，可用于构建分享页面。'
                    : undefined
              }
              showIcon
            />
          </div>
        )}
      </Modal>
    </>
  );
}
