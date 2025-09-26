import React from 'react';
import { Button as AntButton } from 'antd';
import type { ButtonProps } from 'antd';
import { useResponsive, getTouchTargetSize } from '@/hooks/useResponsive';

interface TouchButtonProps extends ButtonProps {
  touchSize?: 'small' | 'medium' | 'large';
  hapticFeedback?: boolean;
}

export const TouchButton: React.FC<TouchButtonProps> = ({
  touchSize = 'medium',
  hapticFeedback = true,
  className = '',
  style = {},
  onClick,
  children,
  ...props
}) => {
  const { isPhone, isTablet } = useResponsive();

  const getSizeStyles = () => {
    const baseSize = getTouchTargetSize(isPhone, isTablet);

    switch (touchSize) {
      case 'small':
        return {
          minWidth: Math.max(baseSize.width - 8, 32),
          minHeight: Math.max(baseSize.height - 8, 32),
          padding: isPhone ? '8px 12px' : '6px 10px',
        };
      case 'large':
        return {
          minWidth: baseSize.width + 8,
          minHeight: baseSize.height + 8,
          padding: isPhone ? '16px 24px' : '14px 20px',
        };
      default:
        return {
          minWidth: baseSize.width,
          minHeight: baseSize.height,
          padding: isPhone ? '12px 16px' : '10px 14px',
        };
    }
  };

  const handleClick = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (hapticFeedback && 'vibrate' in navigator) {
      navigator.vibrate(50);
    }
    onClick?.(e);
  };

  const sizeStyles = getSizeStyles();

  return (
    <AntButton
      {...props}
      className={`touch-target btn-touch transition-all duration-200 ${className}`}
      style={{
        ...sizeStyles,
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        borderRadius: isPhone ? '8px' : '6px',
        fontSize: isPhone ? '16px' : '14px',
        fontWeight: '500',
        touchAction: 'manipulation',
        ...style,
      }}
      onClick={handleClick}
    >
      {children}
    </AntButton>
  );
};

export default TouchButton;
