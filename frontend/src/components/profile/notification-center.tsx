import React from 'react';
import { Card, List, Button, Badge, Empty, Typography, Space, Tag, message, Spin } from 'antd';
import {
  CheckOutlined,
  CloseOutlined,
  BellOutlined,
  ExclamationCircleOutlined,
  CheckCircleOutlined,
  CrownOutlined,
  TeamOutlined,
  MessageOutlined,
  ExportOutlined
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { formatDistanceToNow } from 'date-fns';
import { zhCN } from 'date-fns/locale';
import { userAPI, type Notification } from '@/services/api/user';

const { Text } = Typography;

// 通知类型对应的图标和颜色
const notificationConfig = {
  task_completed: {
    icon: <CheckCircleOutlined />,
    color: 'success',
    tagColor: 'green',
    title: '任务完成'
  },
  task_failed: {
    icon: <CloseOutlined />,
    color: 'error',
    tagColor: 'red',
    title: '任务失败'
  },
  membership_expiring: {
    icon: <ExclamationCircleOutlined />,
    color: 'warning',
    tagColor: 'orange',
    title: '会员即将到期'
  },
  membership_expired: {
    icon: <CrownOutlined />,
    color: 'error',
    tagColor: 'red',
    title: '会员已过期'
  },
  system_alert: {
    icon: <BellOutlined />,
    color: 'info',
    tagColor: 'blue',
    title: '系统通知'
  },
  project_shared: {
    icon: <TeamOutlined />,
    color: 'info',
    tagColor: 'blue',
    title: '项目分享'
  },
  comment_added: {
    icon: <MessageOutlined />,
    color: 'info',
    tagColor: 'blue',
    title: '新评论'
  }
};

export const NotificationCenter: React.FC = () => {
  const queryClient = useQueryClient();

  // 获取通知列表
  const notificationsQuery = useQuery<Notification[]>({
    queryKey: ['user-notifications'],
    queryFn: () => userAPI.getNotifications(),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

  // 获取未读数量
  const unreadCountQuery = useQuery<{ unread_count: number }>({
    queryKey: ['user-notifications-unread-count'],
    queryFn: () => userAPI.getUnreadNotificationsCount(),
    staleTime: 30_000,
    refetchInterval: 60_000,
  });

  // 更新通知状态
  const updateNotificationMutation = useMutation({
    mutationFn: ({ id, status }: { id: number; status: 'read' | 'archived' }) =>
      userAPI.updateNotification(id, { status }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['user-notifications'] });
      void queryClient.invalidateQueries({ queryKey: ['user-notifications-unread-count'] });
    },
    onError: () => {
      void message.error('操作失败，请重试');
    }
  });

  // 标记所有为已读
  const markAllReadMutation = useMutation({
    mutationFn: () => userAPI.markAllNotificationsRead(),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['user-notifications'] });
      void queryClient.invalidateQueries({ queryKey: ['user-notifications-unread-count'] });
      void message.success('所有通知已标记为已读');
    },
    onError: () => {
      void message.error('操作失败，请重试');
    }
  });

  const handleMarkAsRead = (notification: Notification) => {
    if (notification.status === 'unread') {
      void updateNotificationMutation.mutate({
        id: notification.id,
        status: 'read'
      });
    }
  };

  const handleArchive = (notification: Notification) => {
    void updateNotificationMutation.mutate({
      id: notification.id,
      status: 'archived'
    });
  };

  const handleMarkAllRead = () => {
    void markAllReadMutation.mutate();
  };

  const handleActionClick = (notification: Notification) => {
    if (notification.action_url) {
      window.open(notification.action_url, '_blank');
    }
    handleMarkAsRead(notification);
  };

  const notifications = notificationsQuery.data || [];
  const unreadCount = unreadCountQuery.data?.unread_count || 0;
  const isLoading = notificationsQuery.isLoading || unreadCountQuery.isLoading;

  return (
    <Card
      className="h-full"
      title={
        <Space>
          <BellOutlined />
          <span>通知中心</span>
          {unreadCount > 0 && (
            <Badge count={unreadCount} size="small" />
          )}
        </Space>
      }
      extra={
        notifications.length > 0 && unreadCount > 0 && (
          <Button
            type="link"
            size="small"
            loading={markAllReadMutation.isPending}
            onClick={handleMarkAllRead}
          >
            全部已读
          </Button>
        )
      }
    >
      <Spin spinning={isLoading}>
        {notifications.length === 0 ? (
          <Empty
            image={Empty.PRESENTED_IMAGE_SIMPLE}
            description="暂无通知"
            className="py-8"
          />
        ) : (
          <List
            size="small"
            dataSource={notifications}
            className="max-h-96 overflow-y-auto"
            renderItem={(notification) => {
              const config = notificationConfig[notification.type as keyof typeof notificationConfig];
              const isUnread = notification.status === 'unread';

              return (
                <List.Item
                  className={`transition-colors hover:bg-gray-50 ${isUnread ? 'bg-blue-50' : ''}`}
                  actions={[
                    ...(notification.action_url ? [
                      <Button
                        key="action"
                        type="link"
                        size="small"
                        icon={<ExportOutlined />}
                        onClick={() => handleActionClick(notification)}
                      >
                        查看
                      </Button>
                    ] : []),
                    ...(isUnread ? [
                      <Button
                        key="read"
                        type="link"
                        size="small"
                        icon={<CheckOutlined />}
                        loading={updateNotificationMutation.isPending}
                        onClick={() => handleMarkAsRead(notification)}
                      >
                        已读
                      </Button>
                    ] : []),
                    <Button
                      key="archive"
                      type="link"
                      size="small"
                      danger
                      loading={updateNotificationMutation.isPending}
                      onClick={() => handleArchive(notification)}
                    >
                      删除
                    </Button>
                  ]}
                >
                  <List.Item.Meta
                    avatar={
                      <div className={`text-lg ${config ? `text-${config.color}` : 'text-gray-500'}`}>
                        {config?.icon || <BellOutlined />}
                      </div>
                    }
                    title={
                      <div className="flex items-center gap-2">
                        <Text strong={isUnread} className={isUnread ? 'text-gray-900' : 'text-gray-600'}>
                          {notification.title}
                        </Text>
                        {config && (
                          <Tag color={config.tagColor}>
                            {config.title}
                          </Tag>
                        )}
                        {isUnread && (
                          <Badge status="processing" />
                        )}
                      </div>
                    }
                    description={
                      <div className="space-y-1">
                        <Text
                          type="secondary"
                          className={`block ${isUnread ? 'text-gray-700' : 'text-gray-500'}`}
                        >
                          {notification.message}
                        </Text>
                        <Text type="secondary" className="text-xs">
                          {formatDistanceToNow(new Date(notification.created_at), {
                            addSuffix: true,
                            locale: zhCN,
                          })}
                        </Text>
                      </div>
                    }
                  />
                </List.Item>
              );
            }}
          />
        )}
      </Spin>
    </Card>
  );
};
