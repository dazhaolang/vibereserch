import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface LayoutState {
  // Sidebar state
  isSidebarCollapsed: boolean;

  // Scroll position storage for different routes/projects
  scrollPositions: Map<string, number>;

  // Actions
  toggleSidebar: () => void;
  setSidebarCollapsed: (collapsed: boolean) => void;
  saveScrollPosition: (key: string, position: number) => void;
  getScrollPosition: (key: string) => number;
  clearScrollPosition: (key: string) => void;
}

export const useLayoutStore = create<LayoutState>()(
  persist(
    (set, get) => ({
      isSidebarCollapsed: false,
      scrollPositions: new Map(),

      toggleSidebar: () =>
        set((state) => ({
          isSidebarCollapsed: !state.isSidebarCollapsed,
        })),

      setSidebarCollapsed: (collapsed: boolean) =>
        set({ isSidebarCollapsed: collapsed }),

      saveScrollPosition: (key: string, position: number) =>
        set((state) => {
          const newPositions = new Map(state.scrollPositions);
          newPositions.set(key, position);
          return { scrollPositions: newPositions };
        }),

      getScrollPosition: (key: string) => {
        const { scrollPositions } = get();
        return scrollPositions.get(key) ?? 0;
      },

      clearScrollPosition: (key: string) =>
        set((state) => {
          const newPositions = new Map(state.scrollPositions);
          newPositions.delete(key);
          return { scrollPositions: newPositions };
        }),
    }),
    {
      name: 'layout-store',
      // Only persist sidebar collapsed state, not scroll positions
      partialize: (state) => ({
        isSidebarCollapsed: state.isSidebarCollapsed
      }),
    }
  )
);