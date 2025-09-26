import { useParams } from 'react-router-dom';
import { Card, Form, Input, Space, Typography, Button, message } from 'antd';
import { useEffect } from 'react';
import { projectAPI } from '@/services/api/project';
import { useAppStore } from '@/stores/app.store';

const { Title, Text } = Typography;

export const ProjectSettingsPage = () => {
  const { projectId } = useParams();
  const numericProjectId = Number(projectId);
  const [form] = Form.useForm();
  const currentProject = useAppStore((state) => state.currentProject);

  useEffect(() => {
    if (!Number.isNaN(numericProjectId)) {
      if (currentProject && currentProject.id === numericProjectId) {
        form.setFieldsValue({
          name: currentProject.title,
          description: currentProject.description,
        });
      } else {
        void projectAPI.getProject(numericProjectId).then((project) => {
          form.setFieldsValue({
            name: project.title,
            description: project.description,
          });
        });
      }
    }
  }, [numericProjectId, currentProject, form]);

  if (!projectId || Number.isNaN(numericProjectId)) {
    return null;
  }

  const handleSubmit = async (values: { name: string; description?: string }) => {
    try {
      await projectAPI.updateProject(numericProjectId, {
        name: values.name,
        description: values.description,
        research_direction: '',
        keywords: [],
        research_categories: [],
      });

      // 回写 Zustand 状态
      const setCurrentProject = useAppStore.getState().setCurrentProject;
      const updateAvailableProject = useAppStore.getState().updateAvailableProject;

      if (currentProject && currentProject.id === numericProjectId) {
        setCurrentProject({
          ...currentProject,
          title: values.name,
          description: values.description,
        });
      }

      // 更新可用项目列表中的项目
      updateAvailableProject(numericProjectId, {
        title: values.name,
        description: values.description,
      });

      void message.success('项目设置已更新');
    } catch (error) {
      console.error('Failed to update project', error);
      void message.error('更新项目设置失败');
    }
  };

  return (
    <Space direction="vertical" size={16} className="w-full">
      <Title level={3}>项目设置</Title>
      <Card className="shadow-sm border-0">
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            label="项目名称"
            name="name"
            rules={[{ required: true, message: '请输入项目名称' }]}
          >
            <Input placeholder="项目名称" />
          </Form.Item>
          <Form.Item label="项目描述" name="description">
            <Input.TextArea placeholder="项目描述" autoSize={{ minRows: 3, maxRows: 6 }} />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit">
              保存设置
            </Button>
          </Form.Item>
        </Form>
      </Card>
      <Text type="secondary">更多高级设置（权限、通知、自动化流程）将陆续开放。</Text>
    </Space>
  );
};

export default ProjectSettingsPage;
