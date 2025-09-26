const resolveBaseUrl = (value: string | undefined, fallback: string) => {
  if (value === undefined) {
    return fallback;
  }
  if (value === '' || value === '/') {
    return '';
  }
  return value.endsWith('/') ? value.slice(0, -1) : value;
};

const resolveWsUrl = (value: string | undefined, fallback: string) => {
  if (value === undefined) {
    return fallback;
  }
  if (value.startsWith('ws://') || value.startsWith('wss://')) {
    return value;
  }
  if (value.startsWith('http://') || value.startsWith('https://')) {
    return value.replace(/^http/, 'ws');
  }
  return value;
};

// Vite environment configuration
export const env = {
  VITE_API_BASE_URL: resolveBaseUrl(import.meta.env.VITE_API_BASE_URL, 'http://localhost:8000'),
  VITE_WS_URL: resolveWsUrl(import.meta.env.VITE_WS_URL, 'ws://localhost:8000/ws/global'),
  VITE_APP_NAME: import.meta.env.VITE_APP_NAME || '科研文献智能分析平台',
  DEV: import.meta.env.DEV || false,
  PROD: import.meta.env.PROD || false
};

export default env;
