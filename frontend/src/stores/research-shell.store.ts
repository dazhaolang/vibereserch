import { create } from 'zustand';
import { devtools } from 'zustand/middleware';

export type ConversationMode = 'rag' | 'deep' | 'auto';
export type LibraryStatus = 'unselected' | 'ready' | 'building' | 'merging' | 'error';

interface ResearchShellState {
  mode: ConversationMode;
  libraryId: number | null;
  libraryStatus: LibraryStatus;
  sessionId: string | null;
  isAutoPipelineActive: boolean;
  setMode: (mode: ConversationMode) => void;
  setLibraryId: (libraryId: number | null) => void;
  setLibraryStatus: (status: LibraryStatus) => void;
  setSessionId: (sessionId: string | null) => void;
  setAutoPipelineActive: (active: boolean) => void;
  reset: () => void;
}

const initialState: Omit<ResearchShellState,
  'setMode' | 'setLibraryId' | 'setLibraryStatus' | 'setSessionId' | 'setAutoPipelineActive' | 'reset'
> = {
  mode: 'rag',
  libraryId: null,
  libraryStatus: 'unselected',
  sessionId: null,
  isAutoPipelineActive: false,
};

export const useResearchShellStore = create<ResearchShellState>()(
  devtools((set) => ({
    ...initialState,
    setMode: (mode) =>
      set((state) => {
        if (mode === 'auto') {
          return {
            ...state,
            mode,
            isAutoPipelineActive: true,
          };
        }
        return {
          ...state,
          mode,
          isAutoPipelineActive: false,
        };
      }),
    setLibraryId: (libraryId) =>
      set((state) => ({
        ...state,
        libraryId,
        libraryStatus: libraryId === null ? 'unselected' : state.libraryStatus === 'unselected' ? 'ready' : state.libraryStatus,
      })),
    setLibraryStatus: (libraryStatus) =>
      set((state) => ({
        ...state,
        libraryStatus,
      })),
    setSessionId: (sessionId) =>
      set((state) => ({
        ...state,
        sessionId,
      })),
    setAutoPipelineActive: (active) =>
      set((state) => ({
        ...state,
        isAutoPipelineActive: active,
        mode: active ? 'auto' : state.mode === 'auto' ? 'rag' : state.mode,
      })),
    reset: () => set({ ...initialState }),
  }))
);
