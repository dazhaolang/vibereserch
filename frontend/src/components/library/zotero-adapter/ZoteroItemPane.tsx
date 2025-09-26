/* eslint-disable @typescript-eslint/no-unsafe-member-access */
/* eslint-disable @typescript-eslint/no-unsafe-assignment */
import { useZoteroAssets } from './ZoteroAssets';
import { useLibraryStore } from '@/stores/library.store';
import { Empty, Typography, Tag, Spin, Alert, Divider } from 'antd';
import styles from './zotero-item-pane.module.css';
import { ZoteroPdfPreview } from './ZoteroPdfPreview';
import { ZoteroTaskLinkage } from './ZoteroTaskLinkage';

const { Title, Text, Paragraph } = Typography;

export function ZoteroItemPane() {
  useZoteroAssets({ injectScripts: false });
  const {
    selectedItemDetail,
    citations,
    isDetailLoading,
    detailError,
  } = useLibraryStore((state) => ({
    selectedItemDetail: state.selectedItemDetail,
    citations: state.citations,
    isDetailLoading: state.isDetailLoading,
    detailError: state.detailError,
  }));

  if (isDetailLoading) {
    return (
      <div className={styles.loading}>
        <Spin tip="加载文献详情…" />
      </div>
    );
  }

  if (detailError) {
    return (
      <Alert type="error" showIcon message="加载文献详情失败" description={detailError} />
    );
  }

  if (!selectedItemDetail) {
    return (
      <div className={styles.empty}>
        <Empty description="选择文献以查看详细信息" image={Empty.PRESENTED_IMAGE_SIMPLE} />
      </div>
    );
  }

  return (
    <div className={styles.panel}>
      <header className={styles.header}>
        <Title level={4}>{selectedItemDetail.title}</Title>
        {selectedItemDetail.authors?.length ? (
          <Text type="secondary">{selectedItemDetail.authors.join(', ')}</Text>
        ) : null}
      </header>

      <section className={styles.metaSection}>
        <div>
          <Text type="secondary">年份</Text>
          <span>{selectedItemDetail.publication_year ?? '—'}</span>
        </div>
        <div>
          <Text type="secondary">期刊</Text>
          <span>{selectedItemDetail.journal ?? '—'}</span>
        </div>
        <div>
          <Text type="secondary">DOI</Text>
          <span>{selectedItemDetail.doi ?? '—'}</span>
        </div>
        <div>
          <Text type="secondary">来源</Text>
          <span>{selectedItemDetail.source_platform ?? '—'}</span>
        </div>
      </section>

      {selectedItemDetail.abstract ? (
        <section className={styles.section}>
          <Title level={5}>摘要</Title>
          <Paragraph className={styles.abstract}>{selectedItemDetail.abstract}</Paragraph>
        </section>
      ) : null}

      {(selectedItemDetail.tags?.length ?? 0) > 0 ? (
        <section className={styles.section}>
          <Title level={5}>标签</Title>
          <div className={styles.tags}>
            {selectedItemDetail.tags?.map((tag) => (
              <Tag key={tag}>{tag}</Tag>
            ))}
          </div>
        </section>
      ) : null}

      {citations ? (
        <section className={styles.section}>
          <Title level={5}>引用概览</Title>
          <div className={styles.citationStats}>
            <span>引用：{citations.citation_count}</span>
            <span>参考文献：{citations.reference_count}</span>
          </div>
          <div className={styles.citationList}>
            {(citations.citations ?? []).map((item, index) => (
              <div key={`${item.doi ?? index}`} className={styles.citationItem}>
                <strong>{item.title ?? '未命名文献'}</strong>
                <Text type="secondary">
                  {(item.authors ?? []).slice(0, 3).join(', ')} · {item.year ?? '—'}
                </Text>
              </div>
            ))}
          </div>
          <Divider dashed />
          <Title level={5}>参考文献</Title>
          <div className={styles.citationList}>
            {(citations.references ?? []).map((item, index) => (
              <div key={`ref-${item.doi ?? index}`} className={styles.citationItem}>
                <strong>{item.title ?? '未命名文献'}</strong>
                <Text type="secondary">
                  {(item.authors ?? []).slice(0, 3).join(', ')} · {item.year ?? '—'}
                </Text>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      <section className={styles.section}>
        <Title level={5}>相关任务</Title>
        <ZoteroTaskLinkage literatureId={selectedItemDetail.id} />
      </section>

      <section className={styles.section}>
        <Title level={5}>PDF 预览</Title>
        <ZoteroPdfPreview />
      </section>
    </div>
  );
}
