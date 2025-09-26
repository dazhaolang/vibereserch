import { motion } from 'framer-motion';
import styles from './auto-mode-cta.module.css';

export function AutoModeCTA() {
  return (
    <motion.section
      className={styles.cta}
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      transition={{ duration: 0.4 }}
    >
      <div className={styles.copy}>
        <h2>全自动研究流水线</h2>
        <p>
          将文献采集、清洁化、经验生成与问答协同交给 AI Agent 调度，Skywork 式交互随时调整策略。
        </p>
      </div>
      <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.98 }}>立即启动</motion.button>
    </motion.section>
  );
}
