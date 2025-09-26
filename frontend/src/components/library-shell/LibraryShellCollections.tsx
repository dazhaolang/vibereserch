import { Tree } from 'antd';
import type { DataNode } from 'antd/es/tree';
import type { LibraryCollection } from '@/stores/library.store';
import styles from './library-shell-collections.module.css';

interface Props {
  collections: LibraryCollection[];
  selectedId: string | null;
  onSelect: (collectionId: string | null) => void;
}

const toTreeData = (collections: LibraryCollection[]): DataNode[] =>
  collections.map((collection) => ({
    key: collection.id,
    title: `${collection.name} (${collection.itemCount})`,
    children: collection.children ? toTreeData(collection.children) : undefined,
  }));

export function LibraryCollectionsPanel({ collections, selectedId, onSelect }: Props) {
  const treeData = toTreeData(collections);

  return (
    <div className={styles.panel}>
      {treeData.length === 0 ? (
        <div className={styles.empty}>暂无集合</div>
      ) : (
        <Tree
          selectedKeys={selectedId ? [selectedId] : []}
          onSelect={(keys) => {
            onSelect(keys[0]?.toString() ?? null);
          }}
          treeData={treeData}
          showLine
          blockNode
        />
      )}
    </div>
  );
}
