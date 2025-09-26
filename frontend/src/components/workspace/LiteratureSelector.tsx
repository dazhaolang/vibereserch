import React, { useState, useEffect, useCallback } from 'react';
import { Modal, Input, List, Checkbox, Button, Space, Tag, Pagination, Spin, Empty, message } from 'antd';
import { SearchOutlined, BookOutlined, CalendarOutlined, UserOutlined } from '@ant-design/icons';
import { literatureAPI, type LiteratureItem, type LiteratureListResponse } from '@/services/api/literature';

type Literature = Pick<
  LiteratureItem,
  'id' | 'title' | 'authors' | 'abstract' | 'doi' | 'journal' | 'tags'
> & {
  publication_date?: string;
  processing_status?: string;
};

interface LiteratureSelectorProps {
  visible: boolean;
  onCancel: () => void;
  onConfirm: (selectedIds: number[]) => void;
  projectId?: number;
  initialSelected?: number[];
  maxSelection?: number;
}

export const LiteratureSelector: React.FC<LiteratureSelectorProps> = ({
  visible,
  onCancel,
  onConfirm,
  projectId,
  initialSelected = [],
  maxSelection = 10
}) => {
  const [searchQuery, setSearchQuery] = useState('');
  const [literature, setLiterature] = useState<Literature[]>([]);
  const [selectedIds, setSelectedIds] = useState<number[]>(initialSelected);
  const [loading, setLoading] = useState(false);
  const [pagination, setPagination] = useState({
    current: 1,
    pageSize: 10,
    total: 0
  });

  const fetchLiterature = useCallback(
    async (query = '', page = 1): Promise<void> => {
      if (!projectId) {
        return;
      }

      setLoading(true);
      try {
        const response: LiteratureListResponse = await literatureAPI.getLiterature({
          project_id: projectId,
          query,
          page,
          size: pagination.pageSize,
        });

        const mapped: Literature[] = response.items.map((item) => ({
          id: item.id,
          title: item.title,
          authors: Array.isArray(item.authors) ? item.authors : [],
          abstract: item.abstract,
          doi: item.doi,
          journal: item.journal,
          tags: item.tags,
          publication_date: item.publication_year ? String(item.publication_year) : undefined,
          processing_status: item.status,
        }));

        setLiterature(mapped);
        setPagination((prev) => ({
          ...prev,
          current: page,
          total: response.total,
        }));
      } catch (error) {
        console.error('Failed to fetch literature:', error);
        void message.error('获取文献列表失败');
      } finally {
        setLoading(false);
      }
    },
    [pagination.pageSize, projectId]
  );

  useEffect(() => {
    if (visible && projectId) {
      void fetchLiterature();
    }
  }, [visible, projectId, fetchLiterature]);

  useEffect(() => {
    setSelectedIds(initialSelected);
  }, [initialSelected]);

  const handleSearch = useCallback(() => {
    void fetchLiterature(searchQuery, 1);
  }, [fetchLiterature, searchQuery]);

  const handlePageChange = useCallback(
    (page: number) => {
      void fetchLiterature(searchQuery, page);
    },
    [fetchLiterature, searchQuery]
  );

  const handleSelect = (id: number, checked: boolean) => {
    if (checked) {
      if (selectedIds.length >= maxSelection) {
        void message.warning(`最多只能选择 ${maxSelection} 篇文献`);
        return;
      }
      setSelectedIds([...selectedIds, id]);
    } else {
      setSelectedIds(selectedIds.filter(selectedId => selectedId !== id));
    }
  };

  const handleSelectAll = () => {
    const currentPageIds = literature.map(item => item.id);
    const newSelected = [...new Set([...selectedIds, ...currentPageIds])];

    if (newSelected.length > maxSelection) {
      void message.warning(`最多只能选择 ${maxSelection} 篇文献`);
      return;
    }

    setSelectedIds(newSelected);
  };

  const handleClearAll = () => {
    setSelectedIds([]);
  };

  const renderLiteratureItem = (item: Literature) => {
    const isSelected = selectedIds.includes(item.id);
    return (
      <List.Item
        key={item.id}
      actions={[
        <Checkbox
          key="select"
          checked={isSelected}
          onChange={(e) => handleSelect(item.id, e.target.checked)}
        />
      ]}
    >
      <List.Item.Meta
        avatar={<BookOutlined style={{ fontSize: 24, color: '#1890ff' }} />}
        title={
          <div>
            <span style={{ fontWeight: 'bold' }}>{item.title}</span>
            {item.processing_status && (
              <Tag
                color={item.processing_status === 'completed' ? 'green' : 'orange'}
                style={{ marginLeft: 8 }}
              >
                {item.processing_status === 'completed' ? '已处理' : '处理中'}
              </Tag>
            )}
          </div>
        }
        description={
          <div>
            {item.authors.length > 0 && (
              <div style={{ marginBottom: 4 }}>
                <UserOutlined style={{ marginRight: 4 }} />
                {item.authors.slice(0, 3).join(', ')}
                {item.authors.length > 3 && ' 等'}
              </div>
            )}

            {item.publication_date && (
              <div style={{ marginBottom: 4 }}>
                <CalendarOutlined style={{ marginRight: 4 }} />
                {item.publication_date}
                {item.journal && ` • ${item.journal}`}
              </div>
            )}

            {item.abstract && (
              <div style={{
                marginTop: 8,
                color: '#666',
                fontSize: '12px',
                lineHeight: 1.4
              }}>
                {item.abstract.length > 200
                  ? `${item.abstract.slice(0, 200)}...`
                  : item.abstract
                }
              </div>
            )}

            {item.tags && item.tags.length > 0 && (
              <div style={{ marginTop: 8 }}>
                {item.tags.slice(0, 5).map((tag) => (
                  <Tag key={`${item.id}-${tag}`}>{tag}</Tag>
                ))}
              </div>
            )}
         </div>
       }
     />
    </List.Item>
    );
  };

  return (
    <Modal
      title={`选择上下文文献 (已选择 ${selectedIds.length}/${maxSelection})`}
      open={visible}
      onCancel={onCancel}
      onOk={() => onConfirm(selectedIds)}
      width={800}
      style={{ top: 20 }}
      bodyStyle={{ maxHeight: '70vh', overflow: 'auto' }}
      okText="确认选择"
      cancelText="取消"
    >
      {/* 搜索栏 */}
      <div style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="搜索文献标题、作者或关键词"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          onSearch={handleSearch}
          enterButton={<SearchOutlined />}
          size="large"
        />
      </div>

      {/* 操作栏 */}
      <div style={{ marginBottom: 16 }}>
        <Space>
          <Button size="small" onClick={handleSelectAll}>
            全选当前页
          </Button>
          <Button size="small" onClick={handleClearAll}>
            清空选择
          </Button>
          <span style={{ color: '#666' }}>
            当前页: {literature.length} 篇，总共: {pagination.total} 篇
          </span>
        </Space>
      </div>

      {/* 文献列表 */}
      <Spin spinning={loading}>
        {literature.length > 0 ? (
          <>
            <List
              dataSource={literature}
              renderItem={renderLiteratureItem}
              size="small"
            />

            {pagination.total > pagination.pageSize && (
              <div style={{ textAlign: 'center', marginTop: 16 }}>
                <Pagination
                  current={pagination.current}
                  pageSize={pagination.pageSize}
                  total={pagination.total}
                  onChange={handlePageChange}
                  showSizeChanger={false}
                  showQuickJumper
                  showTotal={(total, range) =>
                    `第 ${range[0]}-${range[1]} 条，共 ${total} 条`
                  }
                />
              </div>
            )}
          </>
        ) : loading ? null : (
          <Empty description="暂无文献数据" />
        )}
      </Spin>
    </Modal>
  );
};
