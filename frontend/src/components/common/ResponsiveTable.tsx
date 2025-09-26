import React from 'react';
import { Table as AntTable } from 'antd';
import type { TableProps } from 'antd';
import { useResponsive } from '@/hooks/useResponsive';

interface ResponsiveTableProps<T extends object = Record<string, unknown>> extends TableProps<T> {
  touchOptimized?: boolean;
}

export const ResponsiveTable = <T extends object>({
  touchOptimized = true,
  className = '',
  scroll,
  pagination,
  ...props
}: ResponsiveTableProps<T>) => {
  const { isPhone, isTablet, isMobile } = useResponsive();

  const getTableProps = (): Partial<TableProps<T>> => {
    if (!touchOptimized) return {};

    const baseProps: Partial<TableProps<T>> = {
      size: isPhone ? 'large' : isTablet ? 'middle' : 'small',
      scroll: {
        x: isMobile ? 'max-content' : undefined,
        ...scroll,
      },
    };

    if (isMobile && pagination) {
      baseProps.pagination = {
        showSizeChanger: false,
        showQuickJumper: false,
        showTotal: (total, range) =>
          isPhone ? `${range[0]}-${range[1]} / ${total}` : `共 ${total} 条`,
        pageSize: isPhone ? 5 : 10,
        simple: isPhone,
        ...pagination,
      };
    }

    return baseProps;
  };

  const tableProps = getTableProps();

  return (
    <AntTable
      {...props}
      {...tableProps}
      className={`responsive-table ${touchOptimized ? 'table-touch' : ''} ${className}`}
      style={{
        fontSize: isPhone ? '16px' : isTablet ? '15px' : '14px',
        ...(props.style || {}),
      }}
    />
  );
};

export default ResponsiveTable;
