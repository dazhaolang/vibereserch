import { useMemo } from 'react';
import { Alert, Button, Empty, List, Spin, Tag, Tooltip } from 'antd';
import { useQuery } from '@tanstack/react-query';
import type { LiteratureRelatedTask, TaskExtractionResult } from '@/services/api/tasks';
import { fetchLiteratureRelatedTasks } from '@/services/api/tasks';

interface Props {
  literatureId: number;
}

function renderExtraction(extractions: TaskExtractionResult[]) {
  if (!extractions.length) {
    return null;
  }

  return (
    <div style={{ marginTop: 8 }}>
      {extractions.slice(0, 2).map((item) => (
        <Tooltip key={`${item.id}-${item.extraction_type}`} title={item.content}>
          <Tag color="geekblue">{item.extraction_type}</Tag>
        </Tooltip>
      ))}
      {extractions.length > 2 ? <span style={{ marginLeft: 4 }}>…</span> : null}
    </div>
  );
}

function renderStatusTag(status: string) {
  const normalized = status.toLowerCase();
  const mapping: Record<string, { color: string; text: string }> = {
    pending: { color: 'default', text: '待处理' },
    running: { color: 'processing', text: '运行中' },
    processing: { color: 'processing', text: '运行中' },
    completed: { color: 'success', text: '已完成' },
    failed: { color: 'error', text: '失败' },
    cancelled: { color: 'warning', text: '已取消' },
  };
  const { color, text } = mapping[normalized] ?? { color: 'default', text: status };
  return <Tag color={color}>{text}</Tag>;
}

export function ZoteroTaskLinkage({ literatureId }: Props) {
  const query = useQuery({
    queryKey: ['literature-related-tasks', literatureId],
    queryFn: () => fetchLiteratureRelatedTasks(literatureId),
    enabled: literatureId > 0,
    staleTime: 30_000,
  });

  const tasks = useMemo(() => query.data?.tasks ?? [], [query.data?.tasks]);

  if (query.isLoading) {
    return (
      <div style={{ padding: '24px 0', textAlign: 'center' }}>
        <Spin tip="加载相关任务…" />
      </div>
    );
  }

  if (query.isError) {
    const errorMessage = query.error instanceof Error ? query.error.message : '加载相关任务失败';
    return (
      <Alert
        type="error"
        showIcon
        message="获取相关任务失败"
        description={(
          <div>
            <div style={{ marginBottom: 8 }}>{errorMessage}</div>
            <Button size="small" onClick={() => query.refetch()}>
              重试
            </Button>
          </div>
        )}
      />
    );
  }

  if (tasks.length === 0) {
    return <Empty description="暂无关联任务" />;
  }

  return (
    <List<LiteratureRelatedTask>
      size="small"
      dataSource={tasks}
      renderItem={(item) => (
        <List.Item
          key={item.id}
          actions={[
            item.progress !== null && item.progress !== undefined ? <span key="progress">进度 {item.progress}%</span> : null,
            item.result_url ? (
              <a key="result" href={item.result_url} target="_blank" rel="noreferrer">
                查看结果
              </a>
            ) : null,
          ].filter(Boolean)}
        >
          <List.Item.Meta
            title={(
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                {renderStatusTag(item.status)}
                <strong>{item.title || `任务 #${item.id}`}</strong>
                <Tag color="purple">{item.task_type}</Tag>
              </div>
            )}
            description={(
              <div>
                <div style={{ color: '#94a3b8', fontSize: 12 }}>
                  创建于 {new Date(item.created_at).toLocaleString()}
                  {item.updated_at ? ` · 更新于 ${new Date(item.updated_at).toLocaleString()}` : ''}
                </div>
                {item.description ? <div style={{ marginTop: 4 }}>{item.description}</div> : null}
                {item.error_message ? (
                  <Alert
                    style={{ marginTop: 8 }}
                    type="warning"
                    message="最新错误信息"
                    description={item.error_message}
                    showIcon
                  />
                ) : null}
                {renderExtraction(item.extraction_results ?? [])}
              </div>
            )}
          />
        </List.Item>
      )}
    />
  );
}

export default ZoteroTaskLinkage;
