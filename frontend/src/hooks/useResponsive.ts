import { useState, useEffect } from 'react';
import { Grid } from 'antd';

const { useBreakpoint } = Grid;

export interface ResponsiveState {
  isPhone: boolean;
  isTablet: boolean;
  isDesktop: boolean;
  isMobile: boolean;
  screenWidth: number;
  orientation: 'portrait' | 'landscape';
}

export const useResponsive = (): ResponsiveState => {
  const screens = useBreakpoint();
  const [screenWidth, setScreenWidth] = useState(0);
  const [orientation, setOrientation] = useState<'portrait' | 'landscape'>('portrait');

  useEffect(() => {
    const updateScreenInfo = () => {
      setScreenWidth(window.innerWidth);
      setOrientation(window.innerWidth > window.innerHeight ? 'landscape' : 'portrait');
    };

    updateScreenInfo();
    window.addEventListener('resize', updateScreenInfo);
    return () => window.removeEventListener('resize', updateScreenInfo);
  }, []);

  const mdUp = !!screens.md;
  const lgUp = !!screens.lg;

  const isPhone = !mdUp;
  const isTablet = mdUp && !lgUp;
  const isDesktop = lgUp;
  const isMobile = !lgUp;

  return {
    isPhone,
    isTablet,
    isDesktop,
    isMobile,
    screenWidth,
    orientation,
  };
};

export const useResponsiveValues = <T>(values: {
  phone?: T;
  tablet?: T;
  desktop?: T;
  default: T;
}): T => {
  const { isPhone, isTablet, isDesktop } = useResponsive();

  if (isPhone && values.phone !== undefined) return values.phone;
  if (isTablet && values.tablet !== undefined) return values.tablet;
  if (isDesktop && values.desktop !== undefined) return values.desktop;

  return values.default;
};

export const getTouchTargetSize = (isPhone: boolean, isTablet: boolean): { width: number; height: number } => {
  if (isPhone) return { width: 48, height: 48 };
  if (isTablet) return { width: 44, height: 44 };
  return { width: 32, height: 32 };
};

export const getResponsivePadding = (isPhone: boolean, isTablet: boolean): string => {
  if (isPhone) return '12px 8px';
  if (isTablet) return '16px 12px';
  return '24px 32px';
};

export const getResponsiveFontSize = (isPhone: boolean, isTablet: boolean): {
  xs: string;
  sm: string;
  base: string;
  lg: string;
  xl: string;
} => {
  const scale = isPhone ? 0.9 : isTablet ? 0.95 : 1;

  return {
    xs: `${0.75 * scale}rem`,
    sm: `${0.875 * scale}rem`,
    base: `${1 * scale}rem`,
    lg: `${1.125 * scale}rem`,
    xl: `${1.25 * scale}rem`,
  };
};

export default useResponsive;
