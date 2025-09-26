import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  Button,
  Card,
  Col,
  Divider,
  Form,
  Input,
  List,
  Progress,
  Row,
  Skeleton,
  Space,
  Statistic,
  Tag,
  Typography,
  message,
} from 'antd';
import {
  EditOutlined,
  LockOutlined,
  MailOutlined,
  ReadOutlined,
  RocketOutlined,
  TeamOutlined,
  FileTextOutlined,
} from '@ant-design/icons';
import {
  userAPI,
  type UpdateProfilePayload,
  type UpdatePasswordPayload,
} from '@/services/api/user';
import { useSystemStore } from '@/stores/system-store';
import type { UsageStatistics, UserProfile } from '@/types/user';
import { ActivityLog } from '@/components/profile/activity-log';
import { NotificationCenter } from '@/components/profile/notification-center';
import { AvatarUpload } from '@/components/profile/avatar-upload';

const { Title, Text, Paragraph } = Typography;

const membershipTagColor: Record<string, string> = {
  free: 'default',
  premium: 'gold',
  enterprise: 'purple',
};

const safeField = (value?: string | null) => value ?? '';

export const PersonalCenterPage = () => {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { profile, setProfile } = useSystemStore();
  const [profileForm] = Form.useForm();
  const [passwordForm] = Form.useForm();

  const profileQuery = useQuery<UserProfile>({
    queryKey: ['user-profile'],
    queryFn: () => userAPI.getProfile(),
    placeholderData: profile ?? undefined,
  });

  const usageQuery = useQuery<UsageStatistics>({
    queryKey: ['user-usage-stats'],
    queryFn: () => userAPI.getUsageStatistics(),
    staleTime: 30_000,
  });

  useEffect(() => {
    if (profileQuery.data) {
      setProfile(profileQuery.data);
      profileForm.setFieldsValue({
        full_name: safeField(profileQuery.data.full_name),
        institution: safeField(profileQuery.data.institution),
        research_field: safeField(profileQuery.data.research_field),
      });
    }
  }, [profileQuery.data, profileForm, setProfile]);

  const updateProfileMutation = useMutation({
    mutationFn: (payload: UpdateProfilePayload) => userAPI.updateProfile(payload),
    onSuccess: async (result) => {
      void message.success(result.message || '资料已更新');
      await queryClient.invalidateQueries({ queryKey: ['user-profile'] });
    },
    onError: (error: unknown) => {
      console.error(error);
      void message.error('更新资料失败，请稍后再试');
    },
  });

  const updatePasswordMutation = useMutation({
    mutationFn: (payload: UpdatePasswordPayload) => userAPI.updatePassword(payload),
    onSuccess: (result) => {
      void message.success(result.message || '密码已更新');
      passwordForm.resetFields();
    },
    onError: (error: unknown) => {
      console.error(error);
      void message.error('修改密码失败，请检查当前密码是否正确');
    },
  });

  const handleUpdateProfile = (values: { full_name?: string; institution?: string; research_field?: string }) => {
    const payload: UpdateProfilePayload = {
      full_name: values.full_name?.trim() || undefined,
      institution: values.institution?.trim() || undefined,
      research_field: values.research_field?.trim() || undefined,
    };
    updateProfileMutation.mutate(payload);
  };

  const handleUpdatePassword = (values: { current_password: string; new_password: string; confirm_password: string }) => {
    if (values.new_password !== values.confirm_password) {
      void message.warning('两次输入的新密码不一致');
      return;
    }
    const payload: UpdatePasswordPayload = {
      current_password: values.current_password,
      new_password: values.new_password,
    };
    updatePasswordMutation.mutate(payload);
  };

  const membershipType = profileQuery.data?.membership?.membership_type ?? 'free';
  const usage = usageQuery.data;

  return (
    <div className="space-y-6">
      <Card className="bg-slate-900/60 border-slate-700">
        {profileQuery.isLoading ? (
          <Skeleton avatar paragraph={{ rows: 2 }} active />
        ) : profileQuery.data ? (
          <Row gutter={[24, 24]} align="middle">
            <Col xs={24} md={6} lg={4} className="flex justify-center">
              <AvatarUpload
                currentAvatarUrl={profileQuery.data.avatar_url}
                size={96}
                showUploadButton={false}
              />
            </Col>
            <Col xs={24} md={18} lg={20}>
              <Space direction="vertical" size={8} className="w-full">
                <Title level={3} className="!text-white !mb-0">
                  {profileQuery.data.full_name || profileQuery.data.username}
                </Title>
                <Space size={8} wrap>
                  <Tag color={membershipTagColor[membershipType] ?? 'default'}>
                    {membershipType === 'free' ? '基础版' : membershipType === 'premium' ? '专业版' : '企业版'}
                  </Tag>
                  <Tag icon={<MailOutlined />}>
                    {profileQuery.data.email}
                  </Tag>
                  {profileQuery.data.institution && <Tag>{profileQuery.data.institution}</Tag>}
                </Space>
                <Paragraph className="!text-slate-300 !mb-0">
                  欢迎回来！在这里可以管理个人资料、账号安全设置，并查看自己的平台使用情况。
                </Paragraph>
                <Space wrap>
                  <Button icon={<RocketOutlined />} type="primary" onClick={() => navigate('/projects')}>
                    前往项目中心
                  </Button>
                  <Button icon={<ReadOutlined />} onClick={() => navigate('/library')}>
                    打开文献库
                  </Button>
                </Space>
              </Space>
            </Col>
          </Row>
        ) : (
          <Text type="secondary">尚未加载到用户信息</Text>
        )}
      </Card>

      <Row gutter={[24, 24]}>
        <Col xs={24} lg={16}>
          <Card
            title={
              <Space size={8}>
                <EditOutlined />
                <span>头像管理</span>
              </Space>
            }
            className="mb-6 bg-slate-900/40 border-slate-700"
          >
            <div className="flex justify-center">
              <AvatarUpload
                currentAvatarUrl={profileQuery.data?.avatar_url}
                size={120}
                showUploadButton={true}
              />
            </div>
          </Card>

          <Card
            title={
              <Space size={8}>
                <EditOutlined />
                <span>基本资料</span>
              </Space>
            }
            className="bg-slate-900/40 border-slate-700"
          >
            <Form
              form={profileForm}
              layout="vertical"
              onFinish={handleUpdateProfile}
              disabled={profileQuery.isLoading}
            >
              <Row gutter={16}>
                <Col xs={24} md={12}>
                  <Form.Item name="full_name" label="姓名">
                    <Input placeholder="填写真实姓名" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item name="institution" label="所属机构">
                    <Input placeholder="所在学校或研究机构" />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item name="research_field" label="研究领域">
                <Input.TextArea placeholder="例如：计算机视觉、药物设计" autoSize={{ minRows: 2, maxRows: 4 }} />
              </Form.Item>
              <Form.Item>
                <Button type="primary" htmlType="submit" loading={updateProfileMutation.isPending}>
                  保存资料
                </Button>
              </Form.Item>
            </Form>
          </Card>

          <Card
            title={
              <Space size={8}>
                <LockOutlined />
                <span>账号安全</span>
              </Space>
            }
            className="mt-6 bg-slate-900/40 border-slate-700"
          >
            <Form form={passwordForm} layout="vertical" onFinish={handleUpdatePassword}>
              <Form.Item
                name="current_password"
                label="当前密码"
                rules={[{ required: true, message: '请输入当前密码' }]}
              >
                <Input.Password placeholder="请输入当前密码" autoComplete="current-password" />
              </Form.Item>
              <Row gutter={16}>
                <Col xs={24} md={12}>
                  <Form.Item
                    name="new_password"
                    label="新密码"
                    rules={[{ required: true, message: '请输入新密码' }]}
                  >
                    <Input.Password placeholder="至少 8 位字符" autoComplete="new-password" />
                  </Form.Item>
                </Col>
                <Col xs={24} md={12}>
                  <Form.Item
                    name="confirm_password"
                    label="确认新密码"
                    dependencies={['new_password']}
                    rules={[{ required: true, message: '请再次输入新密码' }]}
                  >
                    <Input.Password placeholder="再次输入新密码" autoComplete="new-password" />
                  </Form.Item>
                </Col>
              </Row>
              <Form.Item>
                <Space>
                  <Button type="primary" htmlType="submit" loading={updatePasswordMutation.isPending}>
                    修改密码
                  </Button>
                  <Button
                    onClick={() => passwordForm.resetFields()}
                    disabled={updatePasswordMutation.isPending}
                  >
                    重置
                  </Button>
                </Space>
              </Form.Item>
            </Form>
          </Card>
        </Col>

        <Col xs={24} lg={8}>
          <Space direction="vertical" size={24} className="w-full">
            <Card className="bg-slate-900/40 border-slate-700" title="使用概览">
              {usageQuery.isLoading ? (
                <Skeleton active paragraph={{ rows: 3 }} />
              ) : usage ? (
                <Space direction="vertical" size={16} className="w-full">
                  <Statistic
                    title="总项目数"
                    value={usage.usage.total_projects ?? 0}
                    prefix={<RocketOutlined />}
                  />
                  <Statistic
                    title="累积文献"
                    value={usage.usage.total_literature ?? 0}
                    prefix={<FileTextOutlined />}
                  />
                  <Statistic
                    title="完成任务"
                    value={usage.usage.completed_tasks ?? 0}
                    prefix={<TeamOutlined />}
                  />
                  <Divider className="my-2" />
                  <div className="space-y-3">
                    <Text type="secondary">额度使用情况</Text>
                    {Object.entries(usage.usage_percentage).map(([key, percent]) => (
                      <div key={key} className="space-y-1">
                        <div className="flex items-center justify-between text-xs text-slate-400">
                          <span>{key}</span>
                          <span>{Math.round(percent)}%</span>
                        </div>
                        <Progress
                          percent={Math.round(percent)}
                          size="small"
                          showInfo={false}
                        />
                      </div>
                    ))}
                  </div>
                </Space>
              ) : (
                <Text type="secondary">暂未获取到使用数据</Text>
              )}
            </Card>

            <Card className="bg-slate-900/40 border-slate-700" title="快捷操作">
              <List
                dataSource={[
                  {
                    key: 'projects',
                    title: '项目列表',
                    description: '查看所有正在进行或已归档的项目，并快速切换上下文。',
                    action: () => navigate('/projects'),
                  },
                  {
                    key: 'library',
                    title: '文献库',
                    description: '管理上传的 PDF、研究资料或检索到的 Semantic Scholar 文献。',
                    action: () => navigate('/library'),
                  },
                  {
                    key: 'tasks',
                    title: '任务看板',
                    description: '查看自动化任务的执行状态、失败重试与费用估算。',
                    action: () => navigate('/tasks'),
                  },
                ]}
                renderItem={(item) => (
                  <List.Item
                    key={item.key}
                    actions={[
                      <Button key={`${item.key}-action`} type="link" onClick={item.action}>
                        前往
                      </Button>,
                    ]}
                  >
                    <List.Item.Meta title={item.title} description={item.description} />
                  </List.Item>
                )}
              />
            </Card>

            <ActivityLog />

            <NotificationCenter />
          </Space>
        </Col>
      </Row>
    </div>
  );
};

export default PersonalCenterPage;
