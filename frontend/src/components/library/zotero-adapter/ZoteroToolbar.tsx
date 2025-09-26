import { useMemo, useState } from 'react';
import { Input, Button, Space, message, Switch, Tooltip, Dropdown, Modal } from 'antd';
import type { MenuProps } from 'antd';
import {
  StarFilled,
  StarOutlined,
  ReloadOutlined,
  CloseOutlined,
  SearchOutlined,
  TagsOutlined,
  InboxOutlined,
  FolderOpenOutlined,
  DeleteOutlined,
  DownloadOutlined,
  DownOutlined,
} from '@ant-design/icons';
import { useLibraryStore } from '@/stores/library.store';
import { literatureAPI } from '@/services/api/literature';
import styles from './zotero-toolbar.module.css';

const { Search } = Input;

export function ZoteroToolbar() {
  const {
    selectedRowIds,
    searchQuery,
    setSearchQuery,
    loadItems,
    setRowSelection,
    filterStarred,
    setFilterStarred,
  } = useLibraryStore((state) => ({
    selectedRowIds: state.selectedRowIds,
    searchQuery: state.searchQuery,
    setSearchQuery: state.setSearchQuery,
    loadItems: state.loadItems,
    setRowSelection: state.setRowSelection,
    filterStarred: state.filterStarred,
    setFilterStarred: state.setFilterStarred,
  }));

  const [isStarring, setIsStarring] = useState(false);
  const [pendingAction, setPendingAction] = useState<string | null>(null);
  const [tagModalState, setTagModalState] = useState<{ visible: boolean; mode: 'add' | 'remove' | 'replace' }>({
    visible: false,
    mode: 'add',
  });
  const [tagInput, setTagInput] = useState('');

  const selectionCount = selectedRowIds.length;
  const selectionEmpty = selectionCount === 0;

  const handleSearch = (value: string) => {
    setSearchQuery(value);
    void loadItems(true);
  };

  const handleStar = async (starred: boolean) => {
    if (selectedRowIds.length === 0) {
      void message.info('请选择至少一篇文献');
      return;
    }
    setIsStarring(true);
    try {
      await literatureAPI.batchStar(selectedRowIds, starred);
      void message.success(`${starred ? '已收藏' : '已取消收藏'} ${selectedRowIds.length} 篇文献`);
      setRowSelection([]);
      await loadItems(true);
    } catch (error) {
      console.error(error);
      void message.error('批量更新收藏状态失败');
    } finally {
      setIsStarring(false);
    }
  };

  const executeBatchAction = async (
    actionKey: string,
    runner: () => Promise<void>,
    successMessage: string,
    failureMessage: string,
  ) => {
    setPendingAction(actionKey);
    try {
      await runner();
      void message.success(successMessage);
      setRowSelection([]);
      await loadItems(true);
    } catch (error) {
      console.error(error);
      void message.error(failureMessage);
    } finally {
      setPendingAction(null);
    }
  };

  const handleArchive = (archived: boolean) => {
    void executeBatchAction(
      archived ? 'archive' : 'unarchive',
      async () => {
        await literatureAPI.batchArchive(selectedRowIds, archived);
      },
      archived ? `已归档 ${selectionCount} 篇文献` : `已取消归档 ${selectionCount} 篇文献`,
      '批量归档操作失败',
    );
  };

  const handleExport = () => {
    void executeBatchAction(
      'export',
      async () => {
        const result = await literatureAPI.exportLiterature(selectedRowIds, {
          format: 'csv',
          fields: ['title', 'authors', 'journal', 'publication_year', 'doi'],
          includeAbstract: true,
          includeKeywords: true,
        });
        if (result.downloadUrl) {
          window.open(result.downloadUrl, '_blank', 'noopener');
        } else {
          throw new Error('缺少下载链接');
        }
      },
      `已生成导出文件（${selectionCount} 篇）`,
      '导出文献失败',
    );
  };

  const confirmDelete = () => {
    Modal.confirm({
      title: '确认删除所选文献？',
      content: `将永久删除 ${selectionCount} 篇文献，该操作不可恢复。`,
      okText: '确认删除',
      okType: 'danger',
      cancelText: '取消',
      onOk: () =>
        executeBatchAction(
          'delete',
          async () => {
            await literatureAPI.batchDelete(selectedRowIds);
          },
          `已删除 ${selectionCount} 篇文献`,
          '删除文献失败',
        ),
    });
  };

  const openTagModal = (mode: 'add' | 'remove' | 'replace') => {
    setTagModalState({ visible: true, mode });
    setTagInput('');
  };

  const closeTagModal = () => {
    setTagModalState({ visible: false, mode: 'add' });
    setTagInput('');
  };

  const handleSubmitTags = async () => {
    const tags = tagInput
      .split(',')
      .map((tag) => tag.trim())
      .filter((tag) => tag.length > 0);

    if (tags.length === 0) {
      void message.warning('请输入至少一个标签');
      return;
    }

    await executeBatchAction(
      `tags:${tagModalState.mode}`,
      async () => {
        await literatureAPI.batchSetTags(selectedRowIds, tagModalState.mode, tags);
      },
      `标签操作已完成（${selectionCount} 篇）`,
      '批量更新标签失败',
    );
    closeTagModal();
  };

  const batchMenuItems = useMemo<MenuProps['items']>(() => [
    {
      key: 'archive',
      icon: <InboxOutlined />,
      label: '批量归档',
    },
    {
      key: 'unarchive',
      icon: <FolderOpenOutlined />,
      label: '取消归档',
    },
    { type: 'divider' },
    {
      key: 'tags:add',
      icon: <TagsOutlined />,
      label: '添加标签',
    },
    {
      key: 'tags:remove',
      icon: <TagsOutlined />,
      label: '移除标签',
    },
    {
      key: 'tags:replace',
      icon: <TagsOutlined />,
      label: '替换标签',
    },
    { type: 'divider' },
    {
      key: 'export',
      icon: <DownloadOutlined />,
      label: '导出（CSV）',
    },
    {
      key: 'delete',
      icon: <DeleteOutlined />,
      danger: true,
      label: '批量删除',
    },
  ], []);

  const handleBatchMenuClick: MenuProps['onClick'] = ({ key }) => {
    if (selectionEmpty) {
      void message.info('请选择至少一篇文献');
      return;
    }

    switch (key) {
      case 'archive':
        handleArchive(true);
        break;
      case 'unarchive':
        handleArchive(false);
        break;
      case 'export':
        handleExport();
        break;
      case 'delete':
        confirmDelete();
        break;
      case 'tags:add':
        openTagModal('add');
        break;
      case 'tags:remove':
        openTagModal('remove');
        break;
      case 'tags:replace':
        openTagModal('replace');
        break;
      default:
        break;
    }
  };

  return (
    <div className={styles.toolbar}>
      <Search
        placeholder="搜索标题、作者、关键词"
        value={searchQuery}
        allowClear
        enterButton={<SearchOutlined />}
        onSearch={handleSearch}
        onChange={(event) => setSearchQuery(event.target.value)}
        style={{ maxWidth: 320 }}
      />
      <Space size={12}>
        <Tooltip title="仅显示已收藏文献">
          <Space>
            <Switch
              checked={filterStarred}
              onChange={(checked) => setFilterStarred(checked)}
              size="small"
            />
            <span className={styles.switchLabel}>仅收藏</span>
          </Space>
        </Tooltip>
        <Button
          icon={<StarFilled />}
          disabled={selectionEmpty}
          loading={isStarring}
          onClick={() => void handleStar(true)}
          type="primary"
        >
          收藏
        </Button>
        <Button
          icon={<StarOutlined />}
          disabled={selectionEmpty}
          loading={isStarring}
          onClick={() => void handleStar(false)}
        >
          取消收藏
        </Button>
        <Dropdown
          menu={{ items: batchMenuItems, onClick: handleBatchMenuClick }}
          disabled={selectionEmpty}
        >
          <Button icon={<TagsOutlined />} loading={Boolean(pendingAction)}>
            批量操作 <DownOutlined />
          </Button>
        </Dropdown>
        <Button
          icon={<CloseOutlined />}
          disabled={selectionEmpty}
          onClick={() => setRowSelection([])}
        >
          清空选择
        </Button>
        {selectionCount > 0 ? (
          <span className={styles.selectionInfo}>已选 {selectionCount} 篇</span>
        ) : null}
        <Button
          icon={<ReloadOutlined />}
          onClick={() => void loadItems(true)}
        >
          刷新
        </Button>
      </Space>
      <Modal
        open={tagModalState.visible}
        title={{ add: '批量添加标签', remove: '批量移除标签', replace: '批量替换标签' }[tagModalState.mode]}
        okText="确认"
        cancelText="取消"
        onCancel={closeTagModal}
        onOk={() => void handleSubmitTags()}
        confirmLoading={pendingAction?.startsWith('tags:')}
      >
        <p>使用逗号分隔多个标签，例如：AI, 临床试验, 综述</p>
        <Input.TextArea
          autoSize={{ minRows: 3, maxRows: 6 }}
          value={tagInput}
          onChange={(event) => setTagInput(event.target.value)}
          placeholder="输入标签"
        />
      </Modal>
    </div>
  );
}
