import type { CSSProperties, ReactNode } from 'react';
import { motion } from 'framer-motion';
import { Sidebar } from './sidebar';
import { TopBar } from './top-bar';
import { BackgroundAurora } from './background-aurora';
import { useLayoutStore } from '@/stores/layout.store';
import { useScrollPreservation } from '@/hooks/useScrollPreservation';
import styles from './app-layout.module.css';

export function AppLayout({ children }: { children: ReactNode }) {
  const isSidebarCollapsed = useLayoutStore((state) => state.isSidebarCollapsed);
  const sidebarWidth = isSidebarCollapsed ? 80 : 280;

  const wrapperStyle = {
    '--sidebar-width': `${sidebarWidth}px`,
    gridTemplateColumns: 'var(--sidebar-width) 1fr',
  } as CSSProperties;

  // Enable scroll position preservation
  useScrollPreservation();

  return (
    <div
      className={styles.wrapper}
      style={wrapperStyle}
    >
      <BackgroundAurora />
      <motion.div
        initial={false}
        animate={{
          width: sidebarWidth,
        }}
        transition={{
          type: 'spring',
          stiffness: 300,
          damping: 30,
          mass: 0.8,
        }}
        className={styles.sidebarContainer}
      >
        <Sidebar />
      </motion.div>
      <div className={styles.mainColumn}>
        <TopBar />
        <main
          className={styles.mainContent}
          data-scroll-container
        >
          {children}
        </main>
      </div>
    </div>
  );
}
