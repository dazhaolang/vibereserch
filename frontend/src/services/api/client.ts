import axios, { isAxiosError, type AxiosError } from 'axios';
import { useAuthStore } from '@/stores/auth-store';

const UNAUTH_STATUSES = new Set([401, 403]);

const resolveBaseUrl = (value: string | undefined) => {
  if (value === undefined || value === '' || value === '/') {
    return 'http://154.12.50.153:8000';
  }
  return value.endsWith('/') ? value.slice(0, -1) : value;
};

const apiClient = axios.create({
  baseURL: resolveBaseUrl(import.meta.env.VITE_API_BASE_URL),
  timeout: 15000
});

apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().accessToken;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (axios.isCancel(error)) {
      return Promise.reject(error);
    }

    if (isAxiosError(error) && error.response?.status && UNAUTH_STATUSES.has(error.response.status)) {
      useAuthStore.getState().clear();
      // 重定向到登录页
      if (typeof window !== 'undefined' && window.location.pathname !== '/auth') {
        window.location.href = '/auth';
      }
    }
    return Promise.reject(error);
  }
);

export { apiClient };
