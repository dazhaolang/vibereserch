import { motion } from 'framer-motion';
import styles from './overview-metric.module.css';

interface Props {
  label: string;
  value: number;
  loading?: boolean;
  glow?: string;
}

export function OverviewMetric({ label, value, glow, loading }: Props) {
  return (
    <motion.div className={styles.card} whileHover={{ y: loading ? 0 : -6 }} transition={{ type: 'spring', stiffness: 320 }}>
      <div className={styles.glow} style={{ background: glow }} />
      <span className={styles.label}>{label}</span>
      <strong className={styles.value}>
        {loading ? <span className={styles.skeleton} /> : new Intl.NumberFormat('zh-CN').format(value)}
      </strong>
    </motion.div>
  );
}
