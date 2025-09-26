import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { triggerResearch } from '@/services/api/research';
import { ResearchResultPanel } from '@/components/research/ResearchResultPanel';
import { Empty, Spin } from 'antd';
import styles from './rag-panel.module.css';
import { motion } from 'framer-motion';
import type { ResearchResult } from '@/types';
import { normalizeResearchResult } from '@/utils/research';

interface Props {
  sessionId: string | null;
  projectId: number | null;
}

export function RagPanel({ sessionId, projectId }: Props) {
  const [question, setQuestion] = useState('');
  const mutation = useMutation<ResearchResult, Error>({
    mutationFn: async () => {
      if (!projectId) {
        throw new Error('未选择项目，无法启动 RAG 查询');
      }

      const { payload } = await triggerResearch({
        project_id: projectId,
        query: question,
        mode: 'rag',
        max_literature_count: 12,
      });

      return normalizeResearchResult(payload, {
        base: {
          id: `rag-${Date.now()}`,
          project_id: projectId,
          mode: 'rag',
          question,
        },
        timestamp: new Date().toISOString(),
        fallbackAnswer: 'RAG查询完成',
        fallbackAnalysis: '基于知识库的检索完成',
        defaultConfidence: 0.75,
        metadata: {
          session_id: sessionId ?? undefined,
        },
      });
    },
  });

  const disabled = !projectId || !question.trim();

  return (
    <section className={styles.panel}>
      <header>
        <h2>RAG 问答</h2>
        <span>Session: {sessionId ?? '未启动'}</span>
      </header>
      <div className={styles.controls}>
        <textarea
          rows={3}
          placeholder="输入问题，使用清洁化文献与主经验回答"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
        />
        <motion.button
          whileHover={disabled ? undefined : { scale: 1.02 }}
          whileTap={disabled ? undefined : { scale: 0.97 }}
          disabled={disabled || mutation.isPending}
          onClick={() => mutation.mutate()}
        >
          {mutation.isPending ? '处理中…' : '提交问题'}
        </motion.button>
      </div>
      <article className={styles.answer}>
        <h3>回答结果</h3>
        {mutation.isPending ? (
          <div style={{ textAlign: 'center', padding: '40px' }}>
            <Spin size="large" />
            <div style={{ marginTop: '16px' }}>生成中...</div>
          </div>
        ) : mutation.data ? (
          <ResearchResultPanel result={mutation.data} />
        ) : (
          <Empty description="暂无结果，请提交问题获取回答" />
        )}
      </article>
    </section>
  );
}
