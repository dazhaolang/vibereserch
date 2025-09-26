import React, { useMemo } from 'react';
import { Tooltip, Space, Progress, Divider } from 'antd';
import {
  DatabaseOutlined,
  ExperimentOutlined,
  RobotOutlined,
  InfoCircleOutlined,
  DollarOutlined,
  ClockCircleOutlined,
} from '@ant-design/icons';
import { motion } from 'framer-motion';
import type { ResearchMode } from '@/types';

interface ModeSelectorProps {
  value: ResearchMode;
  onChange: (mode: ResearchMode) => void;
  disabled?: boolean;
  showCostEstimate?: boolean;
}

interface ModeOption {
  value: ResearchMode;
  label: string;
  icon: React.ReactNode;
  description: string;
  color: string;
  costEstimate: {
    tokens: number;
    time: number; // minutes
    complexity: 'low' | 'medium' | 'high';
  };
}

const MODE_OPTIONS: ModeOption[] = [
  {
    value: 'rag',
    label: 'RAG模式',
    icon: <DatabaseOutlined />,
    description: '从现有知识库中快速检索相关内容，适合已有文献的问题查询',
    color: 'text-green-600',
    costEstimate: {
      tokens: 2000,
      time: 2,
      complexity: 'low',
    },
  },
  {
    value: 'deep',
    label: '深度研究',
    icon: <ExperimentOutlined />,
    description: '针对特定问题生成专属研究经验，适合深入探究科研难题',
    color: 'text-purple-600',
    costEstimate: {
      tokens: 15000,
      time: 8,
      complexity: 'medium',
    },
  },
  {
    value: 'auto',
    label: '全自动',
    icon: <RobotOutlined />,
    description: 'AI智能编排完整研究流程，从搜索到分析全程自动化',
    color: 'text-blue-600',
    costEstimate: {
      tokens: 50000,
      time: 25,
      complexity: 'high',
    },
  },
];

export const ModeSelector: React.FC<ModeSelectorProps> = ({
  value,
  onChange,
  disabled = false,
  showCostEstimate = true,
}) => {
  // 计算当前选择模式的费用估算
  const selectedOption = useMemo(() =>
    MODE_OPTIONS.find(option => option.value === value),
    [value]
  );

  const getCostColor = (complexity: string) => {
    switch (complexity) {
      case 'low': return 'text-green-600';
      case 'medium': return 'text-yellow-600';
      case 'high': return 'text-red-600';
      default: return 'text-gray-600';
    }
  };

  const formatTokens = (tokens: number) => {
    if (tokens >= 1000) {
      return `${(tokens / 1000).toFixed(1)}K`;
    }
    return tokens.toString();
  };
  return (
    <div className="mode-selector">
      <Space direction="vertical" className="w-full">
        <div className="flex items-center gap-2 mb-2">
          <span className="text-sm font-medium text-gray-700">研究模式</span>
          <Tooltip
            title={
              <div className="p-2">
                <div className="mb-2 font-semibold">三种研究模式说明：</div>
                <ul className="space-y-1 text-xs">
                  <li>• RAG模式：快速检索，适合日常查询</li>
                  <li>• 深度研究：生成经验，适合复杂问题</li>
                  <li>• 全自动：端到端流程，适合系统性研究</li>
                </ul>
              </div>
            }
          >
            <InfoCircleOutlined className="text-gray-400 cursor-help" />
          </Tooltip>
        </div>

        <div className="grid grid-cols-3 gap-3">
          {MODE_OPTIONS.map((option) => {
            const isSelected = value === option.value;

            return (
              <motion.div
                key={option.value}
                whileHover={{ scale: disabled ? 1 : 1.02 }}
                whileTap={{ scale: disabled ? 1 : 0.98 }}
              >
                <div
                  className={`
                    relative cursor-pointer rounded-lg border-2 p-4
                    transition-all duration-200
                    ${
                      isSelected
                        ? 'border-blue-500 bg-blue-50 shadow-lg'
                        : 'border-gray-200 hover:border-gray-300 hover:shadow-md'
                    }
                    ${disabled ? 'opacity-50 cursor-not-allowed' : ''}
                  `}
                  onClick={() => !disabled && onChange(option.value)}
                >
                  {/* 选中标记 */}
                  {isSelected && (
                    <motion.div
                      initial={{ scale: 0 }}
                      animate={{ scale: 1 }}
                      className="absolute -top-2 -right-2 bg-blue-500 text-white rounded-full w-6 h-6 flex items-center justify-center"
                    >
                      ✓
                    </motion.div>
                  )}

                  {/* 图标 */}
                  <div className={`text-2xl mb-2 ${isSelected ? 'text-blue-600' : option.color}`}>
                    {option.icon}
                  </div>

                  {/* 标题 */}
                  <div className={`font-semibold mb-1 ${isSelected ? 'text-blue-700' : 'text-gray-800'}`}>
                    {option.label}
                  </div>

                  {/* 描述 */}
                  <div className="text-xs text-gray-600 leading-relaxed">
                    {option.description}
                  </div>

                  {/* 性能指标 */}
                  <div className="mt-3 pt-3 border-t border-gray-100">
                    <div className="flex justify-between text-xs">
                      <span className="text-gray-500">速度</span>
                      <div className="flex gap-1">
                        {option.value === 'rag' && (
                          <>
                            <div className="w-1 h-3 bg-green-500 rounded-full" />
                            <div className="w-1 h-3 bg-green-500 rounded-full" />
                            <div className="w-1 h-3 bg-green-500 rounded-full" />
                          </>
                        )}
                        {option.value === 'deep' && (
                          <>
                            <div className="w-1 h-3 bg-yellow-500 rounded-full" />
                            <div className="w-1 h-3 bg-yellow-500 rounded-full" />
                            <div className="w-1 h-3 bg-gray-300 rounded-full" />
                          </>
                        )}
                        {option.value === 'auto' && (
                          <>
                            <div className="w-1 h-3 bg-orange-500 rounded-full" />
                            <div className="w-1 h-3 bg-gray-300 rounded-full" />
                            <div className="w-1 h-3 bg-gray-300 rounded-full" />
                          </>
                        )}
                      </div>
                    </div>
                    <div className="flex justify-between text-xs mt-1">
                      <span className="text-gray-500">深度</span>
                      <div className="flex gap-1">
                        {option.value === 'rag' && (
                          <>
                            <div className="w-1 h-3 bg-blue-500 rounded-full" />
                            <div className="w-1 h-3 bg-gray-300 rounded-full" />
                            <div className="w-1 h-3 bg-gray-300 rounded-full" />
                          </>
                        )}
                        {option.value === 'deep' && (
                          <>
                            <div className="w-1 h-3 bg-blue-500 rounded-full" />
                            <div className="w-1 h-3 bg-blue-500 rounded-full" />
                            <div className="w-1 h-3 bg-blue-500 rounded-full" />
                          </>
                        )}
                        {option.value === 'auto' && (
                          <>
                            <div className="w-1 h-3 bg-blue-500 rounded-full" />
                            <div className="w-1 h-3 bg-blue-500 rounded-full" />
                            <div className="w-1 h-3 bg-gray-300 rounded-full" />
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                </div>
              </motion.div>
            );
          })}
        </div>

        {/* 模式说明 */}
        <motion.div
          key={value}
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-4 p-3 bg-gray-50 rounded-lg"
        >
          <div className="text-sm">
            <span className="font-medium text-gray-700">当前选择：</span>
            <span className="ml-2 text-blue-600 font-semibold">
              {MODE_OPTIONS.find((o) => o.value === value)?.label}
            </span>
          </div>
          <div className="text-xs text-gray-600 mt-1">
            {MODE_OPTIONS.find((o) => o.value === value)?.description}
          </div>
        </motion.div>

        {/* 费用预估条 */}
        {showCostEstimate && selectedOption && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="mt-4 p-4 bg-blue-50 rounded-lg border border-blue-200"
          >
            <div className="flex items-center gap-2 mb-3">
              <DollarOutlined className="text-blue-600" />
              <span className="text-sm font-medium text-blue-700">费用预估</span>
              <Tooltip title="基于平均计算资源消耗的预估，实际消耗可能因具体任务而异">
                <InfoCircleOutlined className="text-blue-400 cursor-help" />
              </Tooltip>
            </div>

            <div className="grid grid-cols-3 gap-4 mb-3">
              <div className="text-center">
                <div className="text-lg font-semibold text-gray-700">
                  {formatTokens(selectedOption.costEstimate.tokens)}
                </div>
                <div className="text-xs text-gray-500">Token 消耗</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-semibold text-gray-700 flex items-center justify-center gap-1">
                  <ClockCircleOutlined className="text-sm" />
                  {selectedOption.costEstimate.time}分钟
                </div>
                <div className="text-xs text-gray-500">预计时间</div>
              </div>
              <div className="text-center">
                <div className={`text-lg font-semibold ${getCostColor(selectedOption.costEstimate.complexity)}`}>
                  {selectedOption.costEstimate.complexity === 'low' ? '低' :
                   selectedOption.costEstimate.complexity === 'medium' ? '中' : '高'}
                </div>
                <div className="text-xs text-gray-500">复杂度</div>
              </div>
            </div>

            <Divider className="my-3" />

            <div className="space-y-2">
              <div className="flex justify-between items-center text-xs">
                <span className="text-gray-600">资源使用预估</span>
                <span className={getCostColor(selectedOption.costEstimate.complexity)}>
                  {selectedOption.costEstimate.complexity === 'low' ? '25%' :
                   selectedOption.costEstimate.complexity === 'medium' ? '65%' : '90%'}
                </span>
              </div>
              <Progress
                percent={
                  selectedOption.costEstimate.complexity === 'low' ? 25 :
                  selectedOption.costEstimate.complexity === 'medium' ? 65 : 90
                }
                strokeColor={
                  selectedOption.costEstimate.complexity === 'low' ? '#52c41a' :
                  selectedOption.costEstimate.complexity === 'medium' ? '#faad14' : '#f5222d'
                }
                size="small"
                showInfo={false}
              />
            </div>

            <div className="mt-3 text-xs text-blue-600 bg-blue-100 p-2 rounded">
              💡 提示：选择适合的模式可以优化性能和成本
            </div>
          </motion.div>
        )}
      </Space>
    </div>
  );
};
