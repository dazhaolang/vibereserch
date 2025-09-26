import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Badge,
  Button,
  Card,
  Col,
  Divider,
  Empty,
  Form,
  Input,
  Modal,
  Row,
  Space,
  Statistic,
  Tag,
  Tooltip,
  Typography,
  message,
  Steps,
} from 'antd';
import {
  FileTextOutlined,
  FolderAddOutlined,
  PlusOutlined,
  RocketOutlined,
  SettingOutlined,
  ThunderboltOutlined,
  CheckCircleOutlined,
  ClockCircleOutlined,
  PlayCircleOutlined,
  PauseCircleOutlined,
} from '@ant-design/icons';
import { motion } from 'framer-motion';
import { projectAPI, type Project, type CreateEmptyProjectPayload } from '@/services/api/project';
import { useAppStore } from '@/stores/app.store';
import styles from './project-list-page.module.css';

const { Title, Text, Paragraph } = Typography;
const { Step } = Steps;

const projectStatusMeta: Record<string, { label: string; color: string; ribbon: string }> = {
  empty: { label: '待启动', color: 'default', ribbon: '#6366F1' },
  active: { label: '进行中', color: 'processing', ribbon: '#38BDF8' },
  completed: { label: '已完成', color: 'success', ribbon: '#22C55E' },
  archived: { label: '已归档', color: 'warning', ribbon: '#F97316' },
  processing: { label: '处理中', color: 'processing', ribbon: '#a855f7' },
  pending: { label: '排队中', color: 'warning', ribbon: '#facc15' },
  unknown: { label: '未标记', color: 'default', ribbon: '#94a3b8' },
};

// Mobile step indicator mapping
const getStepIcon = (status: string) => {
  switch (status) {
    case 'completed':
      return <CheckCircleOutlined />;
    case 'active':
    case 'processing':
      return <PlayCircleOutlined />;
    case 'pending':
      return <ClockCircleOutlined />;
    case 'archived':
      return <PauseCircleOutlined />;
    default:
      return <FolderAddOutlined />;
  }
};

const getStepStatus = (status: string): 'wait' | 'process' | 'finish' | 'error' => {
  switch (status) {
    case 'completed':
      return 'finish';
    case 'active':
    case 'processing':
      return 'process';
    case 'pending':
    case 'empty':
      return 'wait';
    default:
      return 'wait';
  }
};

const containerVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { staggerChildren: 0.1 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, scale: 0.96 },
  visible: { opacity: 1, scale: 1, transition: { duration: 0.25 } },
};

export const ProjectListPage = () => {
  const navigate = useNavigate();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalOpen, setCreateModalOpen] = useState(false);
  const [form] = Form.useForm<CreateEmptyProjectPayload>();
  const { setCurrentProject, setAvailableProjects } = useAppStore((state) => ({
    setCurrentProject: state.setCurrentProject,
    setAvailableProjects: state.setAvailableProjects,
  }));

  const refreshProjects = useCallback(async () => {
    setLoading(true);
    try {
      const items = await projectAPI.getProjects();
      setProjects(items);
      setAvailableProjects(
        items.map((project) => ({
          id: project.id,
          title: project.title,
          description: project.description ?? undefined,
          created_at: project.created_at,
          updated_at: project.updated_at ?? undefined,
        }))
      );
    } catch (error) {
      console.error('Failed to fetch projects:', error);
      void message.error('获取项目列表失败');
    } finally {
      setLoading(false);
    }
  }, [setAvailableProjects]);

  useEffect(() => {
    void refreshProjects();
  }, [refreshProjects]);

  const handleCreateProject = async (payload: CreateEmptyProjectPayload) => {
    try {
      const created = await projectAPI.createEmptyProject(payload);
      void message.success('项目创建成功');
      setCreateModalOpen(false);
      form.resetFields();
      setProjects((prev) => [...prev, created]);
      setCurrentProject({
        id: created.id,
        title: created.title,
        description: created.description ?? undefined,
        created_at: created.created_at,
        updated_at: created.updated_at ?? undefined,
      });
      navigate(`/projects/${created.id}/overview`);
    } catch (error) {
      console.error('Failed to create project', error);
      void message.error('项目创建失败');
    }
  };

  const groupedProjects = useMemo(() => {
    const statusMap: Record<string, Project[]> = {};
    projects.forEach((project) => {
      const key = project.status ?? 'unknown';
      if (!statusMap[key]) {
        statusMap[key] = [];
      }
      statusMap[key].push(project);
    });
    return statusMap;
  }, [projects]);

  const totalLiterature = projects.reduce((acc, project) => acc + (project.literature_count ?? 0), 0);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
        <Space direction="vertical" size={4}>
          <Title level={2} className="m-0">项目中心</Title>
          <Text type="secondary">管理所有科研项目，查看文献、任务与最新进展</Text>
        </Space>
        <Space wrap>
          <Button icon={<RocketOutlined />} onClick={() => void refreshProjects()} loading={loading}>
            刷新
          </Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateModalOpen(true)}>
            新建项目
          </Button>
        </Space>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card bordered={false} className="shadow-sm">
            <Statistic title="项目总数" value={projects.length} prefix={<FolderAddOutlined />} />
            <Text type="secondary">按状态分布管理不同阶段的研究任务</Text>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card bordered={false} className="shadow-sm">
            <Statistic title="累计文献" value={totalLiterature} prefix={<FileTextOutlined />} />
            <Text type="secondary">已建库和待处理的全部文献</Text>
          </Card>
        </Col>
        <Col xs={24} md={8}>
          <Card bordered={false} className="shadow-sm">
            <Statistic
              title="进行中任务"
              value={projects.filter((p) => ['active', 'processing'].includes(p.status)).length}
              prefix={<ThunderboltOutlined />}
            />
            <Text type="secondary">实时关注自动流程的执行情况</Text>
          </Card>
        </Col>
      </Row>

      {projects.length === 0 ? (
        <Empty description="暂无项目，请先创建" style={{ marginTop: 48 }} />
      ) : (
        <>
          {/* Desktop/Tablet View - Card Grid */}
          <div className="hidden tablet:block">
            <motion.div variants={containerVariants} initial="hidden" animate="visible">
              {Object.entries(groupedProjects).map(([status, list]) => {
                const meta = projectStatusMeta[status] ?? projectStatusMeta.unknown;
                return (
                  <div key={status} className="space-y-3 mb-8">
                    <Space align="center" size={8}>
                      <Badge color={meta.ribbon} />
                      <Text strong>{meta.label}</Text>
                      <Text type="secondary">{list.length} 个项目</Text>
                    </Space>
                    <Row gutter={[16, 16]}>
                      {list.map((project) => (
                        <Col key={project.id} xs={24} md={12} xl={8}>
                          <motion.div variants={itemVariants}>
                            <Badge.Ribbon text={meta.label} color={meta.ribbon}>
                              <Card
                                className="h-full shadow-sm hover:shadow-xl transition-all duration-300"
                                onClick={() => navigate(`/projects/${project.id}/overview`)}
                                hoverable
                              >
                                <Space direction="vertical" size="large" className="w-full">
                                  <div>
                                    <Space align="center" size={12} className="w-full justify-between">
                                      <Title level={4} className="!mb-1">{project.title || '未命名项目'}</Title>
                                      <Tooltip title="配置项目">
                                        <Button
                                          type="text"
                                          icon={<SettingOutlined />}
                                          onClick={(event) => {
                                            event.stopPropagation();
                                            navigate(`/projects/${project.id}/settings`);
                                          }}
                                        />
                                      </Tooltip>
                                    </Space>
                                    {project.description && (
                                      <Paragraph className="!mb-0 text-slate-500" ellipsis={{ rows: 2 }}>
                                        {project.description}
                                      </Paragraph>
                                    )}
                                  </div>

                                  <div className="grid grid-cols-2 gap-12">
                                    <div>
                                      <Text type="secondary" className="block text-xs">文献数量</Text>
                                      <Text strong className="text-lg">{project.literature_count ?? 0}</Text>
                                    </div>
                                    <div>
                                      <Text type="secondary" className="block text-xs">研究进度</Text>
                                      <Text strong className="text-lg">{project.progress_percentage ?? 0}%</Text>
                                    </div>
                                  </div>

                                  <Divider className="my-2" />
                                  <Space size={6} wrap>
                                    <Tag color={meta.color}>{meta.label}</Tag>
                                    {(project.keywords ?? []).slice(0, 3).map((keyword) => (
                                      <Tag key={keyword}>{keyword}</Tag>
                                    ))}
                                    {(project.keywords?.length ?? 0) > 3 && (
                                      <Tag>+{(project.keywords?.length ?? 0) - 3}</Tag>
                                    )}
                                  </Space>

                                  <div className="flex items-center justify-between text-xs text-slate-400">
                                    <span>创建时间：{new Date(project.created_at).toLocaleDateString()}</span>
                                    {project.updated_at && <span>最近更新：{new Date(project.updated_at).toLocaleDateString()}</span>}
                                  </div>

                                  <Space wrap>
                                    <Button type="primary" onClick={(event) => {
                                      event.stopPropagation();
                                      navigate(`/projects/${project.id}/workspace`);
                                    }}>
                                      打开工作台
                                    </Button>
                                    <Button onClick={(event) => {
                                      event.stopPropagation();
                                      navigate(`/projects/${project.id}/literature`);
                                    }}>查看文献</Button>
                                    <Button onClick={(event) => {
                                      event.stopPropagation();
                                      navigate(`/projects/${project.id}/tasks`);
                                    }}>任务面板</Button>
                                  </Space>
                                </Space>
                              </Card>
                            </Badge.Ribbon>
                          </motion.div>
                        </Col>
                      ))}
                    </Row>
                  </div>
                );
              })}
            </motion.div>
          </div>

          {/* Mobile View - Vertical Step Timeline */}
          <div className="block tablet:hidden">
            <motion.div
              variants={containerVariants}
              initial="hidden"
              animate="visible"
              className="bg-white rounded-lg p-4 shadow-sm"
            >
              <Title level={4} className="mb-4 text-center">项目时间线</Title>

              <Steps
                direction="vertical"
                size="small"
                className={styles['mobile-project-steps']}
              >
                {projects
                  .sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime())
                  .map((project) => {
                    const meta = projectStatusMeta[project.status ?? 'unknown'] ?? projectStatusMeta.unknown;
                    return (
                      <Step
                        key={project.id}
                        status={getStepStatus(project.status ?? 'unknown')}
                        icon={getStepIcon(project.status ?? 'unknown')}
                        title={
                          <div className="flex flex-col gap-1">
                            <span className="font-medium text-base text-gray-900">
                              {project.title || '未命名项目'}
                            </span>
                            <div className="flex items-center gap-2">
                              <Tag color={meta.color}>{meta.label}</Tag>
                              <Text type="secondary" className="text-xs">
                                {project.literature_count ?? 0} 文献
                              </Text>
                              <Text type="secondary" className="text-xs">
                                {project.progress_percentage ?? 0}% 进度
                              </Text>
                            </div>
                          </div>
                        }
                        description={
                          <div className="space-y-3 pt-2">
                            {project.description && (
                              <Text type="secondary" className="text-sm block">
                                {project.description.length > 60
                                  ? `${project.description.slice(0, 60)}...`
                                  : project.description}
                              </Text>
                            )}

                            {/* Mobile Action Buttons */}
                            <div className="flex flex-wrap gap-2">
                              <Button
                                type="primary"
                                size="small"
                                className="flex-1 min-w-0"
                                onClick={() => navigate(`/projects/${project.id}/workspace`)}
                              >
                                工作台
                              </Button>
                              <Button
                                size="small"
                                onClick={() => navigate(`/projects/${project.id}/literature`)}
                              >
                                文献
                              </Button>
                              <Button
                                size="small"
                                onClick={() => navigate(`/projects/${project.id}/tasks`)}
                              >
                                任务
                              </Button>
                              <Button
                                size="small"
                                icon={<SettingOutlined />}
                                onClick={() => navigate(`/projects/${project.id}/settings`)}
                              />
                            </div>

                            {/* Keywords */}
                            {(project.keywords ?? []).length > 0 && (
                              <div className="flex flex-wrap gap-1">
                                {(project.keywords ?? []).slice(0, 3).map((keyword) => (
                                  <Tag key={keyword}>{keyword}</Tag>
                                ))}
                                {(project.keywords?.length ?? 0) > 3 && (
                                  <Tag>+{(project.keywords?.length ?? 0) - 3}</Tag>
                                )}
                              </div>
                            )}

                            <Text type="secondary" className="text-xs">
                              创建于 {new Date(project.created_at).toLocaleDateString()}
                            </Text>
                          </div>
                        }
                      />
                    );
                  })}
              </Steps>
            </motion.div>
          </div>
        </>
      )}

      <Modal
        title="创建新项目"
        open={createModalOpen}
        onCancel={() => {
          setCreateModalOpen(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        okText="创建"
        cancelText="取消"
        destroyOnClose
      >
        <Form form={form} layout="vertical" onFinish={handleCreateProject}>
          <Form.Item
            label="项目名称"
            name="name"
            rules={[{ required: true, message: '请输入项目名称' }]}
          >
            <Input placeholder="例如：高性能钙钛矿太阳能电池" />
          </Form.Item>
          <Form.Item label="项目简介" name="description">
            <Input.TextArea
              placeholder="描述项目目标、研究范围或待解决的问题"
              autoSize={{ minRows: 3, maxRows: 5 }}
            />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default ProjectListPage;
