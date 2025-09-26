import { useEffect } from 'react';
import { Button, Empty, Spin, Typography } from 'antd';
import { useZoteroAssets } from '@/components/library/zotero-adapter/ZoteroAssets';
import { ZoteroCollectionTree } from '@/components/library/zotero-adapter/ZoteroCollectionTree';
import { ZoteroItemsTable } from '@/components/library/zotero-adapter/ZoteroItemsTable';
import { ZoteroItemPane } from '@/components/library/zotero-adapter/ZoteroItemPane';
import { ZoteroToolbar } from '@/components/library/zotero-adapter/ZoteroToolbar';
import { useLibraryStore } from '@/stores/library.store';
import styles from './library-shell.module.css';

const { Title, Text } = Typography;

export function LibraryShell() {
  const {
    collections,
    selectedCollectionId,
    setSelectedCollection,
    loadItems,
    hasMore,
    isLoading,
    items,
    selectedProjectId,
  } = useLibraryStore((state) => ({
    collections: state.collections,
    selectedCollectionId: state.selectedCollectionId,
    setSelectedCollection: state.setSelectedCollection,
    loadItems: state.loadItems,
    hasMore: state.hasMore,
    isLoading: state.isLoading,
    items: state.items,
    selectedProjectId: state.selectedProjectId,
  }));

  useEffect(() => {
    if (items.length === 0 && selectedProjectId) {
      void loadItems(true);
    }
  }, [items.length, selectedProjectId, selectedCollectionId, loadItems]);

  useZoteroAssets();

  return (
    <div className={styles.shell}>
      <aside className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <Title level={4} style={{ color: '#e2e8f0', margin: 0 }}>
            文献集合
          </Title>
          <Text type="secondary">按合集或标签浏览文献</Text>
        </div>
        <ZoteroCollectionTree
          collections={collections}
          selectedId={selectedCollectionId}
          onSelect={setSelectedCollection}
        />
      </aside>
      <section className={styles.itemsPanel}>
        <header className={styles.itemsHeader}>
          <div>
            <Title level={4} style={{ margin: 0, color: '#f8fafc' }}>
              文献列表
            </Title>
            <Text type="secondary">勾选文献进行批量操作，双击查看详情</Text>
          </div>
        </header>
        <ZoteroToolbar />
        <ZoteroItemsTable />
        <div className={styles.itemsFooter}>
          {isLoading ? (
            <Spin size="small" />
          ) : hasMore ? (
            <Button type="link" onClick={() => void loadItems(false)}>
              加载更多
            </Button>
          ) : (
            <Text type="secondary">已到达列表末尾</Text>
          )}
        </div>
      </section>
      <aside className={styles.inspectorPanel}>
        <ZoteroItemPane />
      </aside>
      {items.length === 0 && !isLoading ? (
        <div className={styles.emptyOverlay}>
          <Empty description="暂无文献，请尝试更换集合或上传" />
        </div>
      ) : null}
    </div>
  );
}
