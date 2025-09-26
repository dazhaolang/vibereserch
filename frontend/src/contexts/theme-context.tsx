import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { ConfigProvider, theme as antdTheme } from 'antd';
import { getAppTheme } from '@/theme/ant-theme';

export type ThemeMode = 'dark' | 'light' | 'system';

type ResolvedTheme = 'dark' | 'light';

type ThemeContextValue = {
  mode: ThemeMode;
  resolvedMode: ResolvedTheme;
  setMode: (mode: ThemeMode) => void;
};

const STORAGE_KEY = 'app-theme-mode';

const getStoredMode = (): ThemeMode => {
  if (typeof window === 'undefined') return 'dark';
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === 'dark' || stored === 'light' || stored === 'system' ? stored : 'dark';
};

const getSystemPreference = (): ResolvedTheme => {
  if (typeof window === 'undefined') return 'dark';
  return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
};

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

export function AppThemeProvider({ children }: { children: ReactNode }) {
  const initialSystemPreference = getSystemPreference();
  const [mode, setModeState] = useState<ThemeMode>(() => {
    const stored = getStoredMode();
    if (typeof document !== 'undefined') {
      const resolved = stored === 'system' ? initialSystemPreference : stored;
      document.documentElement.dataset.theme = resolved;
      document.documentElement.style.colorScheme = resolved;
    }
    return stored;
  });
  const [systemPreference, setSystemPreference] = useState<ResolvedTheme>(initialSystemPreference);

  const resolvedMode: ResolvedTheme = mode === 'system' ? systemPreference : mode;

  // Sync document dataset & color-scheme
  useEffect(() => {
    if (typeof document === 'undefined') return;
    const { documentElement } = document;
    documentElement.dataset.theme = resolvedMode;
    documentElement.style.colorScheme = resolvedMode;
  }, [resolvedMode]);

  // Listen to system preference changes when in system mode
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const media = window.matchMedia('(prefers-color-scheme: dark)');

    const updatePreference = (matches: boolean) => {
      setSystemPreference(matches ? 'dark' : 'light');
    };

    updatePreference(media.matches);

    if (mode !== 'system') return;

    const listener = (event: MediaQueryListEvent) => {
      updatePreference(event.matches);
    };

    if (typeof media.addEventListener === 'function') {
      media.addEventListener('change', listener);
      return () => media.removeEventListener('change', listener);
    }

    media.addListener(listener);
    return () => media.removeListener(listener);
  }, [mode]);

  const setMode = (next: ThemeMode) => {
    setModeState(next);
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEY, next);
    }
  };

  const contextValue = useMemo<ThemeContextValue>(
    () => ({ mode, resolvedMode, setMode }),
    [mode, resolvedMode]
  );

  const antdThemeConfig = useMemo(() => getAppTheme(resolvedMode), [resolvedMode]);
  const algorithm = resolvedMode === 'dark' ? antdTheme.darkAlgorithm : antdTheme.defaultAlgorithm;

  return (
    <ThemeContext.Provider value={contextValue}>
      <ConfigProvider theme={{ ...antdThemeConfig, algorithm }}>
        {children}
      </ConfigProvider>
    </ThemeContext.Provider>
  );
}

export function useThemeMode() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error('useThemeMode must be used within AppThemeProvider');
  return ctx;
}
