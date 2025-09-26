import { motion } from 'framer-motion';
import type { ConversationMode } from '@/stores/research-shell.store';
import styles from './mode-cards.module.css';

interface ModeCardsProps {
  activeMode: ConversationMode;
  onChange: (mode: ConversationMode) => void;
  disabledModes?: ConversationMode[];
}

const cards: Array<{ mode: ConversationMode; title: string; description: string }> = [
  {
    mode: 'rag',
    title: 'RAG 模式',
    description: '基于当前文献库实时检索并回答问题',
  },
  {
    mode: 'deep',
    title: '深度经验增强',
    description: '拆解问题并注入经过强化的经验与方案',
  },
  {
    mode: 'auto',
    title: '全自动流水线',
    description: '交由智能体自动搜索建库与汇总结论',
  },
];

export function ModeCards({ activeMode, onChange, disabledModes }: ModeCardsProps) {
  return (
    <div className={styles.wrapper}>
      {cards.map((card) => {
        const isActive = activeMode === card.mode;
        const isDisabled = disabledModes?.includes(card.mode) ?? false;
        return (
          <button
            key={card.mode}
            type="button"
            className={styles.card}
            data-active={isActive}
            data-disabled={isDisabled}
            onClick={() => {
              if (!isDisabled) {
                onChange(card.mode);
              }
            }}
            disabled={isDisabled}
          >
            {isActive ? <motion.span layoutId="mode-cards-active" className={styles.activeBg} /> : null}
            <span className={styles.title}>{card.title}</span>
            <span className={styles.description}>{card.description}</span>
            {isDisabled ? <span className={styles.badge}>不可用</span> : null}
          </button>
        );
      })}
    </div>
  );
}
