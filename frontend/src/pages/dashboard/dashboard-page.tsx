import React, { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Row, Col, Card, Statistic, Progress, List, Avatar,
  Button, Space, Typography, Badge, Skeleton
} from 'antd';
import {
  ExperimentOutlined,
  RiseOutlined,
  TeamOutlined,
  ClockCircleOutlined,
  ThunderboltOutlined,
  BookOutlined,
  BulbOutlined,
  RocketOutlined,
  FireOutlined,
  SearchOutlined,
  PlusOutlined,
  CheckCircleOutlined,
} from '@ant-design/icons';
import { motion } from 'framer-motion';
import { useNavigate } from 'react-router-dom';
import { useProjects, useTaskOverview } from '@/hooks/api-hooks';
import { fetchUsageStatistics } from '@/services/api/usage';
import { UnifiedBackground } from '@/components/layout/UnifiedBackground';

const { Title, Text, Paragraph } = Typography;

interface DashboardStats {
  totalProjects: number;
  totalLiterature: number;
  totalExperience: number;
  activeResearch: number;
  weeklyGrowth: number;
  monthlyQueries: number;
  successRate: number;
  avgResponseTime: number;
}

interface RecentActivity {
  id: string;
  type: 'research' | 'upload' | 'experience' | 'collaboration';
  title: string;
  description: string;
  timestamp: string;
  icon: React.ReactNode;
  color: string;
}

export const DashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const projectsQuery = useProjects();
  const taskOverviewQuery = useTaskOverview();
  const usageStatsQuery = useQuery({
    queryKey: ['usage-statistics'],
    queryFn: fetchUsageStatistics,
    staleTime: 60_000,
  });

  const isLoading = projectsQuery.isLoading || taskOverviewQuery.isLoading || usageStatsQuery.isLoading;

  const usageStats = usageStatsQuery.data;
  const taskOverview = taskOverviewQuery.data;

  const totalProjects = usageStats?.usage?.total_projects ?? projectsQuery.data?.length ?? 0;
  const totalLiterature = usageStats?.usage?.total_literature ?? 0;
  const completedTasks = usageStats?.usage?.completed_tasks ?? 0;
  const runningTasks = taskOverview?.running_task_ids?.length ?? 0;
  const monthlyQueries = usageStats?.usage?.monthly_queries_used ?? 0;

  const statusBreakdown = taskOverview?.status_breakdown ?? {};
  const completedCount = Number(statusBreakdown?.completed ?? statusBreakdown?.COMPLETED ?? 0);
  const totalTasks = taskOverview?.total_tasks ?? 0;
  const successRate = totalTasks ? (completedCount / totalTasks) * 100 : 0;

  const stats: DashboardStats = {
    totalProjects,
    totalLiterature,
    totalExperience: completedTasks,
    activeResearch: runningTasks,
    weeklyGrowth: successRate,
    monthlyQueries,
    successRate,
    avgResponseTime: 0,
  };

  const recentActivities: RecentActivity[] = useMemo(() => {
    const recent = taskOverview?.recent_tasks ?? [];
    return recent.map((task, index) => {
      const taskId = task.id ?? task.task_id ?? index;
      const status = (task.status ?? '').toLowerCase();
      const createdAt = task.created_at ? new Date(task.created_at).toLocaleString() : '';

      return {
        id: String(taskId),
        type: 'research',
        title: task.title ?? task.task_type ?? `任务 ${taskId}`,
        description: task.description ?? '无详细描述',
        timestamp: createdAt,
        icon: status === 'completed' ? <CheckCircleOutlined /> : <ThunderboltOutlined />,
        color: status === 'failed' ? '#f87171' : '#1890ff',
      };
    });
  }, [taskOverview]);

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1,
      },
    },
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: {
        duration: 0.5,
      },
    },
  };

  return (
    <UnifiedBackground variant="gradient">
      <div className="p-4 md:p-6">
        <motion.div
          variants={containerVariants}
          initial="hidden"
          animate="visible"
        >
          {/* Header */}
          <motion.div variants={itemVariants} className="mb-6">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <Title level={2} className="mb-0 bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
                  智能研究工作台
                </Title>
                <Text type="secondary">欢迎回来，今天是探索科学的好日子 🚀</Text>
              </div>
              <Space wrap align="end">
                <Button
                  type="primary"
                  icon={<PlusOutlined />}
                  onClick={() => navigate('/workspace')}
                  className="bg-gradient-to-r from-blue-500 to-purple-500 border-0"
                >
                  开始研究
                </Button>
                <Button
                  icon={<SearchOutlined />}
                  onClick={() => navigate('/library')}
                >
                  文献库
                </Button>
              </Space>
            </div>
          </motion.div>

          {/* Stats Cards */}
          <Row gutter={[24, 24]}>
            <Col xs={24} sm={12} lg={6}>
              <motion.div variants={itemVariants}>
                <Card
                  className="hover:shadow-xl transition-all duration-300 border-0"
                  style={{
                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                  }}
                >
                  <Statistic
                    title={<span className="text-white opacity-90">研究项目</span>}
                    value={stats.totalProjects}
                    prefix={<ExperimentOutlined className="text-white" />}
                    valueStyle={{ color: 'white', fontSize: '32px', fontWeight: 'bold' }}
                  />
                  <div className="mt-2">
                    <Badge status="processing" />
                    <Text className="text-white opacity-75 ml-2">
                      {stats.activeResearch} 个进行中
                    </Text>
                  </div>
                </Card>
              </motion.div>
            </Col>

            <Col xs={24} sm={12} lg={6}>
              <motion.div variants={itemVariants}>
                <Card
                  className="hover:shadow-xl transition-all duration-300 border-0"
                  style={{
                    background: 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
                  }}
                >
                  <Statistic
                    title={<span className="text-white opacity-90">文献总数</span>}
                    value={stats.totalLiterature}
                    prefix={<BookOutlined className="text-white" />}
                    valueStyle={{ color: 'white', fontSize: '32px', fontWeight: 'bold' }}
                  />
                  <div className="mt-2 flex items-center">
                    <RiseOutlined className="text-white" />
                    <Text className="text-white opacity-75 ml-2">
                      本周新增 {Math.floor(stats.weeklyGrowth)}
                    </Text>
                  </div>
                </Card>
              </motion.div>
            </Col>

            <Col xs={24} sm={12} lg={6}>
              <motion.div variants={itemVariants}>
                <Card
                  className="hover:shadow-xl transition-all duration-300 border-0"
                  style={{
                    background: 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
                  }}
                >
                  <Statistic
                    title={<span className="text-white opacity-90">研究经验</span>}
                    value={stats.totalExperience}
                    prefix={<BulbOutlined className="text-white" />}
                    suffix={<span className="text-white text-sm">条</span>}
                    valueStyle={{ color: 'white', fontSize: '32px', fontWeight: 'bold' }}
                  />
                  <Progress
                    percent={stats.successRate}
                    strokeColor="white"
                    trailColor="rgba(255,255,255,0.3)"
                    showInfo={false}
                    className="mt-2"
                  />
                </Card>
              </motion.div>
            </Col>

            <Col xs={24} sm={12} lg={6}>
              <motion.div variants={itemVariants}>
                <Card
                  className="hover:shadow-xl transition-all duration-300 border-0"
                  style={{
                    background: 'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
                  }}
                >
                  <Statistic
                    title={<span className="text-white opacity-90">响应速度</span>}
                    value={stats.avgResponseTime}
                    prefix={<ThunderboltOutlined className="text-white" />}
                    suffix={<span className="text-white text-sm">秒</span>}
                    valueStyle={{ color: 'white', fontSize: '32px', fontWeight: 'bold' }}
                  />
                  <div className="mt-2 flex items-center">
                    <FireOutlined className="text-white animate-pulse" />
                    <Text className="text-white opacity-75 ml-2">
                      极速响应
                    </Text>
                  </div>
                </Card>
              </motion.div>
            </Col>
          </Row>

          {/* Recent Activities */}
          <Row gutter={[24, 24]} className="mt-6">
            <Col xs={24}>
              <motion.div variants={itemVariants}>
                <Card
                  title={
                    <div className="flex items-center">
                      <ClockCircleOutlined className="mr-2 text-green-500" />
                      <span className="font-semibold">最近活动</span>
                    </div>
                  }
                  className="shadow-lg border-0"
                  extra={
                    <Button type="link" onClick={() => navigate('/tasks')}>
                      查看全部
                    </Button>
                  }
                >
                  {isLoading ? (
                    <Skeleton active />
                  ) : (
                    <List
                      itemLayout="horizontal"
                      dataSource={recentActivities}
                      renderItem={(item) => (
                        <List.Item>
                          <List.Item.Meta
                            avatar={
                              <Avatar
                                icon={item.icon}
                                style={{ backgroundColor: item.color }}
                                className="shadow-md"
                              />
                            }
                            title={
                              <div className="flex items-center justify-between">
                                <span className="font-medium">{item.title}</span>
                                <Text type="secondary" className="text-xs">
                                  {item.timestamp}
                                </Text>
                              </div>
                            }
                            description={
                              <Paragraph className="mb-0 text-gray-600">
                                {item.description}
                              </Paragraph>
                            }
                          />
                        </List.Item>
                      )}
                    />
                  )}
                </Card>
              </motion.div>
            </Col>
          </Row>

          {/* Quick Actions */}
          <motion.div variants={itemVariants} className="mt-6">
            <Card className="shadow-lg border-0 bg-gradient-to-r from-blue-50 to-purple-50">
              <Title level={4}>快速开始</Title>
              <Row gutter={[16, 16]}>
                {[
                  { icon: <SearchOutlined />, title: 'RAG检索', desc: '快速检索知识库', color: '#1890ff' },
                  { icon: <BulbOutlined />, title: '深度研究', desc: '生成研究经验', color: '#722ed1' },
                  { icon: <RocketOutlined />, title: '全自动模式', desc: 'AI编排流程', color: '#52c41a' },
                  { icon: <TeamOutlined />, title: '团队协作', desc: '邀请成员', color: '#fa8c16' },
                ].map((action, index) => (
                  <Col xs={12} sm={6} key={index}>
                    <motion.div
                      whileHover={{ scale: 1.05 }}
                      whileTap={{ scale: 0.95 }}
                    >
                      <Card
                        hoverable
                        className="text-center cursor-pointer"
                        onClick={() => navigate('/workspace')}
                      >
                        <Avatar
                          size={48}
                          icon={action.icon}
                          style={{ backgroundColor: action.color }}
                        />
                        <Title level={5} className="mt-3 mb-1">{action.title}</Title>
                        <Text type="secondary" className="text-xs">{action.desc}</Text>
                      </Card>
                    </motion.div>
                  </Col>
                ))}
              </Row>
            </Card>
          </motion.div>
        </motion.div>
      </div>
    </UnifiedBackground>
  );
};
