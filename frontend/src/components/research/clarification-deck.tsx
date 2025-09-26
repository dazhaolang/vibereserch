import { useCallback, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import styles from './clarification-deck.module.css';
import { startInteraction, submitInteractionSelection, type ClarificationCard } from '@/services/api/interaction';
import type { ResearchMode } from './mode-switcher';
import type { ProjectSummary } from '@/services/api/project';

interface Props {
  projects: ProjectSummary[];
  mode: ResearchMode;
  selectedProjectId: number | null;
  onProjectChange: (id: number | null) => void;
  onSessionReady: (sessionId: string | null) => void;
}

export function ClarificationDeck({ projects, mode, selectedProjectId, onProjectChange, onSessionReady }: Props) {
  const [card, setCard] = useState<ClarificationCard | null>(null);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [question, setQuestion] = useState('');
  const [countdown, setCountdown] = useState<number | null>(null);

  useEffect(() => {
    setCard(null);
    setSessionId(null);
    onSessionReady(null);
  }, [mode, onSessionReady]);

  useEffect(() => {
    if (!selectedProjectId && projects.length > 0) {
      onProjectChange(projects[0].id);
    }
  }, [onProjectChange, projects, selectedProjectId]);

  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    if (card) {
      setCountdown(card.timeout_seconds);
      timer = setInterval(() => {
        setCountdown((current) => {
          if (current === null) return null;
          if (current <= 1) {
            timer && clearInterval(timer);
            if (sessionId && card.recommended_option_id) {
              submitInteractionSelection(sessionId, card.recommended_option_id).catch(console.error);
            }
            return 0;
          }
          return current - 1;
        });
      }, 1000);
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [card, sessionId]);

  const handleLaunch = useCallback(async () => {
    if (!question.trim() || !selectedProjectId) return;
    try {
      const response = await startInteraction({
        project_id: selectedProjectId,
        context_type: mode,
        user_input: question
      });
      setSessionId(response.session_id);
      onSessionReady(response.session_id);
      if (response.clarification_card) {
        setCard(response.clarification_card);
      } else {
        setCard(null);
      }
    } catch (error) {
      console.error('startInteraction failed', error);
    }
  }, [mode, onSessionReady, question, selectedProjectId]);

  const handleSelect = async (optionId: string) => {
    if (!sessionId) return;
    await submitInteractionSelection(sessionId, optionId);
    setCard(null);
  };

  return (
    <section className={styles.deck}>
      <div className={styles.form}>
        <label htmlFor="project">项目</label>
        <select
          id="project"
          value={selectedProjectId ?? ''}
          onChange={(event) => {
            const value = event.target.value;
            onProjectChange(value ? Number(value) : null);
          }}
        >
          <option value="">请选择项目</option>
          {projects.map((project) => (
            <option key={project.id} value={project.id}>
              {project.name}
            </option>
          ))}
        </select>
        <label htmlFor="question">研究问题</label>
        <textarea
          id="question"
          placeholder="请输入需要研究的问题或目标"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          rows={3}
        />
        <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} onClick={handleLaunch} disabled={!selectedProjectId}>
          发起互动澄清
        </motion.button>
      </div>
      {card && (
        <motion.div
          key={card.session_id}
          className={styles.card}
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <header>
            <h3>{card.question}</h3>
            <span>{countdown !== null ? `${countdown}s` : ''}</span>
          </header>
          <div className={styles.options}>
            {card.options.map((option) => (
              <motion.button
                key={option.option_id}
                whileHover={{ scale: 1.02 }}
                onClick={() => handleSelect(option.option_id)}
                className={styles.option}
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
        </motion.div>
      )}
      {!card && sessionId && (
        <div className={styles.directMessage}>系统已直接进入流程，无需澄清，可继续在下方执行研究。</div>
      )}
    </section>
  );
}
