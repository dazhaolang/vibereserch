import { useMemo } from 'react';
import { Empty, Typography, Tag, Divider } from 'antd';
import { useLibraryStore } from '@/stores/library.store';
import styles from './library-shell-inspector.module.css';

const { Title, Text, Paragraph } = Typography;

export function LibraryInspectorPane() {
  const { items, selectedItemId } = useLibraryStore((state) => ({
    items: state.items,
    selectedItemId: state.selectedItemId,
  }));
  const selected = useMemo(() => items.find((item) => item.id === selectedItemId) ?? null, [items, selectedItemId]);

  if (!selected) {
    return (
      <div className={styles.empty}>
        <Empty description="选择文献以查看详细信息" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <Title level={4}>{selected.title}</Title>
        {selected.authors?.length ? (
          <Text type="secondary">{selected.authors.join(', ')}</Text>
        ) : null}
      </header>
      <Divider dashed />
      <section className={styles.section}>
        <Title level={5}>关键信息</Title>
        <ul className={styles.metaList}>
          <li>
            <span>年份</span>
            <span>{selected.publication_year ?? '—'}</span>
          </li>
          <li>
            <span>DOI</span>
            <span>{selected.doi ?? '—'}</span>
          </li>
          <li>
            <span>来源</span>
            <span>{selected.source_platform ?? '—'}</span>
          </li>
        </ul>
      </section>
      {selected.abstract ? (
        <section className={styles.section}>
          <Title level={5}>摘要</Title>
          <Paragraph>{selected.abstract}</Paragraph>
        </section>
      ) : null}
      {(selected.tags?.length ?? 0) > 0 ? (
        <section className={styles.section}>
          <Title level={5}>标签</Title>
          <div className={styles.tags}>
            {selected.tags?.map((tag) => (
              <Tag key={tag}>{tag}</Tag>
            ))}
          </div>
        </section>
      ) : null}
    </div>
  );
}
