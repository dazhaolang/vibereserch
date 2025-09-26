import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, Button, Progress, Typography, Row, Col, Space, Timeline, Alert, Segmented } from 'antd';
import {
  Zap,
  Clock,
  Play,
  Eye,
  MessageSquare,
  Cpu,
  Database,
  FileText,
  BarChart3
} from 'lucide-react';
import { useLocation, useNavigate } from 'react-router-dom';
import { useAppStore } from '../../store/app-store';
import { useResearchQuery } from '../../hooks/api-hooks';
import { wsManager } from '@/services/websocket/WebSocketManager';

const { Title, Text, Paragraph } = Typography;

interface ClarificationOption {
  option_id: string;
  title: string;
  description: string;
  icon?: string;
  estimated_time?: string;
  estimated_results?: string;
  confidence_score: number;
  implications: string[];
  is_recommended: boolean;
}

interface ClarificationCardProps {
  option: ClarificationOption;
  onSelect: (optionId: string) => void;
  isSelected?: boolean;
  timeRemaining?: number;
}

type AgentStageKey = 'analysis' | 'search' | 'download' | 'extraction' | 'synthesis';
type AgentSelection = 'claude' | 'codex' | 'gemini';

type AgentPlan = Record<string, unknown>;

interface AutoIntentAnalysis {
  intent_confidence?: number;
  ambiguity_score?: number;
  clarification_needed?: boolean;
}

interface AutoAnalysisResult {
  session_id?: string;
  project_id?: number;
  clarification_options?: ClarificationOption[];
  intent_analysis?: AutoIntentAnalysis;
}

interface AutoResearchLocationState {
  analysisResult?: AutoAnalysisResult;
}

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const toAgentPlan = (value: unknown): AgentPlan | null => (isRecord(value) ? value : null);

const ClarificationCard: React.FC<ClarificationCardProps> = ({
  option,
  onSelect,
  isSelected,
  timeRemaining = 5000
}) => {
  const initialSeconds = Math.max(Math.ceil(timeRemaining / 1000), 1);
  const [countdown, setCountdown] = useState(initialSeconds);
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    setCountdown(initialSeconds);
    setIsVisible(true);

    if (timeRemaining <= 0) {
      return;
    }

    const timer = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          if (option.is_recommended) {
            onSelect(option.option_id);
          }
          setIsVisible(false);
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [initialSeconds, onSelect, option.is_recommended, option.option_id, timeRemaining]);

  const progressPercent = ((initialSeconds - countdown) / initialSeconds) * 100;

  return (
    <AnimatePresence>
      {isVisible && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9, y: 20 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.9, y: -20 }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          whileHover={{ y: -4, scale: 1.02 }}
          className="relative"
        >
          <Card
            className={`relative overflow-hidden cursor-pointer transition-all duration-300 ${
              isSelected
                ? 'ring-2 ring-primary-500 border-primary-500'
                : 'border-neutral-700 hover:border-primary-400'
            } ${option.is_recommended ? 'border-accent-500' : ''}`}
            onClick={() => onSelect(option.option_id)}
            bodyStyle={{ padding: '20px' }}
          >
            {/* Countdown Ring */}
            {option.is_recommended && countdown > 0 && (
              <div className="absolute top-3 right-3 w-8 h-8">
                <svg className="w-8 h-8 transform -rotate-90">
                  <circle
                    cx="16"
                    cy="16"
                    r="14"
                    stroke="currentColor"
                    strokeWidth="2"
                    fill="transparent"
                    className="text-neutral-600"
                  />
                  <circle
                    cx="16"
                    cy="16"
                    r="14"
                    stroke="currentColor"
                    strokeWidth="2"
                    fill="transparent"
                    strokeDasharray={`${2 * Math.PI * 14}`}
                    strokeDashoffset={`${2 * Math.PI * 14 * (1 - progressPercent / 100)}`}
                    className="text-accent-500 transition-all duration-1000 ease-linear"
                  />
                </svg>
                <div className="absolute inset-0 flex items-center justify-center text-sm font-bold text-accent-500">
                  {countdown}
                </div>
              </div>
            )}

            {/* Recommended Badge */}
            {option.is_recommended && (
              <div className="absolute top-0 right-0 bg-accent-500 text-white px-2 py-1 text-xs rounded-bl">
                推荐
              </div>
            )}

            <div className="flex items-start space-x-4">
              {/* Icon */}
              <div className="flex-shrink-0">
                <div className="w-12 h-12 rounded-lg bg-gradient-to-r from-primary-500 to-primary-600 flex items-center justify-center">
                  {option.icon ? (
                    <span className="text-2xl">{option.icon}</span>
                  ) : (
                    <Zap className="w-6 h-6 text-white" />
                  )}
                </div>
              </div>

              <div className="flex-1 min-w-0">
                {/* Title */}
                <Title level={5} className="!mb-2 !text-white">
                  {option.title}
                </Title>

                {/* Description */}
                <Paragraph className="!mb-3 !text-neutral-300 text-sm">
                  {option.description}
                </Paragraph>

                {/* Meta Info */}
                <div className="flex items-center space-x-4 mb-3">
                  {option.estimated_time && (
                    <div className="flex items-center text-neutral-400 text-xs">
                      <Clock className="w-3 h-3 mr-1" />
                      {option.estimated_time}
                    </div>
                  )}
                  <div className="flex items-center text-neutral-400 text-xs">
                    <BarChart3 className="w-3 h-3 mr-1" />
                    置信度 {Math.round(option.confidence_score * 100)}%
                  </div>
                </div>

                {/* Implications */}
                {option.implications && option.implications.length > 0 && (
                  <div className="space-y-1">
                    {option.implications.slice(0, 2).map((implication, index) => (
                      <div key={index} className="flex items-center text-neutral-400 text-xs">
                        <div className="w-1 h-1 rounded-full bg-primary-400 mr-2 flex-shrink-0" />
                        {implication}
                      </div>
                    ))}
                  </div>
                )}

                {/* Expected Results */}
                {option.estimated_results && (
                  <div className="mt-3 p-2 bg-neutral-800 rounded text-xs text-neutral-300">
                    <Text className="text-primary-400">预期结果：</Text>
                    {option.estimated_results}
                  </div>
                )}
              </div>
            </div>
          </Card>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

interface AgentOrchestrationProps {
  agentPlan?: AgentPlan | null;
  currentStage?: AgentStageKey;
}

const AgentOrchestration: React.FC<AgentOrchestrationProps> = ({ agentPlan, currentStage }) => {
  const stages: Array<{ key: AgentStageKey; title: string; icon: React.ReactNode }> = [
    { key: 'analysis', title: '问题分析', icon: <Cpu className="w-4 h-4" /> },
    { key: 'search', title: '文献搜索', icon: <Database className="w-4 h-4" /> },
    { key: 'download', title: 'PDF下载', icon: <FileText className="w-4 h-4" /> },
    { key: 'extraction', title: '内容提取', icon: <Eye className="w-4 h-4" /> },
    { key: 'synthesis', title: '知识合成', icon: <BarChart3 className="w-4 h-4" /> },
  ];

  return (
    <Card className="border-neutral-700">
      <Title level={5} className="!text-white !mb-4">
        <Cpu className="w-5 h-5 inline mr-2" />
        Claude Code 工具编排
      </Title>

      <Timeline
        items={stages.map(stage => ({
          dot: stage.icon,
          color: currentStage === stage.key ? 'blue' : 'gray',
          children: (
            <div>
              <Text className={currentStage === stage.key ? 'text-primary-400' : 'text-neutral-400'}>
                {stage.title}
              </Text>
              {currentStage === stage.key && (
                <div className="mt-1">
                  <Progress
                    percent={65}
                    size="small"
                    strokeColor="#3b82f6"
                    trailColor="#374151"
                  />
                </div>
              )}
            </div>
          ),
        }))}
      />

      {agentPlan && (
        <div className="mt-4 p-3 bg-neutral-800 rounded">
          <Text className="text-neutral-300 text-sm">
            AI编排计划：{JSON.stringify(agentPlan, null, 2)}
          </Text>
        </div>
      )}
    </Card>
  );
};

export const AutoResearchPage: React.FC = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const { currentSession } = useAppStore();

  const [selectedOption, setSelectedOption] = useState<string | null>(null);
  const [clarificationPhase, setClarificationPhase] = useState(true);
  const [researchPhase, setResearchPhase] = useState(false);
  const [agentPlan, setAgentPlan] = useState<AgentPlan | null>(null);
  const currentStage: AgentStageKey = 'analysis';
  const [selectedAgent, setSelectedAgent] = useState<AgentSelection>('claude');

  const researchQuery = useResearchQuery();

  // Get analysis result from navigation state
  const locationState = (location.state ?? null) as AutoResearchLocationState | null;
  const analysisResult = locationState?.analysisResult;
  const clarificationOptions = analysisResult?.clarification_options ?? [];
  const hasRecommendedOption = clarificationOptions.some((opt) => opt.is_recommended);
  const intentAnalysis = analysisResult?.intent_analysis;

  useEffect(() => {
    if (analysisResult?.session_id) {
      wsManager.subscribeToSession(analysisResult.session_id);
    }

    return () => {
      if (analysisResult?.session_id) {
        wsManager.unsubscribeFromSession(analysisResult.session_id);
      }
    };
  }, [analysisResult]);

  const handleOptionSelect = async (optionId: string) => {
    if (!analysisResult) {
      return;
    }

    setSelectedOption(optionId);
    setClarificationPhase(false);
    setResearchPhase(true);

    // Find selected option details
    const selectedOptionData = clarificationOptions.find(
      (opt) => opt.option_id === optionId
    );

    try {
      // Start research with selected parameters
      const sessionContext = currentSession?.context as unknown;
      const contextProjectId =
        isRecord(sessionContext) && typeof sessionContext.project_id === 'number'
          ? sessionContext.project_id
          : undefined;

      const projectId =
        (typeof analysisResult.project_id === 'number' ? analysisResult.project_id : undefined) ??
        contextProjectId ??
        1;

      const processingMethod =
        selectedOptionData && selectedOptionData.title.includes('深度') ? 'deep' : 'standard';

      const result = await researchQuery.mutateAsync({
        project_id: projectId,
        query: currentSession?.query || '',
        mode: 'auto',
        auto_config: {
          processing_method: processingMethod,
          enable_ai_filtering: true,
          enable_pdf_processing: true,
          enable_structured_extraction: true,
        },
        agent: selectedAgent,
      });

      // 使用新的结构化响应
      const structuredPlan = toAgentPlan(result.payload['structured_plan']);
      const fallbackPlan = toAgentPlan(result.payload['agent_plan']);
      setAgentPlan(structuredPlan ?? fallbackPlan);

      // 如果有阶段详情，使用它来更新进度
      const stageDetails = result.payload['stage_details'];
      if (isRecord(stageDetails)) {
        console.log('Stage details received:', stageDetails);
        // TODO: 集成到进度显示组件
      }
    } catch (error) {
      console.error('Research query failed:', error);
    }
  };

  const handleManualInput = () => {
    // Allow user to input custom parameters
    console.log('Manual input requested');
  };

  if (!analysisResult) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Alert
          message="未找到分析结果"
          description="请返回首页重新开始研究"
          type="warning"
          showIcon
          action={
            <Button onClick={() => navigate('/')}>
              返回首页
            </Button>
          }
        />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-neural-900 to-neural-800 p-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-8"
        >
          <div className="flex items-center justify-between">
            <div>
              <Title level={2} className="!text-white !mb-2">
                <Zap className="w-8 h-8 inline mr-3 text-primary-400" />
                全自动研究模式
              </Title>
              <Text className="text-neutral-400">
                AI正在分析您的需求：&ldquo;{currentSession?.query}&rdquo;
              </Text>
            </div>
            <Space size="middle">
              <div className="text-right">
                <Text className="text-neutral-400 block mb-1">选择调度核心</Text>
                <Segmented
                  size="middle"
                  options={[
                    { label: 'Claude', value: 'claude' },
                    { label: 'CodeX', value: 'codex' },
                    { label: 'Gemini CLI', value: 'gemini' },
                  ]}
                  value={selectedAgent}
                  onChange={value => setSelectedAgent(value as 'claude' | 'codex' | 'gemini')}
                />
              </div>
              <Button onClick={() => navigate('/')} className="border-neutral-600">
                返回首页
              </Button>
            </Space>
          </div>
        </motion.div>

        <Row gutter={[24, 24]}>
          {/* Main Content */}
          <Col xs={24} lg={16}>
            {clarificationPhase && clarificationOptions.length > 0 && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
              >
                <Card className="border-neutral-700 mb-6">
                  <Title level={4} className="!text-white !mb-4">
                    <MessageSquare className="w-5 h-5 inline mr-2" />
                    请选择研究方向
                  </Title>
                  <Text className="text-neutral-300 block mb-4">
                    AI已分析您的需求，请选择最符合您期望的研究方向。
                    {hasRecommendedOption && (
                      <span className="text-accent-400 ml-2">
                        5秒后将自动选择推荐选项
                      </span>
                    )}
                  </Text>
                </Card>

                <div className="space-y-4">
                  {clarificationOptions.map((option) => (
                    <ClarificationCard
                      key={option.option_id}
                      option={option}
                      onSelect={handleOptionSelect}
                      isSelected={selectedOption === option.option_id}
                      timeRemaining={5000}
                    />
                  ))}
                </div>

                <div className="mt-6 text-center">
                  <Button
                    type="default"
                    onClick={handleManualInput}
                    className="border-neutral-600"
                  >
                    自定义参数
                  </Button>
                </div>
              </motion.div>
            )}

            {researchPhase && (
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.3 }}
              >
                <Card className="border-neutral-700">
                  <Title level={4} className="!text-white !mb-4">
                    <Play className="w-5 h-5 inline mr-2" />
                    研究进行中
                  </Title>

                  <div className="space-y-4">
                    <Alert
                      message="AI正在执行您的研究任务"
                      description="请耐心等待，整个过程预计需要3-5分钟"
                      type="info"
                      showIcon
                    />

                    <div className="flex items-center justify-between p-4 bg-neutral-800 rounded">
                      <div>
                        <Text className="text-white">总体进度</Text>
                        <div className="text-xs text-neutral-400 mt-1">
                          已完成 2/5 个阶段
                        </div>
                      </div>
                      <div className="text-right">
                        <div className="text-2xl font-bold text-primary-400">40%</div>
                        <Progress
                          percent={40}
                          size="small"
                          strokeColor="#3b82f6"
                          trailColor="#374151"
                          className="w-32"
                        />
                      </div>
                    </div>
                  </div>
                </Card>
              </motion.div>
            )}
          </Col>

          {/* Sidebar */}
          <Col xs={24} lg={8}>
            <div className="space-y-6">
              {/* Intent Analysis Results */}
              <Card className="border-neutral-700">
                <Title level={5} className="!text-white !mb-4">
                  意图分析结果
                </Title>
                <div className="space-y-3">
                  <div className="flex justify-between">
                    <Text className="text-neutral-400">意图置信度</Text>
                    <Text className="text-primary-400">
                      {Math.round((intentAnalysis?.intent_confidence ?? 0) * 100)}%
                    </Text>
                  </div>
                  <div className="flex justify-between">
                    <Text className="text-neutral-400">模糊程度</Text>
                    <Text className="text-accent-400">
                      {Math.round((intentAnalysis?.ambiguity_score ?? 0) * 100)}%
                    </Text>
                  </div>
                  <div className="flex justify-between">
                    <Text className="text-neutral-400">需要澄清</Text>
                    <Text className={intentAnalysis?.clarification_needed ? 'text-orange-400' : 'text-green-400'}>
                      {intentAnalysis?.clarification_needed ? '是' : '否'}
                    </Text>
                  </div>
                </div>
              </Card>

              {/* Agent Orchestration */}
              {researchPhase && (
                <AgentOrchestration
                  agentPlan={agentPlan}
                  currentStage={currentStage}
                />
              )}

              {/* Real-time Logs */}
              {researchPhase && (
                <Card className="border-neutral-700">
                  <Title level={5} className="!text-white !mb-4">
                    实时日志
                  </Title>
                  <div className="space-y-2 max-h-48 overflow-y-auto">
                    <div className="text-xs text-neutral-400">
                      [14:32:15] 开始问题分析...
                    </div>
                    <div className="text-xs text-neutral-400">
                      [14:32:18] 检测到关键词: 机器学习, 医疗诊断
                    </div>
                    <div className="text-xs text-primary-400">
                      [14:32:20] 启动文献搜索工具...
                    </div>
                    <div className="text-xs text-neutral-400">
                      [14:32:25] 找到 127 篇相关文献
                    </div>
                  </div>
                </Card>
              )}
            </div>
          </Col>
        </Row>
      </div>
    </div>
  );
};
