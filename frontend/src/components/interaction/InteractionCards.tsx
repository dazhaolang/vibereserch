import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, Button, Progress, Space, Input, message, Tooltip } from 'antd';
import {
  CheckCircleOutlined,
  ClockCircleOutlined,
  BulbOutlined,
  EditOutlined,
} from '@ant-design/icons';
import { motion, AnimatePresence } from 'framer-motion';
import { useResearchStore } from '@/stores/research.store';
import type { ClarificationCard, ClarificationOption } from '@/types';

// 导入动画JSON（需要添加到assets）
// import thinkingAnimation from '@/assets/animations/thinking.json';

interface InteractionCardsProps {
  sessionId: string;
  card: ClarificationCard;
}

export const InteractionCards: React.FC<InteractionCardsProps> = ({
  sessionId,
  card,
}) => {
  const [timeLeft, setTimeLeft] = useState(card.timeout_seconds || 5);
  const [showCustomInput, setShowCustomInput] = useState(false);
  const [customInput, setCustomInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  const timeoutRef = useRef<ReturnType<typeof setTimeout>>();
  const countdownRef = useRef<ReturnType<typeof setInterval>>();

  const { selectOption, submitCustomInput, handleTimeout, pushClarificationEvent } = useResearchStore();

  const logClarificationEvent = useCallback((event: {
    type: 'select-option' | 'custom-input' | 'auto-select' | 'timeout';
    option?: ClarificationOption;
    input?: string;
  }) => {
    pushClarificationEvent({
      id: `${sessionId}-${Date.now()}-${Math.random().toString(16).slice(2, 6)}`,
      time: new Date().toISOString(),
      ...event,
    });
  }, [pushClarificationEvent, sessionId]);

  const handleTimeoutSelection = useCallback(async () => {
    if (card.recommended_option_id) {
      const recommendedOption = card.options.find(
        (opt) => opt.option_id === card.recommended_option_id
      );

      if (recommendedOption) {
        void message.info(`已自动选择推荐选项：${recommendedOption.title}`, 3);
        await handleTimeout(sessionId);
        logClarificationEvent({ type: 'auto-select', option: recommendedOption });
        return;
      }
    }
    await handleTimeout(sessionId);
    logClarificationEvent({ type: 'timeout' });
  }, [card.options, card.recommended_option_id, handleTimeout, logClarificationEvent, sessionId]);

  const handleOptionSelect = useCallback(async (option: ClarificationOption) => {
    // 清除定时器
    if (timeoutRef.current) clearTimeout(timeoutRef.current);
    if (countdownRef.current) clearInterval(countdownRef.current);

    setIsProcessing(true);
    try {
      await selectOption(sessionId, option.option_id);
      void message.success(`已选择：${option.title}`);
      logClarificationEvent({ type: 'select-option', option });
    } catch (error) {
      void message.error('选择失败，请重试');
    } finally {
      setIsProcessing(false);
    }
  }, [logClarificationEvent, selectOption, sessionId]);

  const handleCustomSubmit = useCallback(async () => {
    if (!customInput.trim()) {
      void message.warning('请输入内容');
      return;
    }

    setIsProcessing(true);
    try {
      await submitCustomInput(sessionId, customInput);
      void message.success('自定义输入已提交');
      logClarificationEvent({ type: 'custom-input', input: customInput });
      setCustomInput('');
      setShowCustomInput(false);
    } catch (error) {
      void message.error('提交失败，请重试');
    } finally {
      setIsProcessing(false);
    }
  }, [customInput, logClarificationEvent, sessionId, submitCustomInput]);

  // 倒计时逻辑
  useEffect(() => {
    if (card.timeout_seconds > 0) {
      setTimeLeft(card.timeout_seconds);

      countdownRef.current = setInterval(() => {
        setTimeLeft((prev) => {
          if (prev <= 1) {
            void handleTimeoutSelection();
            return 0;
          }
          return prev - 1;
        });
      }, 1000);

      timeoutRef.current = setTimeout(() => {
        void handleTimeoutSelection();
      }, card.timeout_seconds * 1000);
    }

    return () => {
      if (countdownRef.current) clearInterval(countdownRef.current);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [card, handleTimeoutSelection]);

  const progressPercent =
    card.timeout_seconds > 0
      ? ((card.timeout_seconds - timeLeft) / card.timeout_seconds) * 100
      : 0;

  return (
    <Card
      title={
        <div className="flex justify-between items-center">
          <div className="flex items-center gap-2">
            <BulbOutlined className="text-blue-500 text-lg" />
            <span className="font-semibold">{card.question}</span>
          </div>
          {card.timeout_seconds > 0 && timeLeft > 0 && (
            <div className="flex items-center gap-3">
              <ClockCircleOutlined className="text-gray-500" />
              <span className="text-sm text-gray-600">{timeLeft}秒后自动选择</span>
              <Progress
                type="circle"
                percent={progressPercent}
                width={32}
                format={() => `${timeLeft}`}
                strokeColor={{
                  '0%': '#108ee9',
                  '100%': '#ff4d4f',
                }}
              />
            </div>
          )}
        </div>
      }
      className="shadow-xl border-2 border-blue-100"
      bodyStyle={{ padding: '24px' }}
    >
      <Space direction="vertical" className="w-full" size="middle">
        {/* 选项列表 */}
        <div className="space-y-3">
          {card.options.map((option) => {
            const isRecommended = option.option_id === card.recommended_option_id;

            return (
              <motion.div
                key={option.option_id}
                whileHover={{ scale: 1.02 }}
                whileTap={{ scale: 0.98 }}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.3 }}
              >
                <Tooltip
                  title={isRecommended ? 'AI推荐选项' : ''}
                  placement="topLeft"
                >
                  <Button
                    block
                    size="large"
                    type={isRecommended ? 'primary' : 'default'}
                    onClick={() => handleOptionSelect(option)}
                    disabled={isProcessing}
                    className={`
                      h-auto py-4 px-6 text-left relative
                      ${isRecommended
                        ? 'bg-gradient-to-r from-blue-500 to-blue-600 border-0 shadow-lg'
                        : 'hover:border-blue-400 hover:shadow-md transition-all'
                      }
                    `}
                  >
                    <div className="flex items-start gap-3">
                      {isRecommended && (
                        <CheckCircleOutlined className="text-white text-lg mt-1" />
                      )}
                      <div className="flex-1">
                        <div className={`
                          font-medium text-base
                          ${isRecommended ? 'text-white' : 'text-gray-800'}
                        `}>
                          {option.title}
                        </div>
                        {option.description && (
                          <div className={`
                            text-sm mt-1
                            ${isRecommended ? 'text-blue-100' : 'text-gray-500'}
                          `}>
                            {option.description}
                          </div>
                        )}
                        {option.implications && option.implications.length > 0 && (
                          <div className={`
                            text-xs mt-2 space-y-1
                            ${isRecommended ? 'text-blue-50' : 'text-gray-500'}
                          `}>
                            {option.implications.slice(0, 2).map((implication, index) => (
                              <div key={index} className="flex items-center gap-2">
                                <div className="w-1 h-1 rounded-full bg-blue-400" />
                                {implication}
                              </div>
                            ))}
                          </div>
                        )}
                        <div className="mt-3 flex flex-wrap items-center gap-4 text-xs text-gray-400">
                          {option.estimated_time && (
                            <div>预计耗时：{option.estimated_time}</div>
                          )}
                          {typeof option.confidence_score === 'number' && (
                            <div>置信度：{Math.round(option.confidence_score * 100)}%</div>
                          )}
                        </div>
                        {option.estimated_results && (
                          <div className={`
                            mt-3 p-2 rounded text-xs
                            ${isRecommended ? 'bg-blue-500/20 text-blue-50' : 'bg-gray-100 text-gray-600'}
                          `}>
                            预期结果：{option.estimated_results}
                          </div>
                        )}
                      </div>
                      {isRecommended && (
                        <div className="absolute top-2 right-2">
                          <span className="bg-yellow-400 text-gray-800 text-xs px-2 py-1 rounded-full">
                            推荐
                          </span>
                        </div>
                      )}
                    </div>
                  </Button>
                </Tooltip>
              </motion.div>
            );
          })}
        </div>

        {/* 自定义输入 */}
        {card.custom_input_allowed && (
          <AnimatePresence>
            {!showCustomInput ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
              >
                <Button
                  type="dashed"
                  block
                  size="large"
                  icon={<EditOutlined />}
                  onClick={() => setShowCustomInput(true)}
                  disabled={isProcessing}
                  className="h-12"
                >
                  其他选择（自定义输入）
                </Button>
              </motion.div>
            ) : (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                className="bg-gray-50 p-4 rounded-lg"
              >
                <Space direction="vertical" className="w-full">
                  <div className="text-sm text-gray-600 mb-2">
                    请输入您的想法：
                  </div>
                  <Input.TextArea
                    value={customInput}
                    onChange={(e) => setCustomInput(e.target.value)}
                    placeholder="请详细描述您的需求或选择..."
                    rows={4}
                    maxLength={500}
                    showCount
                    disabled={isProcessing}
                  />
                  <div className="flex gap-2 justify-end">
                    <Button
                      onClick={() => {
                        setShowCustomInput(false);
                        setCustomInput('');
                      }}
                      disabled={isProcessing}
                    >
                      取消
                    </Button>
                    <Button
                      type="primary"
                      onClick={handleCustomSubmit}
                      loading={isProcessing}
                    >
                      提交
                    </Button>
                  </div>
                </Space>
              </motion.div>
            )}
          </AnimatePresence>
        )}

        {/* 上下文信息 */}
        {card.context && (
          <div className="bg-blue-50 p-3 rounded-lg">
            <div className="text-xs text-gray-500">当前阶段</div>
            <div className="text-sm text-gray-700 mt-1">{card.stage}</div>
          </div>
        )}
      </Space>
    </Card>
  );
};
