import { useEffect, useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { message } from 'antd';
import { cancelTask, fetchTaskDetail, retryTask } from '@/services/api/tasks';
import styles from './task-detail-drawer.module.css';
import { motion, AnimatePresence } from 'framer-motion';
import { useProgressSocket } from '@/services/ws/progress-socket';
import { useAuthStore } from '@/stores/auth-store';

interface Props {
  taskId: number | null;
  onClose: () => void;
}

export function TaskDetailDrawer({ taskId, onClose }: Props) {
  const token = useAuthStore((state) => state.accessToken);
  const events = useProgressSocket((state) => (taskId ? state.events[String(taskId)] ?? [] : []));
  const connect = useProgressSocket((state) => state.connect);
  const disconnect = useProgressSocket((state) => state.disconnect);
  const queryClient = useQueryClient();

  const { data, refetch } = useQuery({
    queryKey: ['task-detail', taskId],
    queryFn: () => fetchTaskDetail(taskId!),
    enabled: taskId !== null
  });

  const taskStatus = useMemo(() => data?.status?.toLowerCase?.() ?? data?.status ?? '', [data?.status]);
  const backendTaskId: number | undefined =
    typeof data?.id === 'number'
      ? data.id
      : typeof taskId === 'number'
        ? taskId
        : undefined;
  const isInProgress = taskStatus === 'running' || taskStatus === 'processing';

  const [isCancelling, setIsCancelling] = useState(false);
  const [isRetrying, setIsRetrying] = useState(false);

  const handleCancelTask = async () => {
    if (backendTaskId === undefined || isCancelling) {
      return;
    }
    setIsCancelling(true);
    try {
      const response = await cancelTask(backendTaskId);
      void message.success(response?.message ?? '任务已取消');
      await refetch();
      await queryClient.invalidateQueries({ queryKey: ['tasks'] });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '取消任务失败';
      void message.error(errorMessage);
    } finally {
      setIsCancelling(false);
    }
  };

  const handleRetryTask = async () => {
    if (backendTaskId === undefined || isRetrying) {
      return;
    }
    setIsRetrying(true);
    try {
      await retryTask(backendTaskId, true);
      void message.success('任务已重新排队');
      await refetch();
      await queryClient.invalidateQueries({ queryKey: ['tasks'] });
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : '重试任务失败';
      void message.error(errorMessage);
    } finally {
      setIsRetrying(false);
    }
  };

  const disableCancel = isCancelling || backendTaskId === undefined || !isInProgress;
  const disableRetry = isRetrying || backendTaskId === undefined || isInProgress;

  useEffect(() => {
    if (taskId) {
      void refetch();
      connect(String(taskId), token ?? undefined);
      return () => {
        disconnect(String(taskId));
      };
    }
    return () => undefined;
  }, [connect, disconnect, refetch, taskId, token]);

  return (
    <AnimatePresence>
      {taskId && (
        <motion.div
          className={styles.overlay}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
        >
          <motion.div className={styles.drawer} initial={{ x: '100%' }} animate={{ x: 0 }} exit={{ x: '100%' }}>
            <header>
              <h3>{data?.title ?? '任务详情'}</h3>
              <div className={styles.actions}>
                <button
                  onClick={handleCancelTask}
                  disabled={disableCancel}
                >
                  {isCancelling ? '取消中...' : '取消任务'}
                </button>
                <button
                  onClick={handleRetryTask}
                  disabled={disableRetry}
                >
                  {isRetrying ? '重试中...' : '重试任务'}
                </button>
                <button onClick={onClose}>关闭</button>
              </div>
            </header>
            <section>
              <dl>
                <div>
                  <dt>类型</dt>
                  <dd>{data?.task_type}</dd>
                </div>
                <div>
                  <dt>状态</dt>
                  <dd>{data?.status}</dd>
                </div>
                <div>
                  <dt>当前步骤</dt>
                  <dd>{data?.current_step}</dd>
                </div>
                <div>
                  <dt>进度</dt>
                  <dd>{data?.progress_percentage}%</dd>
                </div>
              </dl>
            </section>
            <section className={styles.result}>
              <h4>结果 / 错误</h4>
              <pre>{JSON.stringify(data?.result ?? data?.error_message ?? {}, null, 2)}</pre>
            </section>
            <section className={styles.timeline}>
              <h4>历史进度</h4>
              <div className={styles.events}>
                {data?.progress_logs?.length ? (
                  data.progress_logs.map((log, index) => (
                    <div key={`${log.step_name}-${index}`} className={styles.eventRow}>
                      <div>
                        <div className={styles.eventType}>{log.step_name}</div>
                        {log.step_description && <div>{log.step_description}</div>}
                      </div>
                      <div>
                        <span>{Math.round(log.progress_percentage)}%</span>
                        {log.completed_at && (
                          <div>{new Date(log.completed_at).toLocaleString()}</div>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className={styles.empty}>暂无历史进度</div>
                )}
              </div>
            </section>
            <section className={styles.timeline}>
              <h4>实时事件</h4>
              <div className={styles.events}>
                {events.length === 0 && <div className={styles.empty}>暂无实时事件</div>}
                {events.map((event, index) => (
                  <div key={`${event.type}-${index}`} className={styles.eventRow}>
                    <span className={styles.eventType}>{event.type}</span>
                    {event.current_step && <span>{event.current_step}</span>}
                    {typeof event.progress === 'number' && <span>{event.progress}%</span>}
                  </div>
                ))}
              </div>
            </section>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
