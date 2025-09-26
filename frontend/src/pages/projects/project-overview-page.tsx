import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import {
  Button,
  Card,
  Col,
  Divider,
  Row,
  Space,
  Statistic,
  Tag,
  Typography,
} from 'antd';
import {
  DeploymentUnitOutlined,
  FileTextOutlined,
  HourglassOutlined,
  SettingOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import { motion } from 'framer-motion';
import { projectAPI, type Project } from '@/services/api/project';
import { useAppStore } from '@/stores/app.store';

const { Title, Text, Paragraph } = Typography;

export const ProjectOverviewPage = () => {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const numericProjectId = Number(projectId);
  const { currentProject, setCurrentProject } = useAppStore((state) => ({
    currentProject: state.currentProject,
    setCurrentProject: state.setCurrentProject,
  }));
  const [project, setProject] = useState<Project | null>(() => {
    if (!currentProject) {
      return null;
    }

    return {
      id: currentProject.id,
      name: currentProject.title,
      title: currentProject.title,
      description: currentProject.description,
      created_at: currentProject.created_at,
      updated_at: currentProject.updated_at,
      research_direction: undefined,
      research_categories: undefined,
      keywords: [],
      status: 'unknown',
      literature_sources: undefined,
      max_literature_count: 0,
      structure_template: undefined,
      extraction_prompts: undefined,
      owner_id: 0,
      literature_count: 0,
      progress_percentage: 0,
    };
  });

  useEffect(() => {
    if (!Number.isNaN(numericProjectId)) {
      projectAPI.getProject(numericProjectId).then((data) => {
        setProject(data);
        setCurrentProject({
          id: data.id,
          title: data.title,
          description: data.description ?? undefined,
          created_at: data.created_at,
          updated_at: data.updated_at ?? undefined,
        });
      }).catch((error) => {
        console.error('Failed to load project overview', error);
      });
    }
  }, [numericProjectId, setCurrentProject]);

  if (!project) {
    return null;
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.25 }}
      className="space-y-6"
    >
      <Card className="shadow-sm border-0">
        <Space direction="vertical" size={8} className="w-full">
          <Space align="center" size={12} className="w-full justify-between">
            <div>
              <Title level={3} className="!mb-0">{project.title}</Title>
              {project.description && (
                <Paragraph className="!mb-0 text-slate-500" ellipsis={{ rows: 2 }}>
                  {project.description}
                </Paragraph>
              )}
            </div>
            <Button type="text" icon={<SettingOutlined />} onClick={() => navigate('settings')}>
              项目设置
            </Button>
          </Space>
          <Divider className="my-2" />
          <Row gutter={[16, 16]}>
            <Col xs={12} md={6}>
              <Statistic title="文献数量" value={project.literature_count ?? 0} prefix={<FileTextOutlined />} />
            </Col>
            <Col xs={12} md={6}>
              <Statistic title="研究进度" value={project.progress_percentage ?? 0} suffix="%" prefix={<DeploymentUnitOutlined />} />
            </Col>
            <Col xs={12} md={6}>
              <Statistic title="最大文献预算" value={project.max_literature_count ?? 0} prefix={<HourglassOutlined />} />
            </Col>
            <Col xs={12} md={6}>
              <Statistic title="项目状态" valueRender={() => <Tag color="processing">{project.status}</Tag>} prefix={<ThunderboltOutlined />} />
            </Col>
          </Row>
        </Space>
      </Card>

      <Row gutter={[16, 16]}>
        <Col xs={24} lg={12}>
          <Card title="快捷操作" className="shadow-sm border-0">
            <Space direction="vertical" size={12} className="w-full">
              <Button type="primary" onClick={() => navigate(`/projects/${project.id}/workspace`)}>
                打开研究工作台
              </Button>
              <Button onClick={() => navigate(`/projects/${project.id}/literature`)}>
                查看文献库
              </Button>
              <Button onClick={() => navigate(`/projects/${project.id}/tasks`)}>
                进入任务面板
              </Button>
            </Space>
          </Card>
        </Col>
        <Col xs={24} lg={12}>
          <Card title="项目信息" className="shadow-sm border-0">
            <Space direction="vertical" size={12} className="w-full text-sm text-slate-500">
              <div className="flex items-center justify-between">
                <Text type="secondary">创建时间</Text>
                <Text>{new Date(project.created_at).toLocaleString()}</Text>
              </div>
              {project.updated_at && (
                <div className="flex items-center justify-between">
                  <Text type="secondary">最近更新</Text>
                  <Text>{new Date(project.updated_at).toLocaleString()}</Text>
                </div>
              )}
              {!!project.keywords?.length && (
                <div>
                  <Text type="secondary">关键词</Text>
                  <Divider className="my-2" />
                  <Space wrap>
                    {project.keywords.map((keyword) => (
                      <Tag key={keyword}>{keyword}</Tag>
                    ))}
                  </Space>
                </div>
              )}
            </Space>
          </Card>
        </Col>
      </Row>
    </motion.div>
  );
};

export default ProjectOverviewPage;
