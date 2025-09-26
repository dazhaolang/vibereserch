import React, { useState } from 'react';
import { Card, Select, Switch, Space, Tooltip, Typography, Slider, Checkbox } from 'antd';
import { RobotOutlined, InfoCircleOutlined } from '@ant-design/icons';

const { Text } = Typography;
const { Option } = Select;

interface AutoModeControlPanelProps {
  onConfigChange: (config: AutoModeConfig) => void;
  disabled?: boolean;
}

export interface AutoModeConfig {
  agent: 'claude' | 'codex' | 'gemini';
  collectFirst: boolean;
  enableAiFiltering: boolean;
  enablePdfProcessing: boolean;
  enableStructuredExtraction: boolean;
  batchSize: number;
  maxConcurrentDownloads: number;
  collectionMaxCount: number;
  sources: string[];
  processingMethod: 'standard' | 'fast' | 'premium';
}

const AVAILABLE_SOURCES = [
  { value: 'semantic_scholar', label: 'Semantic Scholar' },
];

export const AutoModeControlPanel: React.FC<AutoModeControlPanelProps> = ({
  onConfigChange,
  disabled = false
}) => {
  const [config, setConfig] = useState<AutoModeConfig>({
    agent: 'claude',
    collectFirst: false,
    enableAiFiltering: true,
    enablePdfProcessing: true,
    enableStructuredExtraction: true,
    batchSize: 10,
    maxConcurrentDownloads: 5,
    collectionMaxCount: 100,
    sources: ['semantic_scholar'],
    processingMethod: 'standard'
  });

  const updateConfig = (updates: Partial<AutoModeConfig>) => {
    const newConfig = { ...config, ...updates };
    setConfig(newConfig);
    onConfigChange(newConfig);
  };

  return (
    <Card
      title={
        <Space>
          <RobotOutlined />
          <span>全自动模式配置</span>
        </Space>
      }
      size="small"
      className="auto-mode-control-panel"
    >
      <Space direction="vertical" className="w-full" size="middle">
        {/* 调度智能体选择 */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Text strong>调度智能体</Text>
            <Tooltip title="选择负责任务编排的AI智能体">
              <InfoCircleOutlined style={{ color: '#666' }} />
            </Tooltip>
          </div>
          <Select
            value={config.agent}
            onChange={(value) => updateConfig({ agent: value })}
            disabled={disabled}
            className="w-full"
          >
            <Option value="claude">Claude Code</Option>
            <Option value="codex">CodeX</Option>
            <Option value="gemini">Gemini CLI</Option>
          </Select>
        </div>

        {/* 执行策略 */}
        <div>
          <Text strong className="block mb-2">执行策略</Text>
          <Space direction="vertical" className="w-full">
            <div className="flex items-center justify-between">
              <span>先采集文献再处理</span>
              <Switch
                checked={config.collectFirst}
                onChange={(checked) => updateConfig({ collectFirst: checked })}
                disabled={disabled}
              />
            </div>
            <div className="flex items-center justify-between">
              <span>启用AI智能筛选</span>
              <Switch
                checked={config.enableAiFiltering}
                onChange={(checked) => updateConfig({ enableAiFiltering: checked })}
                disabled={disabled}
              />
            </div>
            <div className="flex items-center justify-between">
              <span>启用PDF处理</span>
              <Switch
                checked={config.enablePdfProcessing}
                onChange={(checked) => updateConfig({ enablePdfProcessing: checked })}
                disabled={disabled}
              />
            </div>
            <div className="flex items-center justify-between">
              <span>启用结构化提取</span>
              <Switch
                checked={config.enableStructuredExtraction}
                onChange={(checked) => updateConfig({ enableStructuredExtraction: checked })}
                disabled={disabled}
              />
            </div>
          </Space>
        </div>

        {/* 性能参数 */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Text strong>性能参数</Text>
            <Tooltip title="控制并发度和批次大小以优化处理速度">
              <InfoCircleOutlined style={{ color: '#666' }} />
            </Tooltip>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Text className="block mb-1">批次大小: {config.batchSize}</Text>
              <Slider
                min={5}
                max={50}
                value={config.batchSize}
                onChange={(value) => updateConfig({ batchSize: value })}
                disabled={disabled}
                marks={{
                  5: '5',
                  10: '10',
                  20: '20',
                  50: '50'
                }}
              />
            </div>

            <div>
              <Text className="block mb-1">并发下载: {config.maxConcurrentDownloads}</Text>
              <Slider
                min={1}
                max={10}
                value={config.maxConcurrentDownloads}
                onChange={(value) => updateConfig({ maxConcurrentDownloads: value })}
                disabled={disabled}
                marks={{
                  1: '1',
                  3: '3',
                  5: '5',
                  10: '10'
                }}
              />
            </div>
          </div>
        </div>

        {/* 文献源配置 */}
        <div>
          <Text strong className="block mb-2">文献来源</Text>
          <Checkbox.Group
            options={AVAILABLE_SOURCES}
            value={config.sources}
            onChange={(values) => updateConfig({ sources: values.map((value) => String(value)) })}
            disabled={disabled}
            className="w-full"
          />
        </div>

        {/* 采集限制 */}
        {config.collectFirst && (
          <div>
            <Text className="block mb-1">最大采集数量: {config.collectionMaxCount}</Text>
            <Slider
              min={10}
              max={500}
              value={config.collectionMaxCount}
              onChange={(value) => updateConfig({ collectionMaxCount: value })}
              disabled={disabled}
              marks={{
                10: '10',
                50: '50',
                100: '100',
                200: '200',
                500: '500'
              }}
            />
          </div>
        )}

        {/* 处理质量 */}
        <div>
          <Text strong className="block mb-2">处理质量</Text>
          <Select
            value={config.processingMethod}
            onChange={(value) => updateConfig({ processingMethod: value })}
            disabled={disabled}
            className="w-full"
          >
            <Option value="fast">快速处理（速度优先）</Option>
            <Option value="standard">标准处理（平衡质量与速度）</Option>
            <Option value="premium">高质量处理（质量优先）</Option>
          </Select>
        </div>
      </Space>
    </Card>
  );
};
