import { useEffect, useMemo, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { motion } from 'framer-motion';
import { Tabs, Form, Input, Button, Typography, Checkbox, message, Space } from 'antd';
import { LockOutlined, MailOutlined, UserOutlined } from '@ant-design/icons';
import styles from './auth-landing.module.css';
import { authAPI } from '@/services/api/auth';
import { fetchUserProfile } from '@/services/api/user';
import { useAuthStore } from '@/stores/auth-store';
import { useSystemStore } from '@/stores/system-store';
import { UnifiedBackground } from '@/components/layout/UnifiedBackground';

const { Title, Text } = Typography;

type AuthTab = 'login' | 'register';

interface LoginValues {
  email: string;
  password: string;
  remember?: boolean;
}

interface RegisterValues {
  email: string;
  password: string;
  confirm_password: string;
  username: string;
  full_name?: string;
}

export default function AuthLanding() {
  const navigate = useNavigate();
  const location = useLocation();
  const { accessToken, setCredentials, clear } = useAuthStore();
  const { setProfile } = useSystemStore();

  const [activeTab, setActiveTab] = useState<AuthTab>('login');
  const [loading, setLoading] = useState(false);
  const [loginForm] = Form.useForm<LoginValues>();
  const [registerForm] = Form.useForm<RegisterValues>();

  const redirectPath = useMemo(() => {
    const fromState = location.state as { from?: string } | undefined;
    return fromState?.from && fromState.from !== '/auth' ? fromState.from : '/';
  }, [location.state]);

  useEffect(() => {
    if (accessToken) {
      navigate('/', { replace: true });
    }
  }, [accessToken, navigate]);

  const handleAuthSuccess = async (token: string, userId: number) => {
    setCredentials(token, userId);
    try {
      const profile = await fetchUserProfile();
      setProfile(profile);
    } catch (error) {
      console.warn('Failed to fetch profile after login', error);
    }
    void message.success('登录成功');
    navigate(redirectPath, { replace: true });
  };

  const handleLogin = async (values: LoginValues) => {
    setLoading(true);
    try {
      const response = await authAPI.login({
        email: values.email,
        password: values.password,
      });
      await handleAuthSuccess(response.access_token, response.user_info.id);
    } catch (error) {
      void message.error(
        error instanceof Error && error.message ? error.message : '登录失败，请检查邮箱和密码'
      );
      clear();
    } finally {
      setLoading(false);
    }
  };

  const handleRegister = async (values: RegisterValues) => {
    if (values.password !== values.confirm_password) {
      void message.warning('两次输入的密码不一致');
      return;
    }
    setLoading(true);
    try {
      const response = await authAPI.register({
        email: values.email,
        password: values.password,
        username: values.username,
        full_name: values.full_name,
      });
      await handleAuthSuccess(response.access_token, response.user_info.id);
    } catch (error) {
      void message.error(
        error instanceof Error && error.message ? error.message : '注册失败，请稍后重试'
      );
      clear();
    } finally {
      setLoading(false);
    }
  };

  return (
    <UnifiedBackground variant="aurora">
      <div className="grid place-items-center min-h-screen p-6 md:p-12">
        <motion.div
          className={styles.card}
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.28 }}
        >
          <div className={styles.header}>
            <Title level={3} className={styles.title}>欢迎使用 VibeResearch</Title>
            <Text className={styles.subtitle}>登录或注册，开始构建深度研究工作流</Text>
          </div>

          <Tabs
            activeKey={activeTab}
            onChange={(key) => setActiveTab(key as AuthTab)}
            items={[
              { key: 'login', label: '登录账号' },
              { key: 'register', label: '创建账号' },
            ]}
          />

          {activeTab === 'login' ? (
            <Form<LoginValues>
              form={loginForm}
              layout="vertical"
              onFinish={handleLogin}
            requiredMark={false}
            initialValues={{ remember: true }}
          >
            <Form.Item
              name="email"
              label="邮箱"
              rules={[{ required: true, message: '请输入邮箱' }, { type: 'email', message: '邮箱格式不正确' }]}
            >
              <Input
                prefix={<MailOutlined />}
                placeholder="you@example.com"
                size="large"
                autoComplete="email"
                data-testid="login-email"
              />
            </Form.Item>

            <Form.Item
              name="password"
              label="密码"
              rules={[{ required: true, message: '请输入密码' }]}
            >
              <Input.Password
                prefix={<LockOutlined />}
                placeholder="请输入密码"
                size="large"
                autoComplete="current-password"
                data-testid="login-password"
              />
            </Form.Item>

            <Form.Item name="remember" valuePropName="checked">
              <Checkbox>记住我</Checkbox>
            </Form.Item>

            <Button type="primary" htmlType="submit" size="large" block loading={loading} data-testid="login-submit">
              登录
            </Button>
          </Form>
        ) : (
          <Form<RegisterValues>
            form={registerForm}
            layout="vertical"
            onFinish={handleRegister}
            requiredMark={false}
          >
            <Space direction="vertical" size="middle" className={styles.formGroup}>
              <Form.Item
                name="email"
                label="邮箱"
                rules={[{ required: true, message: '请输入邮箱' }, { type: 'email', message: '邮箱格式不正确' }]}
              >
                <Input prefix={<MailOutlined />} placeholder="you@example.com" size="large" autoComplete="email" />
              </Form.Item>

              <Form.Item
                name="username"
                label="用户名"
                rules={[{ required: true, message: '请输入用户名' }]}
              >
                <Input prefix={<UserOutlined />} placeholder="研究者昵称" size="large" autoComplete="username" />
              </Form.Item>

              <Form.Item name="full_name" label="姓名（可选）">
                <Input prefix={<UserOutlined />} placeholder="真实姓名" size="large" autoComplete="name" />
              </Form.Item>

              <Form.Item
                name="password"
                label="密码"
                rules={[{ required: true, message: '请输入密码' }, { min: 8, message: '密码至少 8 位' }]}
              >
                <Input.Password
                  prefix={<LockOutlined />}
                  placeholder="设置登录密码"
                  size="large"
                  autoComplete="new-password"
                />
              </Form.Item>

              <Form.Item
                name="confirm_password"
                label="确认密码"
                dependencies={["password"]}
                rules={[{ required: true, message: '请再次输入密码' }]}
              >
                <Input.Password
                  prefix={<LockOutlined />}
                  placeholder="再次输入密码"
                  size="large"
                  autoComplete="new-password"
                />
              </Form.Item>
            </Space>

            <Button type="primary" htmlType="submit" size="large" block loading={loading}>
              注册并登录
            </Button>
          </Form>
        )}

          <div className={styles.footerNote}>
            <Text type="secondary">需要返回首页？</Text>
            <Button type="link" onClick={() => navigate('/')}>
              前往仪表盘
            </Button>
          </div>
        </motion.div>
      </div>
    </UnifiedBackground>
  );
}
