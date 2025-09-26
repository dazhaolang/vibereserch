import { motion } from 'framer-motion';
import styles from './mode-switcher.module.css';

export type ResearchMode = 'rag' | 'deep' | 'auto';

const items: Array<{ mode: ResearchMode; title: string; description: string }> = [
  {
    mode: 'rag',
    title: 'RAG 模式',
    description: '使用已清洁化的文献与主经验即时回答问题'
  },
  {
    mode: 'deep',
    title: '深度研究',
    description: '拆解问题、生成结构化经验，再推送问答'
  },
  {
    mode: 'auto',
    title: '全自动',
    description: '交给 Agent 调度多任务流水线，实现端到端研究'
  }
];

interface Props {
  mode: ResearchMode;
  onModeChange: (mode: ResearchMode) => void;
}

export function ModeSwitcher({ mode, onModeChange }: Props) {
  return (
    <div className={styles.switcher}>
      {items.map((item) => (
        <button
          key={item.mode}
          className={styles.item}
          data-active={mode === item.mode}
          onClick={() => onModeChange(item.mode)}
        >
          {mode === item.mode && <motion.span layoutId="mode-active" className={styles.activeBg} />}
          <span className={styles.title}>{item.title}</span>
          <span className={styles.description}>{item.description}</span>
        </button>
      ))}
    </div>
  );
}
