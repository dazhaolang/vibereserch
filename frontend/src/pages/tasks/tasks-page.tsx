import { useCallback, useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { message } from 'antd';

import { cancelTask, fetchTasks, retryTask, type TaskDetail } from '@/services/api/tasks';
import { MotionFade } from '@/animations/motion-fade';
import styles from './tasks-page.module.css';
import { TaskRow } from '@/components/tasks/task-row';
import { TaskDetailDrawer } from '@/components/tasks/task-detail-drawer';
import { useAppStore } from '@/store/app-store';

interface TasksPageProps {
  projectId?: number;
}

export function TasksPage({ projectId }: TasksPageProps) {
  const [activeTaskId, setActiveTaskId] = useState<number | null>(null);
  const setTasks = useAppStore((state) => state.setTasks);
  const taskBuckets = useAppStore((state) => state.tasks);
  const updateTask = useAppStore((state) => state.updateTask);
  const { data } = useQuery({
    queryKey: ['tasks', projectId ?? 'all'],
    queryFn: () => fetchTasks(projectId ? { project_id: projectId } : undefined),
    refetchInterval: 5000,
  });

  const [actionLoading, setActionLoading] = useState<Record<number, { cancel?: boolean; retry?: boolean }>>({});

  const setLoadingState = useCallback((taskId: number, key: 'cancel' | 'retry', value: boolean) => {
    setActionLoading((prev) => ({
      ...prev,
      [taskId]: {
        ...prev[taskId],
        [key]: value,
      },
    }));
  }, []);

  useEffect(() => {
    if (data && Array.isArray(data)) {
      setTasks(data);
    }
  }, [data, setTasks]);

  const tasks = useMemo(() => {
    const merged = [...taskBuckets.active, ...taskBuckets.completed, ...taskBuckets.failed];
    const filtered = projectId ? merged.filter((task) => task.project_id === projectId) : merged;
    return filtered.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
  }, [taskBuckets, projectId]);

  const normalizeTaskDetail = (detail: TaskDetail) => ({
    id: detail.id,
    project_id: detail.project_id,
    task_type: detail.task_type,
    title: detail.title,
    status: detail.status,
    progress_percentage: detail.progress_percentage,
    current_step: detail.current_step,
    created_at: detail.created_at,
    updated_at: detail.updated_at,
    cost_estimate: detail.cost_estimate,
    token_usage: detail.token_usage,
    error_message: detail.error_message,
  });

  const handleCancelTask = useCallback(async (taskId: number) => {
    setLoadingState(taskId, 'cancel', true);
    try {
      const response = await cancelTask(taskId);
      void message.success(response?.message ?? '任务已取消');
      const existing = tasks.find((task) => task.id === taskId);
      if (existing) {
        updateTask({ ...existing, status: 'cancelled' });
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '取消任务失败';
      void message.error(errorMessage);
    } finally {
      setLoadingState(taskId, 'cancel', false);
    }
  }, [setLoadingState, tasks, updateTask]);

  const handleRetryTask = useCallback(async (taskId: number) => {
    setLoadingState(taskId, 'retry', true);
    try {
      const result = await retryTask(taskId, true);
      void message.success('任务已重新排队');
      updateTask(normalizeTaskDetail(result));
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '重试任务失败';
      void message.error(errorMessage);
    } finally {
      setLoadingState(taskId, 'retry', false);
    }
  }, [setLoadingState, updateTask]);

  return (
    <MotionFade>
      <section className={styles.panel}>
        <header>
          <h2>任务列表</h2>
          <span>{tasks.length} 个</span>
        </header>
        <div className={styles.list}>
          {tasks.map((task) => (
            <TaskRow
              key={task.id}
              task={task}
              onSelect={() => setActiveTaskId(task.id)}
              onCancel={() => handleCancelTask(task.id)}
              onRetry={() => handleRetryTask(task.id)}
              disableCancel={!['running', 'processing', 'pending'].includes(task.status?.toLowerCase?.() ?? task.status)}
              disableRetry={!['failed', 'cancelled'].includes(task.status?.toLowerCase?.() ?? task.status)}
              loadingCancel={actionLoading[task.id]?.cancel}
              loadingRetry={actionLoading[task.id]?.retry}
            />
          ))}
        </div>
        <TaskDetailDrawer taskId={activeTaskId} onClose={() => setActiveTaskId(null)} />
      </section>
    </MotionFade>
  );
}
