// 统一的设计系统配置
export const theme = {
  // 品牌色
  colors: {
    primary: {
      50: '#f0f9ff',
      100: '#e0f2fe',
      200: '#bae6fd',
      300: '#7dd3fc',
      400: '#38bdf8',
      500: '#0ea5e9',
      600: '#0284c7',
      700: '#0369a1',
      800: '#075985',
      900: '#0c4a6e',
    },
    secondary: {
      50: '#faf5ff',
      100: '#f3e8ff',
      200: '#e9d5ff',
      300: '#d8b4fe',
      400: '#c084fc',
      500: '#a855f7',
      600: '#9333ea',
      700: '#7e22ce',
      800: '#6b21a8',
      900: '#581c87',
    },
    success: '#10b981',
    warning: '#f59e0b',
    error: '#ef4444',
    info: '#3b82f6',
    dark: {
      bg: '#0f172a',
      card: '#1e293b',
      border: '#334155',
      text: '#cbd5e1',
    },
    light: {
      bg: '#f8fafc',
      card: '#ffffff',
      border: '#e2e8f0',
      text: '#1e293b',
    }
  },

  // 间距系统
  spacing: {
    xs: '0.5rem',
    sm: '1rem',
    md: '1.5rem',
    lg: '2rem',
    xl: '3rem',
    '2xl': '4rem',
  },

  // 圆角系统
  borderRadius: {
    none: '0',
    sm: '0.25rem',
    DEFAULT: '0.5rem',
    md: '0.75rem',
    lg: '1rem',
    xl: '1.5rem',
    full: '9999px',
  },

  // 阴影系统
  shadows: {
    sm: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
    DEFAULT: '0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06)',
    md: '0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06)',
    lg: '0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05)',
    xl: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
    '2xl': '0 25px 50px -12px rgba(0, 0, 0, 0.25)',
    inner: 'inset 0 2px 4px 0 rgba(0, 0, 0, 0.06)',
  },

  // 动画时长
  animation: {
    fast: '150ms',
    normal: '300ms',
    slow: '500ms',
  },

  // 字体系统
  fonts: {
    sans: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    mono: 'SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
  },

  // 断点
  breakpoints: {
    xs: '480px',
    sm: '640px',
    md: '768px',
    lg: '1024px',
    xl: '1280px',
    '2xl': '1536px',
  },
};

// 获取主题配置的辅助函数
type ThemeColors = typeof theme.colors;
type ColorPalette = Record<string | number, string>;

const isPalette = (value: unknown): value is ColorPalette =>
  typeof value === 'object' && value !== null;

export const getThemeColor = (colorKey: string, shade: number | string = 500): string | undefined => {
  const [group, nested] = colorKey.split('.');
  const colorEntry = theme.colors[group as keyof ThemeColors];

  if (!colorEntry) {
    return undefined;
  }

  if (!nested) {
    if (isPalette(colorEntry)) {
      const palette: ColorPalette = colorEntry;
      const numericShade = typeof shade === 'number' ? shade : Number(shade);
      if (!Number.isNaN(numericShade) && palette[numericShade] !== undefined) {
        return palette[numericShade];
      }
      const stringShade = typeof shade === 'string' ? shade : String(shade);
      return palette[stringShade];
    }
    return colorEntry;
  }

  if (!isPalette(colorEntry)) {
    return colorEntry;
  }

  const palette: ColorPalette = colorEntry;
  const numericKey = Number(nested);
  if (!Number.isNaN(numericKey) && palette[numericKey] !== undefined) {
    return palette[numericKey];
  }

  if (palette[nested] !== undefined) {
    return palette[nested];
  }

  const fallbackNumeric = typeof shade === 'number' ? shade : Number(shade);
  if (!Number.isNaN(fallbackNumeric) && palette[fallbackNumeric] !== undefined) {
    return palette[fallbackNumeric];
  }

  const fallbackString = typeof shade === 'string' ? shade : String(shade);
  return palette[fallbackString];
};

// 暗黑模式切换hook
import { useState, useEffect, useCallback } from 'react';

type BreakpointKey = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl';

export const useDarkMode = () => {
  const [isDark, setIsDark] = useState<boolean>(() => {
    const saved = localStorage.getItem('darkMode');
    return saved === 'true';
  });

  useEffect(() => {
    localStorage.setItem('darkMode', JSON.stringify(isDark));
    if (isDark) {
      document.documentElement.classList.add('dark');
    } else {
      document.documentElement.classList.remove('dark');
    }
  }, [isDark]);

  const toggleDark = useCallback(() => {
    setIsDark((prev) => !prev);
  }, []);

  return { isDark, toggleDark };
};

// 响应式断点hook
export const useBreakpoint = (): BreakpointKey => {
  const [breakpoint, setBreakpoint] = useState<BreakpointKey>('lg');

  useEffect(() => {
    const handleResize = () => {
      const width = window.innerWidth;
      if (width < 480) setBreakpoint('xs');
      else if (width < 640) setBreakpoint('sm');
      else if (width < 768) setBreakpoint('md');
      else if (width < 1024) setBreakpoint('lg');
      else if (width < 1280) setBreakpoint('xl');
      else setBreakpoint('2xl');
    };

    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  return breakpoint;
};
