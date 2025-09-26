import React from 'react';
import { Card as AntCard } from 'antd';
import type { CardProps } from 'antd';
import { useResponsive } from '@/hooks/useResponsive';

interface ResponsiveCardProps extends CardProps {
  touchOptimized?: boolean;
  hoverEffect?: boolean;
  spacing?: 'compact' | 'normal' | 'relaxed';
}

export const ResponsiveCard: React.FC<ResponsiveCardProps> = ({
  touchOptimized = true,
  hoverEffect = true,
  spacing = 'normal',
  className = '',
  style = {},
  children,
  ...props
}) => {
  const { isPhone, isTablet } = useResponsive();

  const getSpacingStyles = () => {
    const baseSpacing = {
      compact: { padding: isPhone ? '12px' : '16px' },
      normal: { padding: isPhone ? '16px' : '20px' },
      relaxed: { padding: isPhone ? '20px' : '24px' },
    };

    return baseSpacing[spacing];
  };

  const getTouchStyles = () => {
    if (!touchOptimized) return {};

    return {
      borderRadius: isPhone ? '12px' : isTablet ? '10px' : '8px',
      minHeight: isPhone ? '80px' : '60px',
      transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
      touchAction: 'manipulation',
    };
  };

  const getHoverStyles = () => {
    if (!hoverEffect) return '';

    return 'card-hover hover:shadow-lg hover:-translate-y-1 active:scale-[0.99] transition-all duration-200';
  };

  const spacingStyles = getSpacingStyles();
  const touchStyles = getTouchStyles();

  return (
    <AntCard
      {...props}
      className={`
        ${touchOptimized ? 'card-touch' : ''}
        ${getHoverStyles()}
        border border-neural-200
        bg-white/90 backdrop-blur-sm
        ${className}
      `.trim()}
      style={{
        ...spacingStyles,
        ...touchStyles,
        boxShadow: isPhone
          ? '0 2px 8px rgba(0, 0, 0, 0.08)'
          : '0 1px 4px rgba(0, 0, 0, 0.06)',
        border: '1px solid rgba(148, 163, 184, 0.2)',
        ...style,
      }}
      bodyStyle={{
        padding: 0,
        ...(props.bodyStyle || {}),
      }}
    >
      <div style={spacingStyles}>
        {children}
      </div>
    </AntCard>
  );
};

export default ResponsiveCard;
