import React, { useState, useEffect, useCallback } from 'react';
import { Select, Space, Button, Modal, Form, Input, message } from 'antd';
import { PlusOutlined, FolderOutlined } from '@ant-design/icons';
import { projectAPI } from '@/services/api/project';
import type { Project as ApiProject } from '@/services/api/project';

export interface Project {
  id: number;
  title: string;
  description?: string;
  created_at: string;
  updated_at?: string;
}

interface ProjectSelectorProps {
  value?: number;
  onChange?: (projectId: number, project: Project) => void;
  style?: React.CSSProperties;
}

export const ProjectSelector: React.FC<ProjectSelectorProps> = ({
  value,
  onChange,
  style
}) => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(false);
  const [createModalVisible, setCreateModalVisible] = useState(false);
  const [form] = Form.useForm();

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    try {
      const apiProjects = await projectAPI.getProjects();
      const normalizedProjects: Project[] = apiProjects.map((project: ApiProject) => ({
        id: project.id,
        title: project.title,
        description: project.description ?? undefined,
        created_at: project.created_at,
        updated_at: project.updated_at ?? undefined,
      }));

      setProjects(normalizedProjects);

      if (!value && normalizedProjects.length > 0 && onChange) {
        onChange(normalizedProjects[0].id, normalizedProjects[0]);
      }
    } catch (error) {
      console.error('Failed to fetch projects:', error);
      void message.error('获取项目列表失败');
    } finally {
      setLoading(false);
    }
  }, [onChange, value]);

  useEffect(() => {
    void fetchProjects();
  }, [fetchProjects]);

  const handleProjectChange = (projectId: number) => {
    const project = projects.find(p => p.id === projectId);
    if (project && onChange) {
      onChange(projectId, project);
    }
  };

  const handleCreateProject = async (values: { name: string; description?: string }) => {
    try {
      const created = await projectAPI.createEmptyProject({
        name: values.name,
        description: values.description,
      });

      const normalizedProject: Project = {
        id: created.id,
        title: created.title,
        description: created.description ?? undefined,
        created_at: created.created_at,
        updated_at: created.updated_at ?? undefined,
      };

      setProjects(prev => [...prev, normalizedProject]);
      setCreateModalVisible(false);
      form.resetFields();
      void message.success('项目创建成功');

      if (onChange) {
        onChange(normalizedProject.id, normalizedProject);
      }
    } catch (error) {
      console.error('Failed to create project:', error);
      void message.error('项目创建失败');
    }
  };

  return (
    <>
      <Space.Compact style={style}>
        <Select
          value={value}
          onChange={handleProjectChange}
          placeholder="选择项目"
          loading={loading}
          style={{ minWidth: 200 }}
          optionLabelProp="label"
        >
          {projects.map(project => (
            <Select.Option
              key={project.id}
              value={project.id}
              label={project.title}
            >
              <Space>
                <FolderOutlined />
                <span>{project.title}</span>
                {project.description && (
                  <span style={{ color: '#666', fontSize: '12px' }}>
                    {project.description.slice(0, 30)}...
                  </span>
                )}
              </Space>
            </Select.Option>
          ))}
        </Select>
        <Button
          icon={<PlusOutlined />}
          onClick={() => setCreateModalVisible(true)}
          type="dashed"
        >
          新建项目
        </Button>
      </Space.Compact>

      <Modal
        title="创建新项目"
        open={createModalVisible}
        onCancel={() => {
          setCreateModalVisible(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreateProject}
        >
          <Form.Item
            name="name"
            label="项目名称"
            rules={[{ required: true, message: '请输入项目名称' }]}
          >
            <Input placeholder="输入项目名称" />
          </Form.Item>
          <Form.Item
            name="description"
            label="项目描述"
          >
            <Input.TextArea
              placeholder="输入项目描述（可选）"
              rows={3}
            />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};
