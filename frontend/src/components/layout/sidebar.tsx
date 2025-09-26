import { NavLink } from 'react-router-dom';
import { motion, AnimatePresence } from 'framer-motion';
import { MenuFoldOutlined, MenuUnfoldOutlined } from '@ant-design/icons';
import { Tooltip } from 'antd';
import { useLayoutStore } from '@/stores/layout.store';
import styles from './sidebar.module.css';

const navItems = [
  { to: '/', label: '概览', icon: '📊' },
  { to: '/workspace', label: '执行工作台', icon: '🧪' },
  { to: '/research', label: '研究控制台', icon: '🧠' },
  { to: '/library', label: '文献库', icon: '📚' },
  { to: '/tasks', label: '任务中心', icon: '⚙️' },
  { to: '/settings', label: '设置', icon: '⚡' }
];

export function Sidebar() {
  const { isSidebarCollapsed, toggleSidebar } = useLayoutStore();

  return (
    <aside className={`${styles.sidebar} ${isSidebarCollapsed ? styles.collapsed : ''}`}>
      {/* Brand */}
      <div className={styles.brandContainer}>
        <AnimatePresence mode="wait">
          {!isSidebarCollapsed ? (
            <motion.div
              key="brand-full"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              transition={{ duration: 0.15 }}
              className={styles.brand}
            >
              VibeResearch
            </motion.div>
          ) : (
            <motion.div
              key="brand-mini"
              initial={{ opacity: 0, scale: 0.8 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.8 }}
              transition={{ duration: 0.15 }}
              className={styles.brandMini}
            >
              VR
            </motion.div>
          )}
        </AnimatePresence>

        {/* Toggle Button */}
        <Tooltip
          title={isSidebarCollapsed ? '展开侧边栏' : '收起侧边栏'}
          placement="right"
        >
          <motion.button
            className={styles.toggleButton}
            onClick={toggleSidebar}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          >
            {isSidebarCollapsed ? (
              <MenuUnfoldOutlined className={styles.toggleIcon} />
            ) : (
              <MenuFoldOutlined className={styles.toggleIcon} />
            )}
          </motion.button>
        </Tooltip>
      </div>

      {/* Navigation */}
      <nav className={styles.nav}>
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              [styles.navItem, isActive ? styles.active : undefined].filter(Boolean).join(' ')
            }
          >
            {({ isActive }) => (
              <Tooltip
                title={isSidebarCollapsed ? item.label : ''}
                placement="right"
                mouseEnterDelay={0.5}
              >
                <motion.span
                  className={styles.navInner}
                  whileHover={{ x: isSidebarCollapsed ? 0 : 6 }}
                  transition={{ type: 'spring', stiffness: 420, damping: 38 }}
                >
                  <span className={styles.icon} aria-hidden>
                    {item.icon}
                  </span>
                  <AnimatePresence>
                    {!isSidebarCollapsed && (
                      <motion.span
                        initial={{ opacity: 0, width: 0 }}
                        animate={{ opacity: 1, width: 'auto' }}
                        exit={{ opacity: 0, width: 0 }}
                        transition={{ duration: 0.15, delay: isSidebarCollapsed ? 0 : 0.1 }}
                        className={styles.label}
                      >
                        {item.label}
                      </motion.span>
                    )}
                  </AnimatePresence>
                  {isActive && (
                    <motion.div
                      layoutId="nav-active"
                      className={styles.activeIndicator}
                      transition={{ type: 'spring', stiffness: 300, damping: 30 }}
                    />
                  )}
                </motion.span>
              </Tooltip>
            )}
          </NavLink>
        ))}
      </nav>
    </aside>
  );
}
