import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { triggerResearch } from '@/services/api/research';
import { ResearchResultPanel } from '@/components/research/ResearchResultPanel';
import { Empty, Spin } from 'antd';
import styles from './deep-panel.module.css';
import { motion } from 'framer-motion';
import type { ResearchResult } from '@/types';
import { normalizeResearchResult } from '@/utils/research';

interface Props {
  sessionId: string | null;
  projectId: number | null;
}

export function DeepPanel({ sessionId, projectId }: Props) {
  const [question, setQuestion] = useState('');
  const [method, setMethod] = useState('premium_mineru');

  const mutation = useMutation<ResearchResult, Error>({
    mutationFn: async () => {
      if (!projectId) {
        throw new Error('未选择项目，无法启动深度研究');
      }

      const { payload } = await triggerResearch({
        project_id: projectId,
        query: question,
        mode: 'deep',
        processing_method: method,
      });

      return normalizeResearchResult(payload, {
        base: {
          id: `deep-${Date.now()}`,
          project_id: projectId,
          mode: 'deep',
          question,
        },
        timestamp: new Date().toISOString(),
        fallbackAnswer: '深度研究任务完成',
        fallbackAnalysis: '经验生成已完成',
        defaultConfidence: 0.8,
        metadata: {
          processing_method: method,
          session_id: sessionId ?? undefined,
        },
      });
    },
  });

  const disabled = !projectId || !question.trim();

  return (
    <section className={styles.panel}>
      <header>
        <h2>深度研究流程</h2>
        <span>Session: {sessionId ?? '未启动'}</span>
      </header>
      <div className={styles.form}>
        <label>研究问题</label>
        <textarea
          rows={3}
          placeholder="描述需要深入分析的问题"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
        />
        <label>处理方式</label>
        <select value={method} onChange={(event) => setMethod(event.target.value)}>
          <option value="fast_basic">快速基础</option>
          <option value="standard">标准结构化</option>
          <option value="premium_mineru">MinerU 高质量</option>
        </select>
        <motion.button
          whileHover={disabled ? undefined : { scale: 1.02 }}
          whileTap={disabled ? undefined : { scale: 0.97 }}
          disabled={disabled || mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? '提交中…' : '启动经验生成'}
        </motion.button>
      </div>
      <div className={styles.output}>
        <h3>任务响应</h3>
        {mutation.isPending ? (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <Spin size="large" />
            <div style={{ marginTop: '16px' }}>已提交深度任务，等待经验生成…</div>
          </div>
        ) : mutation.data ? (
          <ResearchResultPanel result={mutation.data} />
        ) : (
          <Empty description="暂无结果，请启动经验生成任务" />
        )}
      </div>
    </section>
  );
}
