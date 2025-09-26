import { apiClient } from './client';
import { useAuthStore } from '@/stores/auth-store';

export interface UserInfo {
  id: number;
  email: string;
  username: string;
  full_name?: string;
  institution?: string;
  research_field?: string;
  is_active: boolean;
  is_verified: boolean;
  created_at: string;
  updated_at?: string;
  last_login?: string;
  membership: {
    id: number;
    user_id: number;
    membership_type: 'FREE' | 'PREMIUM' | 'ENTERPRISE';
    monthly_literature_used: number;
    monthly_queries_used: number;
    total_projects: number;
    subscription_start?: string;
    subscription_end?: string;
    auto_renewal: boolean;
    created_at: string;
    updated_at?: string;
  };
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  user_info: UserInfo;
}

export interface RegisterPayload {
  email: string;
  password: string;
  username: string;
  full_name?: string;
  institution?: string;
  research_field?: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface UpdateProfilePayload {
  full_name?: string;
  institution?: string;
  research_field?: string;
}

export interface ChangePasswordPayload {
  current_password: string;
  new_password: string;
}

export const authAPI = {
  // 用户注册
  async register(payload: RegisterPayload): Promise<LoginResponse> {
    const { data } = await apiClient.post<LoginResponse>('/api/auth/register', payload);

    // 注册成功后自动设置认证信息
    useAuthStore.getState().setCredentials(data.access_token, data.user_info.id);

    return data;
  },

  // 用户登录
  async login(payload: LoginPayload): Promise<LoginResponse> {
    const { data } = await apiClient.post<LoginResponse>('/api/auth/login', payload);

    // 保存认证信息到状态管理
    useAuthStore.getState().setCredentials(data.access_token, data.user_info.id);

    return data;
  },

  // 用户登出
  async logout(): Promise<{ message: string }> {
    try {
      const { data } = await apiClient.post<{ message: string }>('/api/auth/logout');
      return data;
    } catch (error) {
      console.error('Logout error:', error);
      throw error;
    } finally {
      // 清除本地认证信息
      useAuthStore.getState().clear();
    }
  },

  // 获取当前用户信息
  async getCurrentUser(): Promise<UserInfo> {
    const { data } = await apiClient.get<UserInfo>('/api/auth/me');
    return data;
  },

  // 更新用户资料
  async updateProfile(payload: UpdateProfilePayload): Promise<UserInfo> {
    const body: Record<string, unknown> = {};
    if (payload.full_name !== undefined) {
      body.full_name = payload.full_name;
    }
    if (payload.institution !== undefined) {
      body.institution = payload.institution;
    }
    if (payload.research_field !== undefined) {
      body.research_field = payload.research_field;
    }
    const { data } = await apiClient.put<UserInfo>('/api/user/profile', body);
    return data;
  },

  // 修改密码
  async changePassword(payload: ChangePasswordPayload): Promise<{ message: string }> {
    const body = {
      current_password: payload.current_password,
      new_password: payload.new_password,
    };
    const { data } = await apiClient.put<{ message: string }>('/api/user/password', body);
    return data;
  },

  // 邮箱验证
  async requestEmailVerification(): Promise<{ message: string }> {
    const { data } = await apiClient.post<{ message: string }>('/api/auth/request-verification');
    return data;
  },

  async verifyEmail(token: string): Promise<{ message: string }> {
    const { data } = await apiClient.post<{ message: string }>('/api/auth/verify-email', { token });
    return data;
  },

  // 密码重置
  async requestPasswordReset(email: string): Promise<{ message: string }> {
    const { data } = await apiClient.post<{ message: string }>('/api/auth/forgot-password', { email });
    return data;
  },

  async resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
    const { data } = await apiClient.post<{ message: string }>('/api/auth/reset-password', {
      token,
      new_password: newPassword,
    });
    return data;
  },

  // 检查认证状态
  async checkAuth(): Promise<{ isAuthenticated: boolean; user: UserInfo | null }> {
    try {
      const user = await authAPI.getCurrentUser();
      return { isAuthenticated: true, user };
    } catch (error) {
      return { isAuthenticated: false, user: null };
    }
  }
};

// 保持向后兼容
export const login = (payload: LoginPayload) => authAPI.login(payload);
export const logout = () => authAPI.logout();

export default authAPI;
