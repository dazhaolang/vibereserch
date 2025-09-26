import { useLocation, useNavigate } from 'react-router-dom';
import { useMemo, useState } from 'react';
import styles from './top-bar.module.css';
import { QuickActions } from '../common/quick-actions';
import { MotionFade } from '@/animations/motion-fade';
import { Avatar, Button, Dropdown, Space, Typography, message } from 'antd';
import type { MenuProps } from 'antd';
import { LogoutOutlined, UserOutlined, SettingOutlined } from '@ant-design/icons';
import { useSystemStore } from '@/stores/system-store';
import { useAuthStore } from '@/stores/auth-store';
import { authAPI } from '@/services/api/auth';

const titleMap: Record<string, string> = {
  '/': '项目总览',
  '/library': '文献库',
  '/research': '研究控制台',
  '/tasks': '任务中心',
  '/settings': '体验设置'
};

export function TopBar() {
  const location = useLocation();
  const navigate = useNavigate();
  const profile = useSystemStore((state) => state.profile);
  const setProfile = useSystemStore((state) => state.setProfile);
  const clearAuth = useAuthStore((state) => state.clear);
  const [loggingOut, setLoggingOut] = useState(false);

  const title = useMemo(() => {
    if (location.pathname === '/') return titleMap['/'];
    return titleMap[location.pathname] ?? 'VibeResearch';
  }, [location.pathname]);

  const displayName = useMemo(() => {
    if (!profile) return null;
    return profile.full_name || profile.username || profile.email;
  }, [profile]);

  const avatarLabel = useMemo(() => {
    if (!displayName) return 'V';
    return displayName.trim().charAt(0).toUpperCase();
  }, [displayName]);

  const handleLogout = async () => {
    setLoggingOut(true);
    try {
      await authAPI.logout();
      void message.success('已退出登录');
    } catch (error) {
      void message.error('退出登录时出现问题，请稍后再试');
    } finally {
      clearAuth();
      setProfile(null);
      setLoggingOut(false);
      navigate('/auth', { replace: true });
    }
  };

  const menuItems: MenuProps['items'] = [
    { key: 'profile', label: '个人中心', icon: <UserOutlined /> },
    { key: 'settings', label: '体验设置', icon: <SettingOutlined /> },
    { type: 'divider' },
    { key: 'logout', label: '退出登录', icon: <LogoutOutlined />, danger: true },
  ];

  const handleMenuClick: MenuProps['onClick'] = ({ key }) => {
    switch (key) {
      case 'profile':
        navigate('/profile');
        break;
      case 'settings':
        navigate('/settings');
        break;
      case 'logout':
        void handleLogout();
        break;
      default:
        break;
    }
  };

  return (
    <header className={styles.topBar}>
      <MotionFade>
        <div className={styles.heading}>
          <h1>{title}</h1>
          <p>深度研究 AI 平台 · 以互动澄清与自动流水线驱动科研洞察</p>
        </div>
      </MotionFade>
      <div className={styles.actions}>
        <QuickActions />
        {displayName ? (
          <Dropdown
            menu={{ items: menuItems, onClick: handleMenuClick }}
          >
            <Space size={12} className={`${styles.userInfo} touch-target cursor-pointer`}>
              <Avatar style={{ backgroundColor: '#2563eb' }}>{avatarLabel}</Avatar>
              <div className={styles.userText}>
                <Typography.Text style={{ color: '#e2e8f0' }} strong>
                  {displayName}
                </Typography.Text>
                {profile?.membership?.membership_type && (
                  <Typography.Text style={{ color: 'rgba(148,163,184,0.75)' }}>
                    {profile.membership.membership_type}
                  </Typography.Text>
                )}
              </div>
            </Space>
          </Dropdown>
        ) : (
          <Button type="primary" className="btn-touch" onClick={() => navigate('/auth')} loading={loggingOut}>
            登录账号
          </Button>
        )}
      </div>
    </header>
  );
}
