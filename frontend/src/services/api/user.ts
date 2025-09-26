import { apiClient } from './client';
import type { UserProfile, UsageStatistics } from '@/types/user';

export interface UpdateProfilePayload {
  full_name?: string | null;
  institution?: string | null;
  research_field?: string | null;
}

export interface UpdatePasswordPayload {
  current_password: string;
  new_password: string;
}

export interface StandardMessageResponse {
  success: boolean;
  message: string;
}

export interface SecurityEvent {
  id: number;
  user_id: number;
  event_type: 'login' | 'logout' | 'password_change' | 'failed_login';
  ip_address: string;
  location?: string;
  device_info?: string;
  user_agent?: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

export interface Notification {
  id: number;
  user_id: number;
  type: 'task_completed' | 'task_failed' | 'membership_expiring' | 'membership_expired' | 'system_alert' | 'project_shared' | 'comment_added';
  title: string;
  message: string;
  status: 'unread' | 'read' | 'archived';
  action_url?: string;
  metadata?: Record<string, unknown>;
  created_at: string;
  updated_at?: string;
  read_at?: string;
}

export interface NotificationUpdatePayload {
  status: 'read' | 'archived';
}

const getProfile = async (options?: { signal?: AbortSignal }): Promise<UserProfile> => {
  const { data } = await apiClient.get<UserProfile>('/api/user/profile', { signal: options?.signal });
  return data;
};

const updateProfile = async (payload: UpdateProfilePayload): Promise<StandardMessageResponse> => {
  const { data } = await apiClient.put<StandardMessageResponse>('/api/user/profile', payload);
  return data;
};

const updatePassword = async (payload: UpdatePasswordPayload): Promise<StandardMessageResponse> => {
  const { data } = await apiClient.put<StandardMessageResponse>('/api/user/password', payload);
  return data;
};

const getUsageStatistics = async (): Promise<UsageStatistics> => {
  const { data } = await apiClient.get<UsageStatistics>('/api/user/usage-statistics');
  return data;
};

const getSecurityEvents = async (): Promise<SecurityEvent[]> => {
  const { data } = await apiClient.get<SecurityEvent[]>('/api/user/security-events');
  return data;
};

const getNotifications = async (limit?: number, unreadOnly?: boolean): Promise<Notification[]> => {
  const params = new URLSearchParams();
  if (limit) params.append('limit', limit.toString());
  if (unreadOnly) params.append('unread_only', 'true');

  const { data } = await apiClient.get<Notification[]>(`/api/user/notifications?${params.toString()}`);
  return data;
};

const getUnreadNotificationsCount = async (): Promise<{ unread_count: number }> => {
  const { data } = await apiClient.get<{ unread_count: number }>('/api/user/notifications/unread-count');
  return data;
};

const updateNotification = async (id: number, payload: NotificationUpdatePayload): Promise<Notification> => {
  const { data } = await apiClient.put<Notification>(`/api/user/notifications/${id}`, payload);
  return data;
};

const markAllNotificationsRead = async (): Promise<StandardMessageResponse> => {
  const { data } = await apiClient.post<StandardMessageResponse>('/api/user/notifications/mark-all-read');
  return data;
};

const uploadAvatar = async (file: File): Promise<{ success: boolean; message: string; avatar_url: string }> => {
  const formData = new FormData();
  formData.append('file', file);

  const { data } = await apiClient.post<{ success: boolean; message: string; avatar_url: string }>(
    '/api/user/profile/avatar',
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );
  return data;
};

const deleteAvatar = async (): Promise<StandardMessageResponse> => {
  const { data } = await apiClient.delete<StandardMessageResponse>('/api/user/profile/avatar');
  return data;
};

export const userAPI = {
  getProfile,
  updateProfile,
  updatePassword,
  getUsageStatistics,
  getSecurityEvents,
  getNotifications,
  getUnreadNotificationsCount,
  updateNotification,
  markAllNotificationsRead,
  uploadAvatar,
  deleteAvatar,
};

export async function fetchUserProfile(options?: { signal?: AbortSignal }): Promise<UserProfile> {
  return userAPI.getProfile(options);
}
