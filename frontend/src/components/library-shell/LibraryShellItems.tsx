import { useMemo } from 'react';
import { Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { LiteratureItem } from '@/services/api/literature';
import { useLibraryStore } from '@/stores/library.store';
import styles from './library-shell-items.module.css';

export function LibraryItemsTable() {
  const {
    items,
    isLoading,
    selectedProjectId,
    selectedItemId,
    setSelectedItem,
  } = useLibraryStore((state) => ({
    items: state.items,
    isLoading: state.isLoading,
    selectedProjectId: state.selectedProjectId,
    selectedItemId: state.selectedItemId,
    setSelectedItem: state.setSelectedItem,
  }));

  const columns = useMemo<ColumnsType<LiteratureItem>>(() => [
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      ellipsis: true,
      render: (value: string) => <span className={styles.title}>{value}</span>,
    },
    {
      title: '作者',
      dataIndex: 'authors',
      key: 'authors',
      width: 180,
      render: (authors?: string[]) => (authors?.slice(0, 2).join(', ') ?? '—'),
    },
    {
      title: '年份',
      dataIndex: 'publication_year',
      key: 'publication_year',
      width: 80,
      render: (value?: number) => value ?? '—',
    },
    {
      title: '来源',
      dataIndex: 'source_platform',
      key: 'source_platform',
      width: 120,
      render: (value?: string) => value ?? '—',
    },
    {
      title: '标签',
      dataIndex: 'tags',
      key: 'tags',
      width: 180,
      render: (tags?: string[]) => (
        <div className={styles.tags}>
          {(tags ?? []).slice(0, 3).map((tag) => (
            <Tag key={tag}>{tag}</Tag>
          ))}
        </div>
      ),
    },
  ], []);

  return (
    <div className={styles.tableWrapper}>
      <Table<LiteratureItem>
        rowKey="id"
        dataSource={items}
        columns={columns}
        size="small"
        loading={isLoading && items.length === 0}
        pagination={false}
        locale={{ emptyText: selectedProjectId ? '暂无文献' : '请选择文献库' }}
        bordered={false}
        scroll={{ y: 400 }}
        rowClassName={(record) => (record.id === selectedItemId ? styles.rowActive : '')}
        onRow={(record) => ({
          onClick: () => setSelectedItem(record.id),
          onDoubleClick: () => setSelectedItem(record.id),
        })}
      />
    </div>
  );
}
