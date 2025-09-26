import { useEffect, useState, useMemo } from 'react';
import { motion } from 'framer-motion';
import { Alert } from 'antd';
import styles from './conversation-clarification.module.css';
import { useConversationStore } from '@/stores/conversation.store';
import type { ProjectSummary } from '@/services/api/project';
import type { ClarificationCard } from '@/services/api/interaction';

interface Props {
  projects: ProjectSummary[];
  selectedProjectId: number | null;
  onProjectChange: (id: number | null) => void;
}

const findOption = (card: ClarificationCard | null, optionId: string) =>
  card?.options.find((option) => option.option_id === optionId);

export function ConversationClarification({ projects, selectedProjectId, onProjectChange }: Props) {
  const {
    clarificationCard,
    clarificationQuestion,
    launchClarification,
    selectClarificationOption,
    clearClarification,
  } = useConversationStore((state) => ({
    clarificationCard: state.clarificationCard,
    clarificationQuestion: state.clarificationQuestion,
    launchClarification: state.launchClarification,
    selectClarificationOption: state.selectClarificationOption,
    clearClarification: state.clearClarification,
  }));

  const [question, setQuestion] = useState('');
  const [countdown, setCountdown] = useState<number | null>(null);

  useEffect(() => {
    if (!selectedProjectId && projects.length > 0) {
      onProjectChange(projects[0].id);
    }
  }, [projects, selectedProjectId, onProjectChange]);

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    if (clarificationCard?.timeout_seconds) {
      setCountdown(clarificationCard.timeout_seconds);
      timer = setInterval(() => {
        setCountdown((prev) => {
          if (prev === null) return null;
          if (prev <= 1) {
            timer && clearInterval(timer);
            const recommended = clarificationCard.recommended_option_id;
            if (recommended) {
              void selectClarificationOption(recommended);
            }
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    } else {
      setCountdown(null);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [clarificationCard, selectClarificationOption]);

  const recommended = useMemo(() =>
    clarificationCard?.recommended_option_id
      ? findOption(clarificationCard, clarificationCard.recommended_option_id)
      : null,
  [clarificationCard]);

  const handleLaunch = async () => {
    if (!question.trim()) return;
    await launchClarification(question.trim());
    setQuestion('');
  };

  return (
    <section className={styles.wrapper}>
      <div className={styles.form}>
        <label htmlFor="project">文献库</label>
        <select
          id="project"
          value={selectedProjectId ?? ''}
          onChange={(event) => {
            const value = event.target.value;
            onProjectChange(value ? Number(value) : null);
          }}
        >
          <option value="">请选择文献库</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
        <label htmlFor="clarification-question">澄清问题</label>
        <textarea
          id="clarification-question"
          placeholder="输入希望澄清的研究问题或任务目标"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          rows={3}
        />
        <motion.button
          type="button"
          whileHover={{ scale: 1.03 }}
          whileTap={{ scale: 0.97 }}
          onClick={() => void handleLaunch()}
          disabled={!selectedProjectId}
        >
          发起澄清
        </motion.button>
      </div>

      {clarificationCard ? (
        <motion.div
          key={clarificationCard.session_id}
          className={styles.card}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <header>
            <h3>{clarificationCard.question}</h3>
            <span>{countdown !== null ? `${countdown}s` : ''}</span>
          </header>
          <div className={styles.options}>
            {clarificationCard.options.map((option) => (
              <motion.button
                key={option.option_id}
                whileHover={{ scale: 1.02 }}
                className={styles.option}
                onClick={() => void selectClarificationOption(option.option_id)}
              >
                <strong>{option.title}</strong>
                <p>{option.description}</p>
                <footer>
                  <span>{option.estimated_time}</span>
                  {option.is_recommended && <span className={styles.recommend}>推荐</span>}
                </footer>
              </motion.button>
            ))}
          </div>
          {recommended ? (
            <div className={styles.alert}>
              <Alert
                type="info"
                showIcon
                message={`推荐选项：${recommended.title}`}
                description={recommended.description}
              />
            </div>
          ) : null}
          <footer className={styles.cardFooter}>
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              className={styles.dismiss}
              onClick={() => clearClarification()}
            >
              跳过澄清
            </motion.button>
          </footer>
        </motion.div>
      ) : clarificationQuestion ? (
        <div className={styles.awaiting}>已提交澄清请求，等待系统响应…</div>
      ) : null}
    </section>
  );
}
