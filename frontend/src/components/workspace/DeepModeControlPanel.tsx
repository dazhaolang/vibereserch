import React, { useState } from 'react';
import { Card, Slider, Select, Switch, Space, Tooltip, Typography } from 'antd';
import { SettingOutlined, InfoCircleOutlined } from '@ant-design/icons';

const { Text } = Typography;
const { Option } = Select;

interface DeepModeControlPanelProps {
  onConfigChange: (config: DeepModeConfig) => void;
  disabled?: boolean;
}

export interface DeepModeConfig {
  maxIterations: number;
  batchSize: number;
  processingMethod: 'fast_basic' | 'standard' | 'premium_mineru';
  enableStructuredTemplate: boolean;
  templateType: string;
  convergenceThreshold: number;
  enableQualityFilter: boolean;
}

export const DeepModeControlPanel: React.FC<DeepModeControlPanelProps> = ({
  onConfigChange,
  disabled = false
}) => {
  const [config, setConfig] = useState<DeepModeConfig>({
    maxIterations: 3,
    batchSize: 10,
    processingMethod: 'standard',
    enableStructuredTemplate: true,
    templateType: 'research_paper',
    convergenceThreshold: 0.85,
    enableQualityFilter: true
  });

  const updateConfig = (updates: Partial<DeepModeConfig>) => {
    const newConfig = { ...config, ...updates };
    setConfig(newConfig);
    onConfigChange(newConfig);
  };

  return (
    <Card
      title={
        <Space>
          <SettingOutlined />
          <span>深度研究高级配置</span>
        </Space>
      }
      size="small"
      className="deep-mode-control-panel"
    >
      <Space direction="vertical" className="w-full" size="middle">
        {/* 迭代配置 */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Text strong>迭代参数</Text>
            <Tooltip title="控制经验生成的迭代轮次和批次大小">
              <InfoCircleOutlined style={{ color: '#666' }} />
            </Tooltip>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Text className="block mb-1">最大迭代轮次: {config.maxIterations}</Text>
              <Slider
                min={1}
                max={10}
                value={config.maxIterations}
                onChange={(value) => {
                  if (typeof value === 'number') {
                    updateConfig({ maxIterations: value });
                  }
                }}
                disabled={disabled}
                marks={{
                  1: '1',
                  3: '3',
                  5: '5',
                  10: '10'
                }}
              />
            </div>

            <div>
              <Text className="block mb-1">批次大小: {config.batchSize}</Text>
              <Slider
                min={5}
                max={50}
                value={config.batchSize}
                onChange={(value) => {
                  if (typeof value === 'number') {
                    updateConfig({ batchSize: value });
                  }
                }}
                disabled={disabled}
                marks={{
                  5: '5',
                  10: '10',
                  20: '20',
                  50: '50'
                }}
              />
            </div>
          </div>
        </div>

        {/* 处理方式 */}
        <div>
          <Text strong className="block mb-2">处理方式</Text>
          <Select
            value={config.processingMethod}
            onChange={(value) => updateConfig({ processingMethod: value })}
            disabled={disabled}
            className="w-full"
          >
            <Option value="fast_basic">快速基础处理</Option>
            <Option value="standard">标准结构化处理</Option>
            <Option value="premium_mineru">MinerU 高质量处理</Option>
          </Select>
        </div>

        {/* 结构化模板 */}
        <div>
          <div className="flex items-center justify-between mb-2">
            <Text strong>结构化模板</Text>
            <Switch
              checked={config.enableStructuredTemplate}
              onChange={(checked) => updateConfig({ enableStructuredTemplate: checked })}
              disabled={disabled}
            />
          </div>

          {config.enableStructuredTemplate && (
            <Select
              value={config.templateType}
              onChange={(value) => updateConfig({ templateType: value })}
              disabled={disabled}
              className="w-full"
            >
              <Option value="research_paper">学术论文模板</Option>
              <Option value="technical_report">技术报告模板</Option>
              <Option value="literature_review">文献综述模板</Option>
              <Option value="methodology">方法论模板</Option>
            </Select>
          )}
        </div>

        {/* 质量控制 */}
        <div>
          <div className="flex items-center gap-2 mb-2">
            <Text strong>质量控制</Text>
            <Tooltip title="设置收敛阈值和质量过滤器">
              <InfoCircleOutlined style={{ color: '#666' }} />
            </Tooltip>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <Text className="block mb-1">收敛阈值: {(config.convergenceThreshold * 100).toFixed(0)}%</Text>
              <Slider
                min={0.5}
                max={1.0}
                step={0.05}
                value={config.convergenceThreshold}
                onChange={(value) => {
                  if (typeof value === 'number') {
                    updateConfig({ convergenceThreshold: value });
                  }
                }}
                disabled={disabled}
              />
            </div>

            <div className="flex items-center">
              <Switch
                checked={config.enableQualityFilter}
                onChange={(checked) => updateConfig({ enableQualityFilter: checked })}
                disabled={disabled}
              />
              <Text className="ml-2">启用质量过滤</Text>
            </div>
          </div>
        </div>
      </Space>
    </Card>
  );
};
