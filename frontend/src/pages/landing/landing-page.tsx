import React, { useState } from 'react';
import { motion } from 'framer-motion';
import { Input, Card, Button, Space, Tag, Typography, Row, Col, Divider } from 'antd';
import {
  BrainCircuit,
  Search,
  Zap,
  BookOpen,
  ArrowRight,
  Sparkles,
  Target
} from 'lucide-react';
import { useStartInteraction, useRecentProjects } from '../../hooks/api-hooks';
import type { RecentProject } from '../../hooks/api-hooks';
import { useNavigate } from 'react-router-dom';
import { useAppStore } from '../../store/app-store';
import { useResearchShellStore } from '@/stores/research-shell.store';
import { useResearchStore } from '@/stores/research.store';
import { useConversationStore } from '@/stores/conversation.store';

const { Text, Title } = Typography;
const { TextArea } = Input;

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

export const LandingPage: React.FC = () => {
  const [userInput, setUserInput] = useState('');
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const navigate = useNavigate();

  const startInteraction = useStartInteraction();
  const { data: recentProjects } = useRecentProjects();
  const { setCurrentSession } = useAppStore();
  const setLibraryId = useResearchShellStore((state) => state.setLibraryId);
  const setLibraryStatus = useResearchShellStore((state) => state.setLibraryStatus);
  const syncTasks = useResearchStore((state) => state.syncTasks);
  const resetConversation = useConversationStore((state) => state.reset);
  const setMode = useResearchShellStore((state) => state.setMode);

  const handleAnalyzeIntent = async () => {
    if (!userInput.trim()) return;

    setIsAnalyzing(true);
    try {
      const result = await startInteraction.mutateAsync({
        user_input: userInput,
        project_id: recentProjects?.[0]?.id ?? 1,
      });

      const resolvedProjectId = (() => {
        const directParameters = result.direct_action?.parameters;
        const directProjectRaw = isRecord(directParameters) ? directParameters.project_id : undefined;
        if (typeof directProjectRaw === 'number') {
          return directProjectRaw;
        }
        return recentProjects?.[0]?.id ?? null;
      })();

      if (resolvedProjectId !== null) {
        setLibraryId(resolvedProjectId);
        setLibraryStatus('building');
        void syncTasks(resolvedProjectId);
      }

      resetConversation();
      setMode('auto');

      setCurrentSession({
        mode: 'auto',
        sessionId: result.session_id,
        query: userInput,
        context: { interaction: result },
        startTime: new Date(),
      });

      // 默认跳转至研究控制台，让用户在统一界面继续流程
      navigate('/research', {
        state: {
          analysisResult: result,
          forcedMode: result.direct_action?.action_type === 'rag_query'
            ? 'rag'
            : result.direct_action?.action_type === 'deep_research'
              ? 'deep'
              : 'auto',
        },
        replace: false,
      });
    } catch (error) {
      console.error('Intent analysis failed:', error);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const modeCards = [
    {
      key: 'auto',
      title: '全自动研究',
      subtitle: '让AI承担一切复杂性',
      description: '描述您的研究需求，AI将自动选择最佳工具组合，完成从文献搜索到深度分析的全流程',
      icon: <Zap className="w-8 h-8" />,
      color: 'from-blue-500 to-purple-600',
      features: ['智能工具编排', 'Claude Code集成', '端到端自动化', '实时进度追踪'],
      path: '/auto'
    },
    {
      key: 'deep',
      title: '深度研究模式',
      subtitle: '专业工具，精确控制',
      description: '适合复杂研究问题，提供精细化参数调整和迭代式知识合成',
      icon: <BrainCircuit className="w-8 h-8" />,
      color: 'from-emerald-500 to-teal-600',
      features: ['问题拆解可视化', '迭代知识合成', '专业参数控制', '知识图谱分析'],
      path: '/deep'
    },
    {
      key: 'rag',
      title: 'RAG问答空间',
      subtitle: '快速响应，直观反馈',
      description: '基于已有文献库的快速问答，支持上下文选择和相关问题推荐',
      icon: <Search className="w-8 h-8" />,
      color: 'from-orange-500 to-red-600',
      features: ['即时智能问答', '上下文文献选择', '引用来源追踪', '相关问题推荐'],
      path: '/rag'
    }
  ];

  return (
    <div className="min-h-screen bg-gradient-to-br from-neural-900 via-neural-800 to-neural-900 relative overflow-hidden">
      {/* Aurora Background */}
      <div className="absolute inset-0 aurora-bg opacity-20" />

      {/* Main Content */}
      <div className="relative z-10 container mx-auto px-6 py-12">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8 }}
          className="text-center mb-16"
        >
          <div className="flex items-center justify-center mb-6">
            <Sparkles className="w-12 h-12 text-primary-400 mr-4" />
            <Title level={1} className="!text-white !mb-0">
              深度研究AI平台
            </Title>
          </div>
          <Text className="text-xl text-neutral-300 max-w-2xl mx-auto block">
            基于AI的智能研究助手，从文献搜索到深度分析，让研究变得简单而高效
          </Text>
        </motion.div>

        {/* Intent Analysis Input */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.2 }}
          className="max-w-4xl mx-auto mb-16"
        >
          <Card className="glass border border-white/20 shadow-2xl">
            <div className="text-center mb-6">
              <Target className="w-8 h-8 text-primary-400 mx-auto mb-2" />
              <Title level={3} className="!text-white !mb-2">
                描述您的研究需求
              </Title>
              <Text className="text-neutral-400">
                AI将分析您的意图，推荐最适合的研究模式
              </Text>
            </div>

            <Space.Compact className="w-full">
              <TextArea
                value={userInput}
                onChange={(e) => setUserInput(e.target.value)}
                placeholder="例如：我想了解机器学习在医疗诊断中的最新应用..."
                rows={3}
                className="flex-1"
                size="large"
              />
              <Button
                type="primary"
                size="large"
                loading={isAnalyzing}
                onClick={handleAnalyzeIntent}
                className="h-auto px-8"
                icon={<ArrowRight className="w-5 h-5" />}
              >
                智能分析
              </Button>
            </Space.Compact>

            {/* Quick Examples */}
            <div className="mt-4">
              <Text className="text-neutral-500 text-sm">快速示例：</Text>
              <div className="flex flex-wrap gap-2 mt-2">
                {[
                  '量子计算的最新突破',
                  '可持续能源技术发展趋势',
                  '人工智能伦理问题研究'
                ].map((example) => (
                  <Tag
                    key={example}
                    className="cursor-pointer hover:bg-primary-600 transition-colors"
                    onClick={() => setUserInput(example)}
                  >
                    {example}
                  </Tag>
                ))}
              </div>
            </div>
          </Card>
        </motion.div>

        {/* Mode Cards */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.4 }}
          className="mb-16"
        >
          <Title level={2} className="!text-white text-center mb-8">
            选择研究模式
          </Title>

          <Row gutter={[24, 24]}>
            {modeCards.map((mode, index) => (
              <Col xs={24} lg={8} key={mode.key}>
                <motion.div
                  initial={{ opacity: 0, y: 30 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.6, delay: 0.1 * index }}
                  whileHover={{ y: -8, scale: 1.02 }}
                  className="h-full"
                >
                  <Card
                    className="h-full glass border border-white/20 hover:border-white/40 transition-all duration-300 cursor-pointer card-hover"
                    onClick={() => navigate(mode.path)}
                    bodyStyle={{ height: '100%', display: 'flex', flexDirection: 'column' }}
                  >
                    <div className={`w-16 h-16 rounded-full bg-gradient-to-r ${mode.color} flex items-center justify-center mb-4 mx-auto`}>
                      <div className="text-white">
                        {mode.icon}
                      </div>
                    </div>

                    <div className="text-center mb-4">
                      <Title level={4} className="!text-white !mb-2">
                        {mode.title}
                      </Title>
                      <Text className="text-primary-400 text-sm">
                        {mode.subtitle}
                      </Text>
                    </div>

                    <Text className="text-neutral-300 text-center mb-4 flex-1">
                      {mode.description}
                    </Text>

                    <div className="space-y-2">
                      {mode.features.map((feature) => (
                        <div key={feature} className="flex items-center text-neutral-400 text-sm">
                          <div className="w-1.5 h-1.5 rounded-full bg-primary-400 mr-2" />
                          {feature}
                        </div>
                      ))}
                    </div>
                  </Card>
                </motion.div>
              </Col>
            ))}
          </Row>
        </motion.div>

        {/* Recent Projects */}
        {recentProjects && recentProjects.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.6 }}
            className="max-w-4xl mx-auto"
          >
            <Title level={3} className="!text-white mb-6">
              <BookOpen className="w-6 h-6 inline mr-2" />
              最近的项目
            </Title>

            <Row gutter={[16, 16]}>
              {recentProjects.slice(0, 3).map((project: RecentProject) => (
                <Col xs={24} md={8} key={project.id}>
                  <Card className="glass border border-white/10 hover:border-white/30 transition-all cursor-pointer">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <Title level={5} className="!text-white !mb-1">
                          {project.name}
                        </Title>
                        <Text className="text-neutral-400 text-sm">
                          {project.description || '暂无描述'}
                        </Text>
                      </div>
                      <Tag color="blue" className="ml-2">
                        {project.literature_count || 0} 篇文献
                      </Tag>
                    </div>
                  </Card>
                </Col>
              ))}
            </Row>
          </motion.div>
        )}

        {/* Quick Stats */}
        <motion.div
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.8 }}
          className="mt-16 text-center"
        >
          <Divider className="border-white/20" />
          <Row gutter={[32, 16]} className="max-w-2xl mx-auto">
            <Col xs={12} sm={6}>
              <div className="text-center">
                <div className="text-2xl font-bold text-primary-400">200+</div>
                <div className="text-neutral-400 text-sm">文献处理能力</div>
              </div>
            </Col>
            <Col xs={12} sm={6}>
              <div className="text-center">
                <div className="text-2xl font-bold text-primary-400">70%</div>
                <div className="text-neutral-400 text-sm">效率提升</div>
              </div>
            </Col>
            <Col xs={12} sm={6}>
              <div className="text-center">
                <div className="text-2xl font-bold text-primary-400">50%</div>
                <div className="text-neutral-400 text-sm">成本降低</div>
              </div>
            </Col>
            <Col xs={12} sm={6}>
              <div className="text-center">
                <div className="text-2xl font-bold text-primary-400">24/7</div>
                <div className="text-neutral-400 text-sm">智能服务</div>
              </div>
            </Col>
          </Row>
        </motion.div>
      </div>
    </div>
  );
};
