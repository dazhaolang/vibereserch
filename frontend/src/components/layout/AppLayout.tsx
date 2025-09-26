import React, { useMemo, useState } from 'react';
import {
  Layout,
  Menu,
  Avatar,
  Dropdown,
  Badge,
  Button,
  Typography,
  Switch,
  Tooltip,
  Drawer,
  Grid,
  Space,
  Tag,
  message,
} from 'antd';
import type { MenuProps } from 'antd';
import { Outlet, useNavigate, useLocation, useMatch } from 'react-router-dom';
import {
  DashboardOutlined,
  ExperimentOutlined,
  BookOutlined,
  BarChartOutlined,
  SettingOutlined,
  BellOutlined,
  UserOutlined,
  LogoutOutlined,
  MenuFoldOutlined,
  MenuUnfoldOutlined,
  MoonOutlined,
  SunOutlined,
  SearchOutlined,
  QuestionCircleOutlined,
  RocketOutlined,
  FolderOutlined,
} from '@ant-design/icons';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '@/stores/app.store';
import { useSystemStore } from '@/stores/system-store';
import { useAuthStore } from '@/stores/auth-store';
import { authAPI } from '@/services/api/auth';
import { TouchButton } from '@/components/common/TouchButton';
import { TouchInput } from '@/components/common/TouchInput';

const { Header, Sider, Content, Footer } = Layout;
const { Text } = Typography;

interface NavItem {
  key: string;
  icon: React.ReactNode;
  label: string;
  path: string;
  badge?: number;
}

const mainNavItems: NavItem[] = [
  { key: 'dashboard', icon: <DashboardOutlined />, label: '仪表盘', path: '/dashboard' },
  { key: 'projects', icon: <FolderOutlined />, label: '项目', path: '/projects' },
  { key: 'library', icon: <BookOutlined />, label: '文献库', path: '/library', badge: 128 },
  { key: 'research', icon: <ExperimentOutlined />, label: '研究工作台', path: '/research' },
  { key: 'tasks', icon: <BarChartOutlined />, label: '任务中心', path: '/tasks' },
  { key: 'profile', icon: <UserOutlined />, label: '个人中心', path: '/profile' },
  { key: 'settings', icon: <SettingOutlined />, label: '设置', path: '/settings' },
];

const createProjectNavItems = (projectId: string): NavItem[] => [
  { key: 'project-overview', icon: <DashboardOutlined />, label: '项目总览', path: `/projects/${projectId}/overview` },
  { key: 'project-workspace', icon: <ExperimentOutlined />, label: '研究工作台', path: `/projects/${projectId}/workspace` },
  { key: 'project-literature', icon: <BookOutlined />, label: '文献库', path: `/projects/${projectId}/literature` },
  { key: 'project-tasks', icon: <BarChartOutlined />, label: '任务管理', path: `/projects/${projectId}/tasks` },
  { key: 'project-settings', icon: <SettingOutlined />, label: '项目设置', path: `/projects/${projectId}/settings` },
];

export const AppLayout: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();
  const projectMatch = useMatch('/projects/:projectId/*');
  const projectId = projectMatch?.params.projectId ?? null;
  const currentProject = useAppStore((state) => state.currentProject);
  const clearAuth = useAuthStore((state) => state.clear);
  const setSystemProfile = useSystemStore((state) => state.setProfile);
  const [collapsed, setCollapsed] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const screens = Grid.useBreakpoint();

  const isMobile = useMemo(() => !screens.lg, [screens]);
  const isTablet = useMemo(() => screens.md && !screens.lg, [screens]);
  const isPhone = useMemo(() => !screens.md, [screens]);

  // Auto-collapse sidebar on tablet screens for better space utilization
  React.useEffect(() => {
    if (isTablet && !collapsed) {
      setCollapsed(true);
    } else if (!isMobile && !isTablet && collapsed) {
      setCollapsed(false);
    }
  }, [isTablet, isMobile, collapsed]);

  const navItems = useMemo(() => {
    if (projectId) {
      return createProjectNavItems(projectId);
    }
    return mainNavItems;
  }, [projectId]);

  const handleLogout = async () => {
    try {
      await authAPI.logout();
      void message.success('已退出登录');
    } catch (error) {
      console.warn('Logout failed', error);
      void message.info('已清理本地登录状态');
    } finally {
      clearAuth();
      setSystemProfile(null);
      navigate('/auth', { replace: true });
    }
  };

  const userMenuItems: MenuProps['items'] = [
    { key: 'profile', label: '个人中心', icon: <UserOutlined /> },
    { key: 'settings', label: '体验设置', icon: <SettingOutlined /> },
    { type: 'divider' },
    { key: 'help', label: '帮助中心', icon: <QuestionCircleOutlined /> },
    { key: 'logout', label: '退出登录', icon: <LogoutOutlined />, danger: true },
  ];

  const handleUserMenuClick: MenuProps['onClick'] = ({ key }) => {
    switch (key) {
      case 'profile':
        navigate('/profile');
        break;
      case 'settings':
        navigate('/settings');
        break;
      case 'help':
        navigate('/research');
        break;
      case 'logout':
        void handleLogout();
        break;
      default:
        break;
    }
  };

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    const item = navItems.find((nav) => nav.key === key);
    if (item) {
      navigate(item.path);
    }
    if (isMobile) {
      setMobileMenuOpen(false);
    }
  };

  const activeKey = useMemo(() => {
    const found = navItems.find((item) =>
      item.path === '/' ? location.pathname === '/' : location.pathname.startsWith(item.path)
    );
    return found ? found.key : navItems[0]?.key;
  }, [location.pathname, navItems]);

  const renderMenuItems = (items: NavItem[], showBadges = true) =>
    items.map((item) => ({
      key: item.key,
      icon: item.icon,
      label: (
        <div className="flex items-center justify-between">
          <span>{item.label}</span>
          {showBadges && item.badge !== undefined ? (
            <Badge count={item.badge} overflowCount={99} style={{ backgroundColor: '#52c41a' }} />
          ) : null}
        </div>
      ),
    }));

  const handleToggleMenu = () => {
    if (isMobile) {
      setMobileMenuOpen(true);
    } else {
      setCollapsed((prev) => !prev);
    }
  };

  const titleLabel = projectId && currentProject ? currentProject.title : 'VibeSearch';

  return (
    <Layout className="min-h-screen">
      {!isMobile && (
        <Sider
          trigger={null}
          collapsible
          collapsed={collapsed}
          breakpoint="lg"
          width={isTablet ? 200 : 240}
          collapsedWidth={isTablet ? 60 : 80}
          className="shadow-xl transition-all duration-300"
          style={{
            background: 'linear-gradient(180deg, #001529 0%, #002140 100%)',
            borderRight: '1px solid rgba(255, 255, 255, 0.1)'
          }}
        >
          <div className="h-16 flex items-center justify-center border-b border-gray-700 px-4">
            <motion.div
              animate={{ rotate: collapsed ? 360 : 0 }}
              transition={{ duration: 0.3 }}
              className="flex items-center gap-2"
            >
              <RocketOutlined className="text-3xl text-blue-400" />
              <AnimatePresence>
                {!collapsed && (
                  <motion.span
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    exit={{ opacity: 0, x: -20 }}
                    className="text-white font-bold text-lg"
                  >
                    {titleLabel}
                  </motion.span>
                )}
              </AnimatePresence>
            </motion.div>
          </div>

          <Menu
            theme="dark"
            mode="inline"
            selectedKeys={activeKey ? [activeKey] : []}
            onClick={handleMenuClick}
            className="mt-4"
            items={renderMenuItems(navItems, !collapsed)}
          />

          {projectId ? (
            <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-700">
              <Space direction="vertical" size={6}>
                <Text className="text-white text-sm">当前项目</Text>
                <Text className="text-slate-300 text-xs" ellipsis>
                  {currentProject?.description ?? '项目上下文工作台'}
                </Text>
                <Button type="dashed" onClick={() => navigate('/projects')} icon={<FolderOutlined />}>
                  返回项目列表
                </Button>
              </Space>
            </div>
          ) : (
            <div className="absolute bottom-0 left-0 right-0 p-4 border-t border-gray-700">
              <Avatar size="large" src="https://api.dicebear.com/7.x/avataaars/svg?seed=user" className="cursor-pointer" />
            </div>
          )}
        </Sider>
      )}

      <Layout>
        <Header
          className="bg-white/95 backdrop-blur-sm shadow-sm border-b border-neural-200 flex items-center justify-between transition-all duration-200"
          style={{
            height: isPhone ? 56 : 64,
            padding: isPhone ? '0 12px' : '0 16px 0 24px',
            borderBottom: '1px solid rgba(148, 163, 184, 0.2)'
          }}
        >
          <div className="flex items-center gap-3">
            <TouchButton
              type="text"
              icon={isMobile ? <MenuUnfoldOutlined /> : collapsed ? <MenuUnfoldOutlined /> : <MenuFoldOutlined />}
              onClick={handleToggleMenu}
              touchSize="medium"
              className="text-lg"
            />

            {isMobile ? (
              <div className="flex items-center gap-2">
                <RocketOutlined className="text-xl text-blue-500" />
                <Text className="font-semibold text-slate-700">{titleLabel}</Text>
              </div>
            ) : projectId ? (
              <Space size={8} className="text-slate-600">
                <Tag color="geekblue">项目模式</Tag>
                <Text>{currentProject?.title ?? '未命名项目'}</Text>
              </Space>
            ) : null}

            <div className={`ml-2 ${isPhone ? 'hidden' : isTablet ? 'w-48' : 'w-96'} transition-all duration-200`}>
              {!isPhone && (
                <TouchInput
                  placeholder="搜索文献、项目、任务..."
                  prefix={<SearchOutlined />}
                  variant="search"
                  allowClear
                />
              )}
            </div>
          </div>

          <div className={`flex items-center ${isPhone ? 'gap-2' : 'gap-3'}`}>
            {projectId && !isMobile && (
              <TouchButton
                onClick={() => navigate('/projects')}
                icon={<FolderOutlined />}
                touchSize={isTablet ? 'small' : 'medium'}
              >
                {isTablet ? '项目' : '项目列表'}
              </TouchButton>
            )}
            <Tooltip title={darkMode ? '切换到亮色模式' : '切换到暗色模式'}>
              <Switch
                checked={darkMode}
                onChange={setDarkMode}
                checkedChildren={<MoonOutlined />}
                unCheckedChildren={<SunOutlined />}
                className="touch-target"
                style={{
                  minWidth: isPhone ? 48 : 44,
                  height: isPhone ? 24 : 22
                }}
              />
            </Tooltip>
            <Badge count={5} size="small">
              <TouchButton
                type="text"
                icon={<BellOutlined />}
                touchSize="medium"
                className="text-lg"
              />
            </Badge>
            <Dropdown
              menu={{ items: userMenuItems, onClick: handleUserMenuClick }}
              placement="bottomRight"
            >
              <Avatar
                size={isMobile ? 32 : 36}
                src="https://api.dicebear.com/7.x/avataaars/svg?seed=user"
                className="cursor-pointer hover:shadow-lg transition-all"
              />
            </Dropdown>
          </div>
        </Header>

        <Content
          className="bg-gradient-to-br from-neural-50 via-neural-100 to-primary-50 transition-all duration-300"
          style={{
            padding: isPhone ? '12px 8px 16px' : isTablet ? '16px 12px 20px' : '24px 32px',
            minHeight: `calc(100vh - ${isPhone ? 56 : 64}px - 64px)` // header + footer height
          }}
        >
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.25 }}
            className="min-h-[calc(100vh-112px)]"
          >
            <Outlet />
          </motion.div>
        </Content>

        <Footer
          className="text-center text-neural-500 border-t border-neural-200 bg-white/80 backdrop-blur-sm transition-all duration-200"
          style={{
            fontSize: isPhone ? '11px' : '12px',
            padding: isPhone ? '12px 8px' : '16px 24px',
            lineHeight: isPhone ? '1.3' : '1.5'
          }}
        >
          VibResearch © {new Date().getFullYear()} 一体化科研工作台
        </Footer>
      </Layout>

      <Drawer
        placement="left"
        width={isPhone ? 280 : 300}
        onClose={() => setMobileMenuOpen(false)}
        open={mobileMenuOpen}
        bodyStyle={{ padding: 0 }}
        className="mobile-drawer"
        styles={{
          header: { padding: '16px 20px', borderBottom: '1px solid #f0f0f0' },
          body: { padding: 0, background: 'linear-gradient(180deg, #fafbfc 0%, #f5f6fa 100%)' }
        }}
      >
        <div className="h-16 flex items-center gap-3 px-4 border-b border-neural-200 bg-white">
          <RocketOutlined className="text-2xl text-primary-500" />
          <Text className="text-base font-semibold text-neural-800">{titleLabel}</Text>
        </div>
        <div className="px-2 pt-4">
          <Menu
            mode="inline"
            selectedKeys={activeKey ? [activeKey] : []}
            onClick={handleMenuClick}
            className="border-none bg-transparent"
            items={renderMenuItems(navItems).map(item => ({
              ...item,
              className: 'nav-item-touch mb-1 rounded-lg hover:bg-primary-50 transition-all duration-200'
            }))}
          />
        </div>

        {/* Mobile search bar */}
        <div className="p-4 border-t border-neural-200 bg-white">
          <TouchInput
            placeholder="搜索文献、项目、任务..."
            prefix={<SearchOutlined />}
            variant="form"
            allowClear
          />
        </div>
      </Drawer>
    </Layout>
  );
};

export default AppLayout;
