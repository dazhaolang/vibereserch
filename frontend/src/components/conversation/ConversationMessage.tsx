import { memo, useMemo } from 'react';
import type { ConversationMessage } from '@/stores/conversation.store';
import styles from './conversation-message.module.css';

const roleIconMap: Record<ConversationMessage['role'], string> = {
  user: '🧑',
  assistant: '🤖',
  system: '✨',
};

const modeLabelMap: Record<ConversationMessage['mode'], string> = {
  rag: 'RAG',
  deep: '深度',
  auto: '自动',
};

const formatTime = (iso: string): string => {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return '';
  }
  return date.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  });
};

interface Props {
  message: ConversationMessage;
}

export const ConversationMessageBubble = memo(({ message }: Props) => {
  const isUser = message.role === 'user';
  const roleIcon = roleIconMap[message.role];
  const timestamp = useMemo(() => formatTime(message.createdAt), [message.createdAt]);

  const bubbleClassName = [
    styles.message,
    isUser ? styles.user : styles.assistant,
    message.isError ? styles.error : undefined,
  ].filter(Boolean).join(' ');

  return (
    <div className={styles.messageRow}>
      <div className={[styles.meta, isUser ? styles.metaRight : undefined].filter(Boolean).join(' ')}>
        <span className={styles.roleIcon}>{roleIcon}</span>
        <span className={styles.metaTag}>{modeLabelMap[message.mode]}</span>
        {timestamp ? <span className={styles.timestamp}>{timestamp}</span> : null}
      </div>
      <div className={bubbleClassName}>
        <div className={styles.content}>{message.content}</div>
        {message.citations && message.citations.length > 0 ? (
          <div className={styles.citations}>
            {message.citations.map((source) => {
              const labelParts: string[] = [];
              if (source.title) {
                labelParts.push(source.title);
              }
              if (source.year) {
                labelParts.push(String(source.year));
              }
              if (source.doi) {
                labelParts.push(source.doi);
              }
              const label = labelParts.join(' · ') || `来源 ${String(source.id)}`;
              return (
                <span key={String(source.id)} className={styles.citation}>
                  {label}
                </span>
              );
            })}
          </div>
        ) : null}
      </div>
    </div>
  );
});

ConversationMessageBubble.displayName = 'ConversationMessageBubble';
