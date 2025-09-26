import { useNavigate } from 'react-router-dom';
import { motion } from 'framer-motion';
import styles from './quick-actions.module.css';

const actions = [
  { label: '快速 RAG', description: '立即对选定项目发起 RAG 查询', to: '/research?mode=rag' },
  { label: '深度流程', description: '安排结构化经验生成与问答', to: '/research?mode=deep' },
  { label: '全自动', description: '启动智能流水线并调度 Agent', to: '/research?mode=auto' }
];

export function QuickActions() {
  const navigate = useNavigate();

  return (
    <div className={styles.group}>
      {actions.map((action) => (
        <motion.button
          key={action.label}
          className={`${styles.button} btn-touch click-feedback`}
          whileHover={{ scale: 1.04 }}
          whileTap={{ scale: 0.98 }}
          onClick={() => navigate(action.to)}
        >
          <span className={styles.label}>{action.label}</span>
          <span className={styles.desc}>{action.description}</span>
          <motion.span
            className={styles.spark}
            layoutId="cta-highlight"
            transition={{ type: 'spring', stiffness: 520, damping: 36 }}
          />
        </motion.button>
      ))}
    </div>
  );
}
