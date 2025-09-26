import { useQuery } from '@tanstack/react-query';
import {
  Card,
  List,
  Typography,
  Skeleton,
  Tag,
  Space,
  Button,
  Tooltip,
  Empty,
  Alert
} from 'antd';
import {
  ClockCircleOutlined,
  EnvironmentOutlined,
  LaptopOutlined,
  MobileOutlined,
  TabletOutlined,
  DesktopOutlined,
  DownloadOutlined,
  ReloadOutlined
} from '@ant-design/icons';
import { userAPI, type SecurityEvent } from '@/services/api/user';

const { Text, Paragraph } = Typography;

// 设备类型图标映射
const getDeviceIcon = (deviceType: string) => {
  switch (deviceType.toLowerCase()) {
    case 'mobile':
      return <MobileOutlined />;
    case 'tablet':
      return <TabletOutlined />;
    case 'desktop':
      return <DesktopOutlined />;
    default:
      return <LaptopOutlined />;
  }
};

// 事件类型颜色映射
const getEventColor = (eventType: string) => {
  switch (eventType) {
    case 'login':
      return 'green';
    case 'logout':
      return 'blue';
    case 'password_change':
      return 'orange';
    case 'failed_login':
      return 'red';
    default:
      return 'default';
  }
};

// 事件类型标签文本
const getEventLabel = (eventType: string) => {
  switch (eventType) {
    case 'login':
      return '登录';
    case 'logout':
      return '退出';
    case 'password_change':
      return '密码修改';
    case 'failed_login':
      return '登录失败';
    default:
      return eventType;
  }
};

// 格式化时间
const formatTime = (timestamp: string) => {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  const diffHours = Math.floor(diffMs / (1000 * 60 * 60));
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

  if (diffMins < 60) {
    return `${diffMins}分钟前`;
  } else if (diffHours < 24) {
    return `${diffHours}小时前`;
  } else if (diffDays < 7) {
    return `${diffDays}天前`;
  } else {
    return date.toLocaleDateString('zh-CN', {
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  }
};

// 获取IP地理位置
const getLocationDisplay = (ipAddress: string, location?: string) => {
  if (location && location !== 'Unknown') {
    return location;
  }

  // 简单的内网IP判断
  if (ipAddress.startsWith('192.168.') ||
      ipAddress.startsWith('10.') ||
      ipAddress.startsWith('172.16.') ||
      ipAddress === '127.0.0.1') {
    return '本地网络';
  }

  return '未知位置';
};

export const ActivityLog = () => {
  const securityEventsQuery = useQuery<SecurityEvent[]>({
    queryKey: ['user-security-events'],
    queryFn: () => userAPI.getSecurityEvents(),
    staleTime: 60_000, // 1分钟内缓存
    refetchInterval: 5 * 60 * 1000, // 每5分钟自动刷新
  });

  const handleExport = () => {
    try {
      const data = securityEventsQuery.data;
      if (!data || data.length === 0) {
        return;
      }

      // 生成CSV内容
      const headers = ['时间', '事件类型', 'IP地址', '地理位置', '设备信息', '用户代理'];
      const csvContent = [
        headers.join(','),
        ...data.map(event => [
          new Date(event.timestamp).toLocaleString('zh-CN'),
          getEventLabel(event.event_type),
          event.ip_address,
          getLocationDisplay(event.ip_address, event.location),
          event.device_info || '',
          event.user_agent || ''
        ].map(field => `"${field}"`).join(','))
      ].join('\n');

      // 创建下载链接
      const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
      const link = document.createElement('a');
      const url = URL.createObjectURL(blob);
      link.setAttribute('href', url);
      link.setAttribute('download', `安全日志_${new Date().toISOString().split('T')[0]}.csv`);
      link.style.visibility = 'hidden';
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
    } catch (error) {
      console.error('导出失败:', error);
    }
  };

  const recentEvents = securityEventsQuery.data?.slice(0, 20) || [];
  const hasRecentActivity = recentEvents.length > 0;

  return (
    <Card
      title={
        <Space size={8}>
          <ClockCircleOutlined />
          <span>活动日志</span>
        </Space>
      }
      extra={
        <Space>
          <Tooltip title="刷新活动记录">
            <Button
              type="text"
              icon={<ReloadOutlined />}
              onClick={() => securityEventsQuery.refetch()}
              loading={securityEventsQuery.isFetching}
              size="small"
            />
          </Tooltip>
          <Tooltip title="导出为CSV文件">
            <Button
              type="text"
              icon={<DownloadOutlined />}
              onClick={handleExport}
              disabled={!hasRecentActivity}
              size="small"
            />
          </Tooltip>
        </Space>
      }
      className="bg-slate-900/40 border-slate-700"
      size="small"
    >
      {securityEventsQuery.isLoading ? (
        <Skeleton active paragraph={{ rows: 4 }} />
      ) : securityEventsQuery.error ? (
        <Alert
          message="加载失败"
          description="无法获取安全日志，请稍后重试"
          type="error"
          showIcon
          action={
            <Button size="small" onClick={() => securityEventsQuery.refetch()}>
              重试
            </Button>
          }
        />
      ) : !hasRecentActivity ? (
        <Empty
          description="暂无活动记录"
          image={Empty.PRESENTED_IMAGE_SIMPLE}
        />
      ) : (
        <>
          <div className="mb-3">
            <Text type="secondary" className="text-xs">
              显示最近 {recentEvents.length} 条活动记录
            </Text>
          </div>

          <List
            itemLayout="horizontal"
            dataSource={recentEvents}
            size="small"
            renderItem={(event) => (
              <List.Item className="border-b border-slate-700/30 last:border-b-0 py-3">
                <List.Item.Meta
                  avatar={
                    <div className="flex items-center justify-center w-8 h-8 rounded-lg bg-slate-800 border border-slate-600">
                      {getDeviceIcon(event.device_info || '')}
                    </div>
                  }
                  title={
                    <div className="flex items-center justify-between">
                      <Space size={8}>
                        <Tag color={getEventColor(event.event_type)}>
                          {getEventLabel(event.event_type)}
                        </Tag>
                        <Text className="text-sm font-medium">
                          {formatTime(event.timestamp)}
                        </Text>
                      </Space>
                    </div>
                  }
                  description={
                    <div className="space-y-1">
                      <div className="flex items-center gap-4 text-xs text-slate-400">
                        <Space size={4}>
                          <EnvironmentOutlined />
                          <span>{event.ip_address}</span>
                          <span>·</span>
                          <span>{getLocationDisplay(event.ip_address, event.location)}</span>
                        </Space>
                      </div>

                      {event.user_agent && (
                        <Paragraph
                          className="text-xs text-slate-500 mb-0"
                          ellipsis={{ rows: 1, tooltip: event.user_agent }}
                        >
                          {event.user_agent}
                        </Paragraph>
                      )}
                    </div>
                  }
                />
              </List.Item>
            )}
          />

          {recentEvents.length >= 20 && (
            <div className="mt-3 text-center">
              <Text type="secondary" className="text-xs">
                仅显示最近20条记录，完整日志可通过导出功能获取
              </Text>
            </div>
          )}
        </>
      )}
    </Card>
  );
};

export default ActivityLog;
