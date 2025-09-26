import React, { useState } from 'react';
import { motion } from 'framer-motion';
import {
  Card,
  Typography,
  Row,
  Col,
  Slider,
  Switch,
  Button,
  Select,
  Input,
  Tree,
  Tag,
  Progress,
  Divider,
  Space,
  Alert,
  Tabs,
  message,
} from 'antd';
import {
  BrainCircuit,
  GitBranch,
  Settings,
  Play,
  Target,
  Database,
  Zap,
  Lightbulb,
  CheckCircle,
  Clock
} from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../../store/app-store';
import { useAppStore as useWorkspaceStore } from '@/stores/app.store';
import { researchAPI } from '@/services/api/research';
import { useResearchQuery } from '../../hooks/api-hooks';

const { Title, Text } = Typography;
const { TextArea } = Input;
const { Option } = Select;
const { TabPane } = Tabs;

interface SubQuestion {
  id: string;
  text: string;
  complexity: 'low' | 'medium' | 'high';
  relatedLiteratureCount: number;
  keywords: string[];
  priority: number;
}

interface IterationConfig {
  rounds: number;
  docsPerRound: number;
  focusTopics: string[];
  analysisDepth: 'surface' | 'moderate' | 'deep';
  enableCrossValidation: boolean;
  synthesisMethod: 'sequential' | 'parallel' | 'hierarchical';
}

const isPlainObject = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const QueryDecomposition: React.FC<{
  query: string;
  onQueryUpdate: (query: string) => void;
  subQuestions: SubQuestion[];
  onSubQuestionsUpdate: (questions: SubQuestion[]) => void;
  onIterationConfigUpdate: (config: Partial<IterationConfig>) => void;
  projectId?: number;
}> = ({ query, onQueryUpdate, subQuestions, onSubQuestionsUpdate, onIterationConfigUpdate, projectId }) => {
  const [isDecomposing, setIsDecomposing] = useState(false);
  const [overallComplexity, setOverallComplexity] = useState(0.6);

  const handleDecomposeQuery = async () => {
    if (!query.trim()) {
      return;
    }

    if (!projectId) {
      void message.warning('请先选择一个项目再进行问题拆解');
      return;
    }

    setIsDecomposing(true);
    try {
      const analysisResult = await researchAPI.analyzeQuery({
        query,
        project_id: projectId,
        context: {
          mode: 'deep',
          existing_keywords: [],
        },
      });

      // 转换API响应为组件需要的格式
      const subQuestionList: string[] = Array.isArray(analysisResult.sub_questions)
        ? analysisResult.sub_questions
        : [];
      const suggestedKeywords: string[] = Array.isArray(analysisResult.suggested_keywords)
        ? analysisResult.suggested_keywords
        : [];

      const subQuestions: SubQuestion[] = subQuestionList.map((question, index) => ({
        id: (index + 1).toString(),
        text: question,
        complexity: analysisResult.complexity_score > 0.7 ? 'high' :
                    analysisResult.complexity_score > 0.4 ? 'medium' : 'low',
        relatedLiteratureCount: Math.floor(Math.random() * 50) + 10, // TODO: 从实际搜索结果获取
        keywords: suggestedKeywords.slice(index * 2, (index + 1) * 2) || [],
        priority: index + 1
      }));

      onSubQuestionsUpdate(subQuestions);
      setOverallComplexity(analysisResult.complexity_score);

      // 如果有推荐的处理建议，更新配置
      const suggestions = analysisResult.processing_suggestions;
      if (isPlainObject(suggestions)) {
        const updates: Partial<IterationConfig> = {};
        const batchSize = suggestions['batch_size'];
        const maxIterations = suggestions['max_iterations'];
        if (typeof batchSize === 'number') {
          updates.docsPerRound = batchSize;
        }
        if (typeof maxIterations === 'number') {
          updates.rounds = maxIterations;
        }
        if (Object.keys(updates).length > 0) {
          onIterationConfigUpdate(updates);
        }
      }
    } catch (error) {
      console.error('Query decomposition failed:', error);
      void message.error((error as Error)?.message || '问题分析失败，请稍后重试');
    } finally {
      setIsDecomposing(false);
    }
  };

  const treeData = subQuestions.map(sq => ({
    title: (
      <div className="flex items-start justify-between w-full">
        <div className="flex-1">
          <Text className="text-white font-medium">{sq.text}</Text>
          <div className="flex items-center space-x-2 mt-2">
            <Tag color={sq.complexity === 'high' ? 'red' : sq.complexity === 'medium' ? 'orange' : 'green'}>
              {sq.complexity === 'high' ? '高复杂度' : sq.complexity === 'medium' ? '中等复杂度' : '低复杂度'}
            </Tag>
            <Tag color="blue">{sq.relatedLiteratureCount} 篇文献</Tag>
            <Tag color="purple">优先级 {sq.priority}</Tag>
          </div>
          <div className="flex flex-wrap gap-1 mt-2">
            {sq.keywords.map(keyword => (
              <Tag key={keyword} className="text-xs">
                {keyword}
              </Tag>
            ))}
          </div>
        </div>
      </div>
    ),
    key: sq.id,
    children: []
  }));

  return (
    <Card className="border-neutral-700 mb-6">
      <Title level={4} className="!text-white !mb-4">
        <GitBranch className="w-5 h-5 inline mr-2" />
        问题拆解分析
      </Title>

      <div className="mb-6">
        <Text className="text-neutral-300 block mb-2">主要研究问题：</Text>
        <TextArea
          value={query}
          onChange={(e) => onQueryUpdate(e.target.value)}
          placeholder="输入您的复杂研究问题..."
          rows={3}
          className="mb-4"
        />

        <div className="flex items-center justify-between">
          <Button
            type="primary"
            loading={isDecomposing}
            onClick={handleDecomposeQuery}
            icon={<Target className="w-4 h-4" />}
          >
            AI智能拆解
          </Button>

          <div className="flex items-center space-x-4">
            <Text className="text-neutral-400">整体复杂度：</Text>
            <div className="flex items-center space-x-2">
              <Progress
                type="circle"
                size={40}
                percent={Math.round(overallComplexity * 100)}
                strokeColor={overallComplexity > 0.7 ? '#ef4444' : overallComplexity > 0.4 ? '#f59e0b' : '#10b981'}
                trailColor="#374151"
              />
              <Text className="text-primary-400">
                {overallComplexity > 0.7 ? '高' : overallComplexity > 0.4 ? '中' : '低'}
              </Text>
            </div>
          </div>
        </div>
      </div>

      {subQuestions.length > 0 && (
        <div>
          <Divider className="border-neutral-600" />
          <Text className="text-neutral-300 block mb-4">拆解后的子问题：</Text>
          <Tree
            treeData={treeData}
            defaultExpandAll
            className="custom-tree"
            showLine={false}
          />
        </div>
      )}
    </Card>
  );
};

const IterationConfigPanel: React.FC<{
  config: IterationConfig;
  onConfigUpdate: (config: IterationConfig) => void;
  extractedTopics: string[];
}> = ({ config, onConfigUpdate, extractedTopics }) => {
  const handleConfigChange = <Key extends keyof IterationConfig>(key: Key, value: IterationConfig[Key]) => {
    onConfigUpdate({
      ...config,
      [key]: value
    });
  };

  return (
    <Card className="border-neutral-700">
      <Title level={4} className="!text-white !mb-4">
        <Settings className="w-5 h-5 inline mr-2" />
        迭代参数配置
      </Title>

      <div className="space-y-6">
        {/* Iteration Rounds */}
        <div>
          <Text className="text-neutral-300 block mb-2">迭代轮次：{config.rounds} 轮</Text>
          <Slider
            min={3}
            max={10}
            value={config.rounds}
            onChange={(value) => {
              if (typeof value === 'number') {
                handleConfigChange('rounds', value);
              }
            }}
            marks={{
              3: '3',
              5: '5',
              7: '7',
              10: '10'
            }}
          />
          <Text className="text-neutral-500 text-sm">
            更多轮次可获得更深入的知识合成，但会增加时间和成本
          </Text>
        </div>

        {/* Docs per Round */}
        <div>
          <Text className="text-neutral-300 block mb-2">每轮文献数：{config.docsPerRound} 篇</Text>
          <Slider
            min={3}
            max={15}
            value={config.docsPerRound}
            onChange={(value) => {
              if (typeof value === 'number') {
                handleConfigChange('docsPerRound', value);
              }
            }}
            marks={{
              3: '3',
              5: '5',
              10: '10',
              15: '15'
            }}
          />
          <Text className="text-neutral-500 text-sm">
            每轮处理更多文献可提高全面性，但会增加处理时间
          </Text>
        </div>

        {/* Analysis Depth */}
        <div>
          <Text className="text-neutral-300 block mb-2">分析深度：</Text>
          <Select
            value={config.analysisDepth}
            onChange={(value: IterationConfig['analysisDepth']) => handleConfigChange('analysisDepth', value)}
            className="w-full"
          >
            <Option value="surface">浅层分析 - 快速概览</Option>
            <Option value="moderate">中等深度 - 平衡效率与质量</Option>
            <Option value="deep">深度分析 - 全面深入</Option>
          </Select>
        </div>

        {/* Synthesis Method */}
        <div>
          <Text className="text-neutral-300 block mb-2">合成方法：</Text>
          <Select
            value={config.synthesisMethod}
            onChange={(value: IterationConfig['synthesisMethod']) => handleConfigChange('synthesisMethod', value)}
            className="w-full"
          >
            <Option value="sequential">顺序合成 - 逐步积累知识</Option>
            <Option value="parallel">并行合成 - 多角度同时分析</Option>
            <Option value="hierarchical">分层合成 - 层次化知识构建</Option>
          </Select>
        </div>

        {/* Focus Topics */}
        <div>
          <Text className="text-neutral-300 block mb-2">聚焦主题：</Text>
          <div className="flex flex-wrap gap-2">
            {extractedTopics.map(topic => (
              <Tag.CheckableTag
                key={topic}
                checked={config.focusTopics.includes(topic)}
                onChange={(checked) => {
                  const newTopics = checked
                    ? [...config.focusTopics, topic]
                    : config.focusTopics.filter(t => t !== topic);
                  handleConfigChange('focusTopics', newTopics);
                }}
                className="border-neutral-600"
              >
                {topic}
              </Tag.CheckableTag>
            ))}
          </div>
          <Text className="text-neutral-500 text-sm mt-2">
            选择要重点关注的主题，未选择的主题也会被分析但权重较低
          </Text>
        </div>

        {/* Advanced Options */}
        <div>
          <Divider className="border-neutral-600 my-4" />
          <Text className="text-neutral-300 block mb-3">高级选项：</Text>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <Text className="text-neutral-300">启用交叉验证</Text>
                <br />
                <Text className="text-neutral-500 text-sm">验证不同文献间的观点一致性</Text>
              </div>
              <Switch
                checked={config.enableCrossValidation}
                onChange={(checked) => handleConfigChange('enableCrossValidation', checked)}
              />
            </div>
          </div>
        </div>

        {/* Cost Estimation */}
        <div className="p-4 bg-neutral-800 rounded">
          <div className="flex items-center justify-between mb-2">
            <Text className="text-neutral-300">预估成本：</Text>
            <Text className="text-primary-400 font-bold">
              ${(config.rounds * config.docsPerRound * 0.15).toFixed(2)}
            </Text>
          </div>
          <div className="flex items-center justify-between mb-2">
            <Text className="text-neutral-400 text-sm">预估时间：</Text>
            <Text className="text-neutral-400 text-sm">
              {Math.round(config.rounds * config.docsPerRound * 0.5)} 分钟
            </Text>
          </div>
          <Progress
            percent={Math.min((config.rounds * config.docsPerRound) / 50 * 100, 100)}
            strokeColor="#3b82f6"
            trailColor="#374151"
            size="small"
          />
        </div>
      </div>
    </Card>
  );
};

export const DeepResearchPage: React.FC = () => {
  const navigate = useNavigate();
  const { currentSession } = useAppStore();
  const currentProject = useWorkspaceStore((state) => state.currentProject);
  const researchQuery = useResearchQuery();

  const [query, setQuery] = useState(currentSession?.query || '');
  const [subQuestions, setSubQuestions] = useState<SubQuestion[]>([]);
  const [iterationConfig, setIterationConfig] = useState<IterationConfig>({
    rounds: 5,
    docsPerRound: 5,
    focusTopics: [],
    analysisDepth: 'moderate',
    enableCrossValidation: true,
    synthesisMethod: 'sequential'
  });

  const [isResearching, setIsResearching] = useState(false);
  const [researchProgress, setResearchProgress] = useState(0);

  const extractedTopics = [
    '机器学习算法',
    '深度学习',
    '医疗影像',
    '临床诊断',
    '数据预处理',
    '模型验证',
    '伦理考量',
    '监管标准'
  ];

  const handleStartResearch = async () => {
    if (!query.trim()) {
      return;
    }

    if (!currentProject) {
      void message.warning('请先选择一个项目再启动深度研究');
      return;
    }

    setIsResearching(true);
    setResearchProgress(0);

    try {
      const result = await researchQuery.mutateAsync({
        project_id: currentProject.id,
        query,
        mode: 'deep',
        processing_method: 'deep_iterative',
        keywords: iterationConfig.focusTopics,
        auto_config: {
          iteration_rounds: iterationConfig.rounds,
          docs_per_round: iterationConfig.docsPerRound,
          analysis_depth: iterationConfig.analysisDepth,
          synthesis_method: iterationConfig.synthesisMethod,
          enable_cross_validation: iterationConfig.enableCrossValidation,
          sub_questions: subQuestions.map(sq => sq.text)
        }
      });

      // Navigate to results page or show progress
      console.log('Deep research started:', result);
    } catch (error) {
      console.error('Deep research failed:', error);
    } finally {
      setIsResearching(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-neural-900 to-neural-800 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <div className="flex items-center justify-between">
            <div>
              <Title level={2} className="!text-white !mb-2">
                <BrainCircuit className="w-8 h-8 inline mr-3 text-emerald-400" />
                深度研究工作台
              </Title>
              <Text className="text-neutral-400">
                专业研究工具，精确控制每个分析环节
              </Text>
            </div>
            <Button onClick={() => navigate('/')} className="border-neutral-600">
              返回首页
            </Button>
          </div>
        </motion.div>

        {!currentProject && (
          <Alert
            type="warning"
            showIcon
            message="请在研究工作台选择一个项目后再执行深度研究操作"
            className="mb-4"
          />
        )}

        {!isResearching ? (
          <Row gutter={[24, 24]}>
            {/* Main Configuration */}
            <Col xs={24} lg={16}>
              <div className="space-y-6">
                {/* Query Decomposition */}
                <QueryDecomposition
                  query={query}
                  onQueryUpdate={setQuery}
                  subQuestions={subQuestions}
                  onSubQuestionsUpdate={setSubQuestions}
                  onIterationConfigUpdate={(config) =>
                    setIterationConfig((prev) => ({
                      ...prev,
                      ...config,
                    }))
                  }
                  projectId={currentProject?.id}
                />

                {/* Start Research Button */}
                <Card className="border-neutral-700 text-center">
                  <Space direction="vertical" size="large">
                    <div>
                      <Title level={4} className="!text-white !mb-2">
                        准备启动深度研究
                      </Title>
                      <Text className="text-neutral-400">
                        配置完成后点击启动，系统将进行 {iterationConfig.rounds} 轮迭代分析
                      </Text>
                    </div>

                    <Button
                      type="primary"
                      size="large"
                      icon={<Play className="w-5 h-5" />}
                      onClick={handleStartResearch}
                      disabled={!query.trim() || subQuestions.length === 0 || !currentProject}
                      className="px-8"
                    >
                      启动深度研究
                    </Button>

                    {(!query.trim() || subQuestions.length === 0) && (
                      <Alert
                        message="请先完成问题拆解分析"
                        type="warning"
                        showIcon
                        className="mt-4"
                      />
                    )}
                  </Space>
                </Card>
              </div>
            </Col>

            {/* Configuration Panel */}
            <Col xs={24} lg={8}>
              <div className="space-y-6">
                <IterationConfigPanel
                  config={iterationConfig}
                  onConfigUpdate={setIterationConfig}
                  extractedTopics={extractedTopics}
                />

                {/* Literature Preview */}
                <Card className="border-neutral-700">
                  <Title level={5} className="!text-white !mb-4">
                    <Database className="w-5 h-5 inline mr-2" />
                    相关文献预览
                  </Title>

                  <div className="space-y-3">
                    {subQuestions.map(sq => (
                      <div key={sq.id} className="flex items-center justify-between">
                        <Text className="text-neutral-300 text-sm flex-1">
                          {sq.text.substring(0, 30)}...
                        </Text>
                        <Tag color="blue">
                          {sq.relatedLiteratureCount}篇
                        </Tag>
                      </div>
                    ))}
                  </div>

                  <Divider className="border-neutral-600 my-4" />

                  <div className="text-center">
                    <div className="text-2xl font-bold text-emerald-400">
                      {subQuestions.reduce((sum, sq) => sum + sq.relatedLiteratureCount, 0)}
                    </div>
                    <Text className="text-neutral-400 text-sm">总计可用文献</Text>
                  </div>
                </Card>

                {/* Research Tips */}
                <Card className="border-neutral-700">
                  <Title level={5} className="!text-white !mb-3">
                    <Lightbulb className="w-5 h-5 inline mr-2" />
                    研究建议
                  </Title>

                  <div className="space-y-2">
                    <div className="flex items-start space-x-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-2 flex-shrink-0" />
                      <Text className="text-neutral-400 text-sm">
                        问题越具体，分析结果越精确
                      </Text>
                    </div>
                    <div className="flex items-start space-x-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-2 flex-shrink-0" />
                      <Text className="text-neutral-400 text-sm">
                        选择重点主题可以提高分析针对性
                      </Text>
                    </div>
                    <div className="flex items-start space-x-2">
                      <div className="w-1.5 h-1.5 rounded-full bg-emerald-400 mt-2 flex-shrink-0" />
                      <Text className="text-neutral-400 text-sm">
                        交叉验证有助于提高结论可信度
                      </Text>
                    </div>
                  </div>
                </Card>
              </div>
            </Col>
          </Row>
        ) : (
          /* Research Progress View */
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="max-w-4xl mx-auto"
          >
            <Card className="border-neutral-700">
              <Title level={3} className="!text-white text-center !mb-6">
                深度研究进行中
              </Title>

              <div className="space-y-6">
                <Alert
                  message="AI正在进行深度迭代分析"
                  description="这个过程会比较耗时，请耐心等待。您可以随时查看详细进度。"
                  type="info"
                  showIcon
                />

                <div className="text-center">
                  <Progress
                    type="circle"
                    size={120}
                    percent={researchProgress}
                    strokeColor="#10b981"
                    trailColor="#374151"
                  />
                  <div className="mt-4">
                    <Text className="text-white text-lg">
                      第 2 轮 / 共 {iterationConfig.rounds} 轮
                    </Text>
                    <br />
                    <Text className="text-neutral-400">
                      正在处理第 3 篇文献...
                    </Text>
                  </div>
                </div>

                <Tabs defaultActiveKey="progress" className="custom-tabs">
                  <TabPane tab="进度详情" key="progress">
                    <div className="space-y-4">
                      {Array.from({ length: iterationConfig.rounds }, (_, i) => (
                        <div key={i} className="flex items-center justify-between p-3 bg-neutral-800 rounded">
                          <div>
                            <Text className="text-white">第 {i + 1} 轮迭代</Text>
                            <br />
                            <Text className="text-neutral-400 text-sm">
                              {i < 2 ? '已完成' : i === 2 ? '进行中' : '等待中'}
                            </Text>
                          </div>
                          <div className="text-right">
                            {i < 2 && <CheckCircle className="w-6 h-6 text-green-400" />}
                            {i === 2 && <Zap className="w-6 h-6 text-blue-400 animate-pulse" />}
                            {i > 2 && <Clock className="w-6 h-6 text-neutral-600" />}
                          </div>
                        </div>
                      ))}
                    </div>
                  </TabPane>

                  <TabPane tab="实时日志" key="logs">
                    <div className="space-y-2 max-h-64 overflow-y-auto">
                      <div className="text-xs text-neutral-400">
                        [15:23:15] 开始第2轮迭代分析
                      </div>
                      <div className="text-xs text-neutral-400">
                        [15:23:18] 处理文献: &ldquo;Deep Learning for Medical Diagnosis&rdquo;
                      </div>
                      <div className="text-xs text-primary-400">
                        [15:23:25] 提取关键概念: 卷积神经网络, 医疗影像
                      </div>
                      <div className="text-xs text-neutral-400">
                        [15:23:30] 与前轮知识进行交叉验证...
                      </div>
                    </div>
                  </TabPane>
                </Tabs>
              </div>
            </Card>
          </motion.div>
        )}
      </div>
    </div>
  );
};
