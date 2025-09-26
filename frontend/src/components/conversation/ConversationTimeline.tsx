import { useEffect, useRef } from 'react';
import { Spin } from 'antd';
import type { ConversationMessage } from '@/stores/conversation.store';
import styles from './conversation-timeline.module.css';
import { ConversationMessageBubble } from './ConversationMessage';

interface Props {
  messages: ConversationMessage[];
  isLoading: boolean;
  emptyHint?: string;
}

export function ConversationTimeline({ messages, isLoading, emptyHint }: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const anchorRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!containerRef.current || !anchorRef.current) {
      return;
    }
    anchorRef.current.scrollIntoView({ behavior: 'smooth', block: 'end' });
  }, [messages.length, isLoading]);

  return (
    <div className={styles.timeline} ref={containerRef}>
      {messages.length === 0 && !isLoading ? (
        <div className={styles.emptyState}>{emptyHint ?? '开始提问，让助手基于文献库给出回答。'}</div>
      ) : null}

      {messages.map((message) => (
        <ConversationMessageBubble key={message.id} message={message} />
      ))}

      {isLoading ? (
        <div className={styles.loading}>
          <Spin size="small" />
          正在生成回答…
        </div>
      ) : null}

      <div ref={anchorRef} className={styles.scrollAnchor} />
    </div>
  );
}
