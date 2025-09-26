import React, { useEffect, useState, useRef } from 'react';
import { Steps, Progress, Timeline, Tag, Collapse, Space, Button, Tooltip } from 'antd';
import {
  LoadingOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  ReloadOutlined,
  ExpandOutlined,
  CompressOutlined,
} from '@ant-design/icons';
import { motion, AnimatePresence } from 'framer-motion';
import { useWebSocket } from '@/hooks/useWebSocket';
import type { Task, TaskProgress, TaskProgressDetails } from '@/types';

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const isTaskProgressMessage = (value: unknown): value is TaskProgress => {
  if (!isRecord(value)) {
    return false;
  }

  return typeof value.task_id === 'string' && typeof value.status === 'string';
};

const getNumericDetail = (value: unknown): number | undefined =>
  typeof value === 'number' ? value : undefined;

const isTaskProgressDetails = (value: unknown): value is TaskProgressDetails => isRecord(value);

interface ProgressPanelProps {
  task: Task;
  onCancel?: () => void;
  onRetry?: () => void;
}

interface StageInfo {
  title: string;
  description: string;
  expectedDuration?: number; // 秒
}

const TASK_STAGES: Record<string, StageInfo[]> = {
  'literature_collection': [
    { title: '初始化', description: '准备搜索环境', expectedDuration: 2 },
    { title: '搜索文献', description: '从多个数据源搜索', expectedDuration: 10 },
    { title: '筛选去重', description: '去除重复文献', expectedDuration: 5 },
    { title: '质量评估', description: 'AI质量评分', expectedDuration: 8 },
    { title: '入库', description: '保存到数据库', expectedDuration: 3 },
  ],
  'search_and_build_library': [
    { title: '搜索', description: '搜索相关文献', expectedDuration: 10 },
    { title: 'AI筛选', description: '智能质量评估', expectedDuration: 15 },
    { title: 'PDF下载', description: '批量下载PDF', expectedDuration: 20 },
    { title: '内容提取', description: '解析PDF内容', expectedDuration: 15 },
    { title: '结构化处理', description: '提取结构化数据', expectedDuration: 20 },
    { title: '数据入库', description: '保存处理结果', expectedDuration: 5 },
  ],
  'experience_generation': [
    { title: '准备', description: '加载文献数据', expectedDuration: 3 },
    { title: '第1轮迭代', description: '初始知识提取', expectedDuration: 30 },
    { title: '第2轮迭代', description: '知识深化', expectedDuration: 30 },
    { title: '第3轮迭代', description: '知识整合', expectedDuration: 30 },
    { title: '第4轮迭代', description: '知识优化', expectedDuration: 30 },
    { title: '第5轮迭代', description: '最终总结', expectedDuration: 30 },
    { title: '完成', description: '生成研究经验', expectedDuration: 5 },
  ],
  'analysis': [
    { title: '数据准备', description: '加载分析数据', expectedDuration: 5 },
    { title: '分析处理', description: 'AI深度分析', expectedDuration: 20 },
    { title: '生成结果', description: '整理分析结果', expectedDuration: 10 },
  ],
  'auto_pipeline': [
    { title: '编排任务', description: '分析研究目标并规划任务链', expectedDuration: 8 },
    { title: '执行搜索', description: '调用搜索建库工具', expectedDuration: 15 },
    { title: '处理文献', description: '解析并结构化文献', expectedDuration: 20 },
    { title: '生成经验', description: '生成经验与回答', expectedDuration: 15 },
  ],
};

export const ProgressPanel: React.FC<ProgressPanelProps> = ({ task, onCancel, onRetry }) => {
  const [currentProgress, setCurrentProgress] = useState<TaskProgress | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isPaused, setIsPaused] = useState(false);
  const [elapsedTime, setElapsedTime] = useState(0);
  const startTimeRef = useRef<number>(Date.now());
  const { subscribe } = useWebSocket();

  useEffect(() => {
    startTimeRef.current = Date.now();
    const timer = setInterval(() => {
      setElapsedTime(Math.floor((Date.now() - startTimeRef.current) / 1000));
    }, 1000);

    return () => clearInterval(timer);
  }, [task.id]);

  useEffect(() => {
    const handler = (...args: unknown[]) => {
      const payload = args[0];
      if (!isTaskProgressMessage(payload)) {
        return;
      }

      const matchesTask =
        String(payload.task_id) === String(task.backendTaskId ?? '') ||
        String(payload.task_id) === String(task.id);

      if (!matchesTask) {
        return;
      }

      setCurrentProgress(payload);

      if (payload.log) {
        setLogs((prev) => [
          ...prev,
          `[${new Date().toLocaleTimeString()}] ${payload.log}`,
        ]);
      }
      if (payload.step_result) {
        const resultText = typeof payload.step_result === 'string'
          ? payload.step_result
          : JSON.stringify(payload.step_result);
        setLogs((prev) => [
          ...prev,
          `[${new Date().toLocaleTimeString()}] ${resultText}`,
        ]);
      }
    };

    const unsubscribeFn = subscribe('task_progress', handler);

    return () => {
      unsubscribeFn();
    };
  }, [task, subscribe]);

  const getStageIcon = (status?: string) => {
    switch (status) {
      case 'processing':
        return <LoadingOutlined className="text-blue-500" spin />;
      case 'completed':
        return <CheckCircleOutlined className="text-green-500" />;
      case 'failed':
        return <CloseCircleOutlined className="text-red-500" />;
      case 'paused':
        return <PauseCircleOutlined className="text-yellow-500" />;
      default:
        return <ClockCircleOutlined className="text-gray-400" />;
    }
  };

  const normalizedStatus = task.status === 'running' ? 'processing' : task.status;

  const getProgressStatus = () => {
    if (normalizedStatus === 'failed') return 'exception';
    if (normalizedStatus === 'completed') return 'success';
    if (isPaused) return 'normal';
    return 'active';
  };

  const stages = TASK_STAGES[task.type] || [];
  const currentStageIndex = currentProgress?.current_stage || 0;
  const overallProgress =
    currentProgress?.overall_progress ?? currentProgress?.progress ?? task.progress ?? 0;

  const formatTime = (seconds: number) => {
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = seconds % 60;

    if (hours > 0) {
      return `${hours}小时${minutes}分${secs}秒`;
    } else if (minutes > 0) {
      return `${minutes}分${secs}秒`;
    } else {
      return `${secs}秒`;
    }
  };

  const estimateRemainingTime = () => {
    if (!currentProgress || overallProgress === 0) return null;

    const elapsed = elapsedTime;
    const rate = overallProgress / 100;

    if (rate > 0) {
      const totalTime = elapsed / rate;
      const remaining = Math.max(0, totalTime - elapsed);
      return Math.ceil(remaining);
    }

    return null;
  };

  const remainingTime = estimateRemainingTime();

  const progressDetails = isTaskProgressDetails(currentProgress?.details)
    ? currentProgress.details
    : undefined;
  const filesProcessed = getNumericDetail(progressDetails?.files_processed);
  const successCount = getNumericDetail(progressDetails?.success_count);
  const failedCount = getNumericDetail(progressDetails?.failed_count);

  return (
    <div className="progress-panel">
      <Space direction="vertical" className="w-full" size="large">
        {/* 总体进度 */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="bg-gradient-to-r from-blue-50 to-indigo-50 p-4 rounded-lg"
        >
          <div className="flex justify-between items-center mb-2">
            <div className="flex items-center gap-2">
              <span className="font-semibold">总体进度</span>
              <Tag color={normalizedStatus === 'completed' ? 'success' : 'processing'}>
                {normalizedStatus === 'pending' && '等待中'}
                {normalizedStatus === 'processing' && '处理中'}
                {normalizedStatus === 'completed' && '已完成'}
                {normalizedStatus === 'failed' && '失败'}
              </Tag>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-sm text-gray-600">
                已用时：{formatTime(elapsedTime)}
              </span>
              {remainingTime && (
                <Tag color="blue">
                  预计剩余：{formatTime(remainingTime)}
                </Tag>
              )}
              {onCancel && normalizedStatus === 'processing' && (
                <Tooltip title="取消任务">
                  <Button
                    size="small"
                    danger
                    icon={<CloseCircleOutlined />}
                    onClick={onCancel}
                  >
                    取消
                  </Button>
                </Tooltip>
              )}
            </div>
          </div>

          <Progress
            percent={overallProgress}
            status={getProgressStatus()}
            strokeColor={{
              '0%': '#108ee9',
              '100%': '#87d068',
            }}
            format={(percent) => (
              <span className="text-sm font-medium">{percent}%</span>
            )}
          />

          {/* 控制按钮 */}
          <div className="flex justify-end gap-2 mt-3">
            <Tooltip title={isPaused ? '继续' : '暂停'}>
              <Button
                size="small"
                icon={isPaused ? <PlayCircleOutlined /> : <PauseCircleOutlined />}
                onClick={() => setIsPaused(!isPaused)}
                disabled={normalizedStatus !== 'processing'}
              >
                {isPaused ? '继续' : '暂停'}
              </Button>
            </Tooltip>

            <Tooltip title={onRetry ? '重试' : '暂不可用'}>
              <Button
                size="small"
                icon={<ReloadOutlined />}
                disabled={!onRetry || normalizedStatus === 'processing'}
                onClick={() => {
                  if (onRetry) {
                    onRetry();
                  }
                }}
              >
                重试
              </Button>
            </Tooltip>

            <Tooltip title={isExpanded ? '收起' : '展开'}>
              <Button
                size="small"
                icon={isExpanded ? <CompressOutlined /> : <ExpandOutlined />}
                onClick={() => setIsExpanded(!isExpanded)}
              >
                {isExpanded ? '收起' : '详情'}
              </Button>
            </Tooltip>
          </div>
        </motion.div>

        {/* 阶段进度 */}
        <Steps
          current={currentStageIndex}
          size="small"
          items={stages.map((stage, index) => {
            const isCurrentStage = index === currentStageIndex;
            const stageProgress = isCurrentStage ? (currentProgress?.progress || 0) :
                                index < currentStageIndex ? 100 : 0;

            return {
              title: (
                <div className="flex items-center gap-2">
                  <span>{stage.title}</span>
                  {isCurrentStage && normalizedStatus === 'processing' && (
                    <Tag color="processing" className="ml-2">
                      {stageProgress}%
                    </Tag>
                  )}
                </div>
              ),
              description: (
                <div className="text-xs">
                  <div>{stage.description}</div>
                  {isCurrentStage && currentProgress?.message && (
                    <div className="text-blue-600 mt-1">{currentProgress.message}</div>
                  )}
                </div>
              ),
              status: index < currentStageIndex ? 'finish' :
                     index === currentStageIndex ? 'process' : 'wait',
              icon: index === currentStageIndex ? getStageIcon(normalizedStatus) : undefined,
            };
          })}
        />

        {/* 详细日志 - 可展开 */}
        <AnimatePresence>
          {isExpanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
            >
              <Collapse ghost>
                <Collapse.Panel
                  header={`详细日志 (${logs.length} 条)`}
                  key="logs"
                  className="bg-gray-50"
                >
                  <div className="max-h-60 overflow-y-auto">
                    <Timeline
                      items={logs.map((log, index) => ({
                        key: index,
                        children: (
                          <motion.div
                            initial={{ opacity: 0, x: -20 }}
                            animate={{ opacity: 1, x: 0 }}
                            transition={{ delay: index * 0.05 }}
                            className="text-xs font-mono text-gray-600"
                          >
                            {log}
                          </motion.div>
                        ),
                        color: log.includes('错误') ? 'red' :
                              log.includes('警告') ? 'yellow' :
                              log.includes('成功') ? 'green' : 'blue',
                      }))}
                    />
                  </div>
                </Collapse.Panel>
              </Collapse>
            </motion.div>
          )}
        </AnimatePresence>

        {/* 统计信息 */}
        {progressDetails && (
          <div className="grid grid-cols-3 gap-2 text-xs">
            {typeof filesProcessed === 'number' && (
              <div className="bg-blue-50 p-2 rounded">
                <div className="text-gray-600">已处理文件</div>
                <div className="font-semibold">{filesProcessed}</div>
              </div>
            )}
            {typeof successCount === 'number' && (
              <div className="bg-green-50 p-2 rounded">
                <div className="text-gray-600">成功</div>
                <div className="font-semibold">{successCount}</div>
              </div>
            )}
            {typeof failedCount === 'number' && (
              <div className="bg-red-50 p-2 rounded">
                <div className="text-gray-600">失败</div>
                <div className="font-semibold">{failedCount}</div>
              </div>
            )}
          </div>
        )}
      </Space>
    </div>
  );
};
