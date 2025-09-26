import type { ThemeConfig } from 'antd';

type SupportedMode = 'light' | 'dark';

const sharedTokens = {
  fontFamily: "'Inter','Noto Sans SC',sans-serif",
  borderRadius: 14,
};

const darkTheme: ThemeConfig = {
  token: {
    ...sharedTokens,
    colorPrimary: '#4C6EF5',
    colorInfo: '#4C6EF5',
    colorSuccess: '#4ADE80',
    colorWarning: '#FACC15',
    colorError: '#F87171',
    colorTextBase: '#E2E8F0',
    colorBgBase: '#0B1220',
    colorBgContainer: '#111A2C',
    boxShadowSecondary: '0 18px 40px rgba(12, 18, 32, 0.32)'
  },
  components: {
    Layout: {
      bodyBg: 'transparent',
      headerBg: 'rgba(15,23,42,0.85)'
    },
    Card: {
      paddingLG: 24,
      colorBgContainer: 'rgba(17, 26, 44, 0.85)',
      headerFontSize: 18,
      borderRadiusLG: 18,
      boxShadowTertiary: '0 24px 48px rgba(7, 12, 22, 0.45)'
    },
    Modal: {
      titleFontSize: 20,
      contentBg: 'rgba(15,20,35,0.95)',
      headerBg: 'rgba(12,18,32,0.95)',
      footerBg: 'rgba(12,18,32,0.95)',
      borderRadiusLG: 18
    },
    Segmented: {
      itemActiveBg: 'rgba(76,110,245,0.15)',
      trackBg: 'rgba(255,255,255,0.04)',
      itemColor: '#94A3B8'
    }
  }
};

const lightTheme: ThemeConfig = {
  token: {
    ...sharedTokens,
    colorPrimary: '#2563EB',
    colorInfo: '#2563EB',
    colorSuccess: '#16A34A',
    colorWarning: '#F59E0B',
    colorError: '#DC2626',
    colorTextBase: '#0F172A',
    colorBgBase: '#FFFFFF',
    colorBgContainer: '#FFFFFF',
    boxShadowSecondary: '0 18px 36px rgba(15, 23, 42, 0.12)'
  },
  components: {
    Layout: {
      bodyBg: 'transparent',
      headerBg: 'rgba(241,245,249,0.92)'
    },
    Card: {
      paddingLG: 24,
      colorBgContainer: 'rgba(255,255,255,0.95)',
      headerFontSize: 18,
      borderRadiusLG: 18,
      boxShadowTertiary: '0 18px 36px rgba(15, 23, 42, 0.08)'
    },
    Modal: {
      titleFontSize: 20,
      contentBg: '#FFFFFF',
      headerBg: '#FFFFFF',
      footerBg: '#FFFFFF',
      borderRadiusLG: 18
    },
    Segmented: {
      itemActiveBg: 'rgba(37, 99, 235, 0.12)',
      trackBg: 'rgba(15, 23, 42, 0.04)',
      itemColor: '#334155'
    }
  }
};

export const getAppTheme = (mode: SupportedMode): ThemeConfig => (mode === 'dark' ? darkTheme : lightTheme);
