import type { ReactNode } from 'react';
import { NavLink } from 'react-router-dom';
import styles from './perplexity-shell.module.css';

interface PerplexityShellProps {
  librarySwitcher?: ReactNode;
  modeBar: ReactNode;
  conversation: ReactNode;
  contextPanel?: ReactNode;
  sidebarFooter?: ReactNode;
}

const navItems = [
  { to: '/research', label: '新研究', icon: '🧠' },
  { to: '/library', label: '文献库', icon: '📚' },
  { to: '/settings', label: '高级设置', icon: '⚙️' },
];

export function PerplexityShell({
  librarySwitcher,
  modeBar,
  conversation,
  contextPanel,
  sidebarFooter,
}: PerplexityShellProps) {
  const bodyClassName = [styles.body, contextPanel ? undefined : styles.bodyFull]
    .filter(Boolean)
    .join(' ');

  return (
    <div className={styles.wrapper}>
      <aside className={styles.sidebar}>
        <div className={styles.sidebarHeader}>
          <div className={styles.brand}>VibeResearch</div>
          {librarySwitcher ? <div className={styles.librarySwitcher}>{librarySwitcher}</div> : null}
        </div>
        <nav className={styles.navList}>
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                [styles.navItem, isActive ? styles.activeNav : undefined].filter(Boolean).join(' ')
              }
            >
              <span className={styles.navIcon}>{item.icon}</span>
              <span className={styles.navLabel}>{item.label}</span>
            </NavLink>
          ))}
        </nav>
        {sidebarFooter ? <div className={styles.sidebarFooter}>{sidebarFooter}</div> : null}
      </aside>
      <div className={styles.mainArea}>
        <header className={styles.modeBar}>{modeBar}</header>
        <div className={bodyClassName}>
          <section className={styles.conversation}>{conversation}</section>
          {contextPanel ? <aside className={styles.contextPanel}>{contextPanel}</aside> : null}
        </div>
      </div>
    </div>
  );
}
