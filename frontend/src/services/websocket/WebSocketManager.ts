type QueuedMessage = {
  type: string;
  payload?: Record<string, unknown>;
};

type ConnectionStatus = {
  connected: boolean;
  reconnectAttempts: number;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null && !Array.isArray(value);

const RECONNECT_DELAY = 2000;
const MAX_RECONNECT_ATTEMPTS = 5;

const convertHttpToWs = (url: string) => {
  if (url.startsWith('http://')) {
    return url.replace('http://', 'ws://');
  }
  if (url.startsWith('https://')) {
    return url.replace('https://', 'wss://');
  }
  return url;
};

const resolveDefaultGlobalUrl = () => {
  if (typeof window === 'undefined') {
    const apiBase = import.meta.env.VITE_API_BASE_URL as string | undefined;
    if (apiBase) {
      return convertHttpToWs(`${apiBase.replace(/\/$/, '')}/ws/global`);
    }
    return 'ws://localhost:8000/ws/global';
  }

  const configuredBase = import.meta.env.VITE_API_BASE_URL as string | undefined;
  if (configuredBase) {
    return convertHttpToWs(`${configuredBase.replace(/\/$/, '')}/ws/global`);
  }

  const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const host = window.location.host;
  return `${protocol}://${host}/ws/global`;
};

const normalizeWebSocketUrl = (url: string) => {
  if (!url) return resolveDefaultGlobalUrl();
  if (url.startsWith('ws://') || url.startsWith('wss://')) {
    return url;
  }
  if (url.startsWith('/')) {
    if (typeof window === 'undefined') {
      return `ws://localhost:8000${url}`;
    }
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const host = window.location.host;
    return `${protocol}://${host}${url}`;
  }
  return convertHttpToWs(url);
};

const withToken = (url: string, token?: string | null) => {
  if (!token) return url;
  try {
    const baseOrigin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000';
    const target = new URL(url, baseOrigin);
    target.searchParams.set('token', token);
    return target.toString();
  } catch (error) {
    console.warn('无法为 WebSocket URL 附加 token，使用原始地址', error);
    return url;
  }
};

const resolveAuthToken = (explicitToken?: string | null) => {
  if (explicitToken) return explicitToken;
  if (typeof window === 'undefined') return null;

  const direct = localStorage.getItem('access_token') || localStorage.getItem('token');
  if (direct) return direct;

  try {
    const persisted = localStorage.getItem('vibereserch-auth');
    if (persisted) {
      const parsed: unknown = JSON.parse(persisted);
      if (isRecord(parsed) && isRecord(parsed.state) && typeof parsed.state.accessToken === 'string') {
        return parsed.state.accessToken;
      }
    }
  } catch (error) {
    console.warn('无法解析持久化的认证信息', error);
  }

  return null;
};

const ensureGlobalPath = (value: string) => {
  if (!value) return value;

  if (value.startsWith('ws://') || value.startsWith('wss://')) {
    return value.endsWith('/ws/global') ? value : `${value.replace(/\/$/, '')}/ws/global`;
  }

  try {
    const baseOrigin = typeof window !== 'undefined' ? window.location.origin : 'http://localhost:3000';
    const resolved = new URL(value, baseOrigin);
    const protocol = resolved.protocol === 'https:' ? 'wss:' : resolved.protocol === 'http:' ? 'ws:' : resolved.protocol;
    return `${protocol}//${resolved.host}/ws/global`;
  } catch (error) {
    console.warn('无法解析 WebSocket 基地址，已回退默认路径', error);
    if (value.startsWith('/')) {
      return '/ws/global';
    }
    return `${value.replace(/\/$/, '')}/ws/global`;
  }
};

type EventHandler = (...args: unknown[]) => void;

class SimpleEmitter {
  private listeners = new Map<string, Set<EventHandler>>();

  on(event: string, handler: EventHandler) {
    const handlers = this.listeners.get(event) ?? new Set<EventHandler>();
    handlers.add(handler);
    this.listeners.set(event, handlers);
  }

  off(event: string, handler: EventHandler) {
    const handlers = this.listeners.get(event);
    if (!handlers) return;
    handlers.delete(handler);
    if (handlers.size === 0) {
      this.listeners.delete(event);
    }
  }

  emit(event: string, ...args: unknown[]) {
    const handlers = this.listeners.get(event);
    if (!handlers) return;
    handlers.forEach((handler) => {
      try {
        handler(...args);
      } catch (error) {
        console.error(`WebSocketManager listener error for event "${event}"`, error);
      }
    });
  }
}

class WebSocketManager extends SimpleEmitter {
  private socket: WebSocket | null = null;
  private reconnectAttempts = 0;
  private readonly maxReconnectAttempts = MAX_RECONNECT_ATTEMPTS;
  private readonly reconnectDelay = RECONNECT_DELAY;
  private connected = false;
  private messageQueue: QueuedMessage[] = [];
  private globalUrl: string;
  private pendingUrl: string | null = null;
  private candidateUrls: string[] = [];
  private candidateIndex = 0;
  private tokenRetryTimer: ReturnType<typeof setTimeout> | null = null;

  constructor() {
    super();
    this.candidateUrls = this.buildCandidateUrls();
    this.globalUrl = this.candidateUrls[0] ?? resolveDefaultGlobalUrl();
    this.pendingUrl = this.globalUrl;

    if (typeof window !== 'undefined') {
      // 尝试在前端启动后自动连接（延时避免与认证流程冲突）
      setTimeout(() => {
        this.connect();
      }, 1000);
    }
  }

  private scheduleTokenRetry() {
    if (typeof window === 'undefined') return;
    if (this.tokenRetryTimer) return;

    this.tokenRetryTimer = setTimeout(() => {
      this.tokenRetryTimer = null;
      this.connect(this.pendingUrl ?? this.candidateUrls[this.candidateIndex] ?? this.globalUrl);
    }, this.reconnectDelay);
  }

  private clearTokenRetry() {
    if (this.tokenRetryTimer) {
      clearTimeout(this.tokenRetryTimer);
      this.tokenRetryTimer = null;
    }
  }

  private buildCandidateUrls(): string[] {
    const seen = new Set<string>();

    const explicitWs = import.meta.env.VITE_WS_URL as string | undefined;
    if (explicitWs) {
      const candidate = explicitWs.includes('/ws') ? explicitWs : ensureGlobalPath(explicitWs);
      seen.add(normalizeWebSocketUrl(candidate));
    }

    const apiBase = import.meta.env.VITE_API_BASE_URL as string | undefined;
    if (apiBase) {
      seen.add(normalizeWebSocketUrl(ensureGlobalPath(apiBase)));
    }

    if (typeof window !== 'undefined') {
      seen.add(normalizeWebSocketUrl('/ws/global'));
      seen.add(normalizeWebSocketUrl(ensureGlobalPath(window.location.origin)));
    }

    seen.add(normalizeWebSocketUrl('http://localhost:8000/ws/global'));

    return Array.from(seen);
  }

  private getActiveBaseUrl() {
    const fallback = this.candidateUrls[this.candidateIndex] ?? this.globalUrl;
    return normalizeWebSocketUrl(this.pendingUrl ?? fallback);
  }

  private advanceCandidate() {
    if (this.candidateUrls.length <= 1) {
      return false;
    }

    const nextIndex = (this.candidateIndex + 1) % this.candidateUrls.length;
    if (nextIndex === this.candidateIndex) {
      return false;
    }

    this.candidateIndex = nextIndex;
    this.pendingUrl = this.candidateUrls[this.candidateIndex];
    console.warn(`[WebSocket] fallback to alternate endpoint: ${this.pendingUrl}`);
    return true;
  }

  connect(url?: string, token?: string) {
    const baseUrl = normalizeWebSocketUrl(url || this.pendingUrl || this.candidateUrls[this.candidateIndex] || this.globalUrl);
    const authToken = resolveAuthToken(token);

    if (!authToken) {
      this.pendingUrl = baseUrl;
      this.connected = false;
      this.scheduleTokenRetry();
      return;
    }

    const targetUrl = withToken(baseUrl, authToken);
    this.pendingUrl = baseUrl;
    const knownIndex = this.candidateUrls.indexOf(baseUrl);
    if (knownIndex >= 0) {
      this.candidateIndex = knownIndex;
    }

    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      this.socket = new WebSocket(targetUrl);
      this.pendingUrl = null;
      this.clearTokenRetry();
      this.setupEventHandlers();
    } catch (error) {
      console.error('创建 WebSocket 连接失败', error);
    }
  }

  private scheduleReconnect() {
    const authToken = resolveAuthToken();
    if (!authToken) {
      this.pendingUrl = this.pendingUrl ?? this.globalUrl;
      this.reconnectAttempts = 0;
      return;
    }

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      const advanced = this.advanceCandidate();
      this.reconnectAttempts = 0;
      if (!advanced) {
        console.error('WebSocket 重连次数已达上限');
        this.emit('max_reconnect_exceeded');
        return;
      }
    }

    this.reconnectAttempts += 1;
    this.clearTokenRetry();
    setTimeout(() => {
      this.connect(this.getActiveBaseUrl(), authToken);
    }, this.reconnectDelay * this.reconnectAttempts);
  }

  private setupEventHandlers() {
    if (!this.socket) return;

    this.socket.onopen = () => {
      this.pendingUrl = null;
      this.connected = true;
      this.reconnectAttempts = 0;
      this.emit('connected');
      this.flushQueue();
    };

    this.socket.onclose = (event) => {
      this.connected = false;
      this.emit('disconnected', event.reason);
      this.scheduleReconnect();
    };

    this.socket.onerror = (error) => {
      console.error('WebSocket 错误', error);
      this.emit('error', error);
    };

    this.socket.onmessage = (event: MessageEvent<string>) => {
      try {
        const payload: unknown = JSON.parse(event.data);
        this.routeIncomingMessage(payload);
      } catch (error) {
        console.warn('无法解析的 WebSocket 消息', event.data);
      }
    };
  }

  private routeIncomingMessage(message: unknown) {
    if (!isRecord(message)) return;
    const type = typeof message.type === 'string' ? message.type : 'message';

    switch (type) {
      case 'progress_event':
        this.emit('task_progress', isRecord(message.event) ? message.event : {});
        break;
      case 'task_progress':
      case 'task_completed':
      case 'task_failed':
      case 'task_started':
        this.emit(type, message);
        this.emit('task_progress', message);
        break;
      case 'interaction_update':
      case 'notification':
      case 'research_result':
      case 'experience_generated':
      case 'literature_processed':
      case 'connection_established':
      case 'global_connection_established':
      case 'task_status':
      case 'history_events':
      case 'active_tasks':
        this.emit(type, message);
        break;
      default:
        this.emit('message', message);
    }
  }

  private flushQueue() {
    while (this.messageQueue.length && this.socket?.readyState === WebSocket.OPEN) {
      const message = this.messageQueue.shift();
      if (message) {
        this.dispatch(message.type, message.payload);
      }
    }
  }

  private dispatch(type: string, payload?: Record<string, unknown>) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.messageQueue.push({ type, payload });
      return;
    }

    const body = JSON.stringify({ type, ...(payload || {}) });
    this.socket.send(body);
  }

  subscribe(event: string, handler: EventHandler) {
    this.on(event, handler);
    return () => this.unsubscribe(event, handler);
  }

  unsubscribe(event: string, handler: EventHandler) {
    this.off(event, handler);
  }

  send(type: string, payload?: Record<string, unknown>) {
    this.dispatch(type, payload);
  }

  subscribeToTask(taskId: string) {
    if (!taskId) return;
    this.send('subscribe_task', { task_id: taskId });
  }

  unsubscribeFromTask(taskId: string) {
    if (!taskId) return;
    this.send('unsubscribe_task', { task_id: taskId });
  }

  subscribeToSession(sessionId: string) {
    if (!sessionId) return;
    this.send('subscribe_session', { session_id: sessionId });
  }

  unsubscribeFromSession(sessionId: string) {
    if (!sessionId) return;
    this.send('unsubscribe_session', { session_id: sessionId });
  }

  disconnect() {
    if (this.socket) {
      this.socket.close();
      this.socket = null;
      this.connected = false;
      this.reconnectAttempts = 0;
    }
    this.clearTokenRetry();
  }

  getConnectionStatus(): ConnectionStatus {
    return {
      connected: this.connected,
      reconnectAttempts: this.reconnectAttempts,
    };
  }

  refreshConnection(token?: string) {
    this.disconnect();
    this.connect(this.getActiveBaseUrl(), token);
  }
}

export const wsManager = new WebSocketManager();
