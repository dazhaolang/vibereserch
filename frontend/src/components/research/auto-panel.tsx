import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { triggerResearch } from '@/services/api/research';
import { ResearchResultPanel } from '@/components/research/ResearchResultPanel';
import { Empty, Spin } from 'antd';
import styles from './auto-panel.module.css';
import { motion } from 'framer-motion';
import type { ResearchResult } from '@/types';
import { normalizeResearchResult } from '@/utils/research';

interface Props {
  sessionId: string | null;
  projectId: number | null;
}

export function AutoPanel({ sessionId, projectId }: Props) {
  const [goal, setGoal] = useState('');
  const [keywords, setKeywords] = useState<string>('');
  const [agent, setAgent] = useState<'claude' | 'codex' | 'gemini'>('claude');

  const mutation = useMutation<ResearchResult, Error>({
    mutationFn: async () => {
      if (!projectId) {
        throw new Error('未选择项目，无法启动全自动研究');
      }

      const keywordList = keywords
        .split(',')
        .map((word) => word.trim())
        .filter(Boolean);

      const { payload } = await triggerResearch({
        project_id: projectId,
        query: goal,
        mode: 'auto',
        keywords: keywordList,
        auto_config: {
          enable_ai_filtering: true,
          enable_pdf_processing: true,
          enable_structured_extraction: true,
        },
        agent,
      });

      return normalizeResearchResult(payload, {
        base: {
          id: `auto-${Date.now()}`,
          project_id: projectId,
          mode: 'auto',
          question: goal,
        },
        timestamp: new Date().toISOString(),
        fallbackAnswer: '自动流水线执行完成',
        fallbackAnalysis: '智能体已完成任务编排和执行',
        defaultConfidence: 0.8,
        metadata: {
          agent,
          keywords: keywordList,
          session_id: sessionId ?? undefined,
        },
      });
    },
  });

  const disabled = !projectId || !goal.trim();

  return (
    <section className={styles.panel}>
      <header>
        <h2>全自动研究流水线</h2>
        <span>Session: {sessionId ?? '未启动'}</span>
      </header>
      <div className={styles.form}>
        <label>研究目标</label>
        <textarea
          rows={3}
          placeholder="描述希望自动探索的研究课题"
          value={goal}
          onChange={(event) => setGoal(event.target.value)}
        />
        <label>初始关键词（逗号分隔）</label>
        <input
          placeholder="例如：solid electrolyte, garnet, thin film"
          value={keywords}
          onChange={(event) => setKeywords(event.target.value)}
        />
        <label>调度核心</label>
        <select value={agent} onChange={(event) => setAgent(event.target.value as 'claude' | 'codex' | 'gemini')}>
          <option value="claude">Claude Code</option>
          <option value="codex">CodeX</option>
          <option value="gemini">Gemini CLI</option>
        </select>
        <motion.button
          whileHover={disabled ? undefined : { scale: 1.02 }}
          whileTap={disabled ? undefined : { scale: 0.97 }}
          disabled={disabled || mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? '执行中…' : '启动全自动流水线'}
        </motion.button>
      </div>
      <div className={styles.result}>
        <h3>流水线状态</h3>
        {mutation.isPending ? (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <Spin size="large" />
            <div style={{ marginTop: '16px' }}>Agent 正在生成任务编排方案…</div>
          </div>
        ) : mutation.data ? (
          <ResearchResultPanel result={mutation.data} />
        ) : (
          <Empty description="暂无结果，请启动全自动流水线" />
        )}
      </div>
    </section>
  );
}
