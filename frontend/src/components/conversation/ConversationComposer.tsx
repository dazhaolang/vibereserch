import { useState } from 'react';
import { Tooltip } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import type { ConversationMode, LibraryStatus } from '@/stores/research-shell.store';
import styles from './conversation-composer.module.css';

interface Props {
  mode: ConversationMode;
  libraryStatus: LibraryStatus;
  isSending: boolean;
  disabled?: boolean;
  onSend: (text: string) => Promise<void> | void;
}

const placeholderMap: Record<ConversationMode, string> = {
  rag: '请输入问题，系统将基于当前文献库检索并回答…',
  deep: '描述需要深入分析的研究问题，系统会生成结构化经验…',
  auto: '输入研究目标，智能体将自动搜索、建库并汇总结果…',
};

export function ConversationComposer({
  mode,
  libraryStatus,
  isSending,
  disabled,
  onSend,
}: Props) {
  const [value, setValue] = useState('');

  const isDisabled = disabled || isSending;
  const trimmed = value.trim();
  const canSend = trimmed.length > 0 && !isDisabled;
  const placeholder = placeholderMap[mode];
  const requiresLibrary = mode !== 'auto';

  const libraryWarning = requiresLibrary && libraryStatus !== 'ready'
    ? '当前文献库未就绪，无法发送查询'
    : undefined;

  const handleSubmit = async () => {
    if (!canSend) {
      return;
    }
    await onSend(trimmed);
    setValue('');
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      void handleSubmit();
    }
  };

  return (
    <div className={styles.composer}>
      <div className={styles.editor}>
        <textarea
          className={styles.textarea}
          value={value}
          placeholder={placeholder}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isDisabled}
        />
        <Tooltip title={canSend ? '发送' : undefined}>
          <button
            type="button"
            className={styles.sendButton}
            onClick={() => void handleSubmit()}
            disabled={!canSend}
          >
            {isSending ? '发送中…' : <SendOutlined />}
          </button>
        </Tooltip>
      </div>
      <div className={styles.actions}>
        <span className={styles.hint}>回车发送，Shift + 回车换行</span>
        {libraryWarning ? <span className={styles.warning}>{libraryWarning}</span> : null}
      </div>
    </div>
  );
}
