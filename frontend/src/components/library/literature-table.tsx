import styles from './literature-table.module.css';
import type { LiteratureItem } from '@/services/api/literature';
import { motion } from 'framer-motion';

interface Props {
  items: LiteratureItem[];
  loading?: boolean;
}

export function LiteratureTable({ items, loading }: Props) {
  return (
    <section className={styles.container}>
      <header>
        <h2>文献列表</h2>
        <span>{items.length} 条</span>
      </header>
      <div className={styles.tableWrapper}>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>标题</th>
              <th>作者</th>
              <th>年份</th>
              <th>质量评分</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className={styles.placeholder}>
                  正在加载文献列表...
                </td>
              </tr>
            )}
            {!loading && items.length === 0 && (
              <tr>
                <td colSpan={5} className={styles.placeholder}>
                  暂无文献，请先导入或运行搜索建库任务。
                </td>
              </tr>
            )}
            {items.map((item) => (
              <motion.tr
                key={item.id}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
              >
                <td>{item.title}</td>
                <td>{item.authors?.join(', ')}</td>
                <td>{item.publication_year ?? '-'}</td>
                <td>{item.quality_score?.toFixed?.(1) ?? '-'}</td>
                <td>{item.status ?? (item.is_parsed ? '已解析' : '待处理')}</td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
