import { motion } from 'framer-motion';
import styles from './insight-list.module.css';

interface InsightItem {
  id: string;
  title: string;
  summary: string;
  created_at: string;
}

interface Props {
  insights: InsightItem[];
  loading?: boolean;
}

export function InsightList({ insights, loading }: Props) {
  return (
    <section className={styles.panel}>
      <header className={styles.header}>
        <h2>最新研究洞察</h2>
        <span>{insights.length} 条</span>
      </header>
      <div className={styles.list}>
        {loading && <div className={styles.placeholder}>正在加载洞察...</div>}
        {!loading && insights.length === 0 && <div className={styles.placeholder}>暂无数据，快去生成新的经验书吧。</div>}
        {insights.map((item, index) => (
          <motion.article
            key={item.id}
            className={styles.item}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.08 }}
          >
            <div className={styles.meta}>
              <span>{new Date(item.created_at).toLocaleString()}</span>
            </div>
            <h3>{item.title}</h3>
            <p>{item.summary}</p>
          </motion.article>
        ))}
      </div>
    </section>
  );
}
