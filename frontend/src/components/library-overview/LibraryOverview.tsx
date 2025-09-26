import { memo } from 'react';
import { Button, Empty, Skeleton, Tag, Tooltip } from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import { motion } from 'framer-motion';
import classNames from 'classnames';
import styles from './library-overview.module.css';
import type { ProjectSummary, ProjectStatus } from '@/services/api/project';
import type { LibraryStatus } from '@/stores/research-shell.store';

interface LibraryOverviewProps {
  projects: ProjectSummary[];
  selectedProjectId: number | null;
  isLoading?: boolean;
  isRefreshing?: boolean;
  onSelect: (projectId: number | null) => void;
  onCreateNew?: () => void;
  onRefresh?: () => void;
}

const statusMeta: Record<ProjectStatus, {
  label: string;
  tagColor: string;
  hint: string;
  libraryStatus: LibraryStatus;
}> = {
  empty: {
    label: '待启动',
    tagColor: 'default',
    hint: '尚未开始构建，可快速启动',
    libraryStatus: 'ready',
  },
  active: {
    label: '进行中',
    tagColor: 'blue',
    hint: '可直接用于研究',
    libraryStatus: 'ready',
  },
  completed: {
    label: '已完成',
    tagColor: 'green',
    hint: '数据构建完毕，适合长期使用',
    libraryStatus: 'ready',
  },
  archived: {
    label: '已归档',
    tagColor: 'gold',
    hint: '只读模式，仍可查询历史内容',
    libraryStatus: 'ready',
  },
  pending: {
    label: '排队中',
    tagColor: 'orange',
    hint: '等待处理队列，即将开始构建',
    libraryStatus: 'building',
  },
  processing: {
    label: '构建中',
    tagColor: 'purple',
    hint: '正在构建或合并文献，请稍候',
    libraryStatus: 'building',
  },
  unknown: {
    label: '未知状态',
    tagColor: 'default',
    hint: '状态未同步，可尝试刷新',
    libraryStatus: 'ready',
  },
};

const libraryStatusLabel: Record<LibraryStatus, string> = {
  unselected: '未选择',
  ready: '可用',
  building: '构建中',
  merging: '合并中',
  error: '异常',
};

const clampProgress = (value?: number | null): number | null => {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    return null;
  }
  if (!Number.isFinite(value)) {
    return null;
  }
  return Math.min(100, Math.max(0, Math.round(value)));
};

const renderSkeletons = () => (
  <div className={styles.grid}>
    {[1, 2, 3].map((key) => (
      <div key={key} className={styles.skeletonCard}>
        <Skeleton active title paragraph={{ rows: 3 }} />
      </div>
    ))}
  </div>
);

export const LibraryOverview = memo(function LibraryOverview({
  projects,
  selectedProjectId,
  isLoading = false,
  isRefreshing = false,
  onSelect,
  onCreateNew,
  onRefresh,
}: LibraryOverviewProps) {
  const hasProjects = projects.length > 0;

  return (
    <section className={styles.wrapper}>
      <header className={styles.header}>
        <div>
          <h2 className={styles.title}>文献库概览</h2>
          <p className={styles.subtitle}>选择或新建文献库，查看构建进度与可用状态</p>
        </div>
        <div className={styles.actions}>
          {onRefresh ? (
            <Button
              icon={<ReloadOutlined />}
              onClick={() => onRefresh()}
              loading={isRefreshing}
            >
              刷新
            </Button>
          ) : null}
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => onCreateNew?.()}
          >
            新建文献库
          </Button>
        </div>
      </header>

      {isLoading ? renderSkeletons() : null}

      {!isLoading && hasProjects ? (
        <div className={styles.grid}>
          {projects.map((project) => {
            const status = statusMeta[project.status ?? 'unknown'] ?? statusMeta.unknown;
            const progress = clampProgress(project.progress_percentage);
            const isSelected = project.id === selectedProjectId;

            return (
              <motion.button
                key={project.id}
                type="button"
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                className={classNames(styles.card, {
                  [styles.selected]: isSelected,
                })}
                onClick={() => onSelect(project.id)}
              >
                <div className={styles.cardHeader}>
                  <span className={styles.cardTitle}>{project.name}</span>
                  <Tag color={status.tagColor} className={styles.statusTag}>
                    {status.label}
                  </Tag>
                </div>
                {project.description ? (
                  <p className={styles.description}>{project.description}</p>
                ) : null}
                <dl className={styles.metrics}>
                  <div>
                    <dt>文献数量</dt>
                    <dd>{project.literature_count ?? 0} 篇</dd>
                  </div>
                  <div>
                    <dt>预计完成度</dt>
                    <dd>{progress !== null ? `${progress}%` : '—'}</dd>
                  </div>
                </dl>
                <footer className={styles.footer}>
                  <Tooltip title={status.hint} placement="bottomLeft">
                    <span className={classNames(styles.statusBadge, styles[status.libraryStatus])}>
                      {libraryStatusLabel[status.libraryStatus]}
                    </span>
                  </Tooltip>
                  <span className={styles.badgeHint}>点击进入详情</span>
                </footer>
              </motion.button>
            );
          })}
          <motion.button
            type="button"
            whileHover={{ scale: 1.01 }}
            whileTap={{ scale: 0.98 }}
            className={classNames(styles.card, styles.createCard)}
            onClick={() => onCreateNew?.()}
          >
            <div className={styles.createIcon}>
              <PlusOutlined />
            </div>
            <h3 className={styles.cardTitle}>新建文献库</h3>
            <p className={styles.description}>
              通过 AI 构建、PDF 上传或 DOI 检索快速扩充您的研究资料。
            </p>
            <span className={styles.badgeHint}>开始构建</span>
          </motion.button>
        </div>
      ) : null}

      {!isLoading && !hasProjects ? (
        <div className={styles.empty}>
          <Empty
            description="暂无文献库，点击右上角按钮开始构建"
            image={Empty.PRESENTED_IMAGE_SIMPLE}
          />
        </div>
      ) : null}
    </section>
  );
});

export type { LibraryOverviewProps };
