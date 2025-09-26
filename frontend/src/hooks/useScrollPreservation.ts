import { useEffect, useCallback } from 'react';
import { useLocation } from 'react-router-dom';
import { useLayoutStore } from '@/stores/layout.store';
import { useAppStore } from '@/stores/app.store';

/**
 * Hook for preserving scroll position during navigation and project switching
 */
export function useScrollPreservation() {
  const location = useLocation();
  const currentProject = useAppStore((state) => state.currentProject);
  const { saveScrollPosition, getScrollPosition } = useLayoutStore();

  // Generate unique key for current scroll context
  const getScrollKey = useCallback(() => {
    const projectId = currentProject?.id || 'global';
    const route = location.pathname;
    return `${projectId}:${route}`;
  }, [currentProject?.id, location.pathname]);

  // Save scroll position before route change
  const saveCurrentScrollPosition = useCallback(() => {
    const scrollKey = getScrollKey();
    const mainContent = document.querySelector('[data-scroll-container]');
    if (mainContent) {
      const scrollTop = mainContent.scrollTop;
      saveScrollPosition(scrollKey, scrollTop);
    }
  }, [getScrollKey, saveScrollPosition]);

  // Restore scroll position after route change
  const restoreScrollPosition = useCallback(() => {
    const scrollKey = getScrollKey();
    const savedPosition = getScrollPosition(scrollKey);

    if (savedPosition > 0) {
      // Use setTimeout to ensure DOM is ready
      setTimeout(() => {
        const mainContent = document.querySelector('[data-scroll-container]');
        if (mainContent) {
          mainContent.scrollTo({
            top: savedPosition,
            behavior: 'smooth'
          });
        }
      }, 100);
    }
  }, [getScrollKey, getScrollPosition]);

  // Save scroll position on route/project change
  useEffect(() => {
    return () => {
      saveCurrentScrollPosition();
    };
  }, [location.pathname, currentProject?.id, saveCurrentScrollPosition]);

  // Restore scroll position on mount and route/project change
  useEffect(() => {
    restoreScrollPosition();
  }, [location.pathname, currentProject?.id, restoreScrollPosition]);

  // Manual scroll position management
  const manualSave = useCallback(() => {
    saveCurrentScrollPosition();
  }, [saveCurrentScrollPosition]);

  const manualRestore = useCallback(() => {
    restoreScrollPosition();
  }, [restoreScrollPosition]);

  return {
    saveScrollPosition: manualSave,
    restoreScrollPosition: manualRestore,
  };
}
