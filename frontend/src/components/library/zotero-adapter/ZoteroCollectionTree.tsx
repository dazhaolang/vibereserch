import { useMemo } from 'react';
import type { DataNode } from 'antd/es/tree';
import { Tree } from 'antd';
import classNames from 'classnames';
import type { LibraryCollection } from '@/stores/library.store';
import styles from './zotero-collection-tree.module.css';
import { useZoteroAssets } from './ZoteroAssets';

interface Props {
  collections: LibraryCollection[];
  selectedId: string | null;
  onSelect: (collectionId: string | null) => void;
}

const buildTree = (collections: LibraryCollection[]): DataNode[] =>
  collections.map((collection) => ({
    key: collection.id,
    title: (
      <span className={styles.collectionLabel}>
        {collection.name}
        <span className={styles.count}>{collection.itemCount}</span>
      </span>
    ),
    children: collection.children ? buildTree(collection.children) : undefined,
  }));

export function ZoteroCollectionTree({ collections, selectedId, onSelect }: Props) {
  useZoteroAssets({ injectScripts: false });
  const treeData = useMemo(() => buildTree(collections), [collections]);

  return (
    <div className={classNames('zotero-collection-tree', styles.wrapper)}>
      <Tree
        selectable
        showLine
        blockNode
        treeData={treeData}
        selectedKeys={selectedId ? [selectedId] : []}
        onSelect={(keys) => {
          onSelect(keys[0] ? String(keys[0]) : null);
        }}
      />
    </div>
  );
}
