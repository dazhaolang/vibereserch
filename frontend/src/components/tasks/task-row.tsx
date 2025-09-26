import { Button, Tooltip } from 'antd';
import { StopOutlined, ReloadOutlined } from '@ant-design/icons';
import { motion } from 'framer-motion';
import styles from './task-row.module.css';

type TaskRowTask = {
  id: number;
  title: string;
  task_type: string;
  status: string;
  progress_percentage: number;
  current_step?: string;
};

interface Props {
  task: TaskRowTask;
  onSelect: () => void;
  onCancel?: () => void;
  onRetry?: () => void;
  disableCancel?: boolean;
  disableRetry?: boolean;
  loadingCancel?: boolean;
  loadingRetry?: boolean;
}

const statusColor: Record<string, string> = {
  running: '#38bdf8',
  pending: '#facc15',
  completed: '#4ade80',
  failed: '#f87171',
  cancelled: '#94a3b8',
};

export function TaskRow({
  task,
  onSelect,
  onCancel,
  onRetry,
  disableCancel,
  disableRetry,
  loadingCancel,
  loadingRetry,
}: Props) {
  const statusKey = task.status?.toLowerCase?.() ?? task.status;
  return (
    <motion.div
      role="button"
      tabIndex={0}
      className={styles.row}
      whileHover={{ scale: 1.01 }}
      onClick={onSelect}
      onKeyDown={(event) => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          onSelect();
        }
      }}
    >
      <span className={styles.title}>{task.title}</span>
      <span className={styles.type}>{task.task_type}</span>
      <div className={styles.progressBar}>
        <span className={styles.progressFill} style={{ width: `${task.progress_percentage}%` }} />
      </div>
      <span className={styles.status} style={{ color: statusColor[statusKey] ?? '#f8fafc' }}>
        {task.status}
      </span>
      <div className={styles.actions}>
        <Tooltip title={disableCancel ? '无法取消' : '取消任务'}>
          <Button
            size="small"
            icon={<StopOutlined />}
            onClick={(event) => {
              event.stopPropagation();
              onCancel?.();
            }}
            disabled={disableCancel}
            loading={loadingCancel}
          >
            取消
          </Button>
        </Tooltip>
        <Tooltip title={disableRetry ? '无法重试' : '重试任务'}>
          <Button
            size="small"
            icon={<ReloadOutlined />}
            onClick={(event) => {
              event.stopPropagation();
              onRetry?.();
            }}
            disabled={disableRetry}
            loading={loadingRetry}
            type="primary"
          >
            重试
          </Button>
        </Tooltip>
      </div>
    </motion.div>
  );
}
