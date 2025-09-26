import React from 'react';
import { Input as AntInput, type InputProps } from 'antd';
import { useResponsive } from '@/hooks/useResponsive';

interface TouchInputProps extends Omit<InputProps, 'variant'> {
  touchOptimized?: boolean;
  variant?: 'default' | 'search' | 'form';
}

export const TouchInput: React.FC<TouchInputProps> = ({
  touchOptimized = true,
  variant = 'default',
  className = '',
  style = {},
  ...props
}) => {
  const { isPhone, isTablet } = useResponsive();

  const getInputStyles = () => {
    if (!touchOptimized) return {};

    const baseHeight = isPhone ? 48 : isTablet ? 44 : 40;
    const baseFontSize = isPhone ? '16px' : isTablet ? '15px' : '14px';

    const variantStyles = {
      default: {
        height: baseHeight,
        fontSize: baseFontSize,
        borderRadius: isPhone ? '12px' : isTablet ? '10px' : '8px',
      },
      search: {
        height: baseHeight,
        fontSize: baseFontSize,
        borderRadius: isPhone ? '24px' : isTablet ? '20px' : '16px',
      },
      form: {
        height: baseHeight,
        fontSize: baseFontSize,
        borderRadius: isPhone ? '8px' : isTablet ? '6px' : '4px',
      }
    };

    return variantStyles[variant];
  };

  const inputStyles = getInputStyles();

  return (
    <AntInput
      {...props}
      className={`touch-input ${touchOptimized ? 'input-touch' : ''} ${className}`}
      style={{
        ...inputStyles,
        touchAction: 'manipulation',
        ...style,
      }}
    />
  );
};

export default TouchInput;
