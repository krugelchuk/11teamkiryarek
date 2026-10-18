import type { ApiErrorBody } from './types';

/**
 * Базовый URL API.
 * 1) VITE_API_URL, если задан;
 * 2) в development — тот же хост и API на 8000;
 * 3) в собранном приложении — тот же origin, включая выбранный порт.
 */
function resolveBaseUrl(): string {
  const fromEnv = import.meta.env.VITE_API_URL as string | undefined;
  if (fromEnv !== undefined) return fromEnv.trim().replace(/\/+$/, '');
  if (!import.meta.env.DEV) return typeof window !== 'undefined' ? window.location.origin : '';
  const host = typeof window !== 'undefined' && window.location.hostname ? window.location.hostname : 'localhost';
  const protocol = typeof window !== 'undefined' && window.location.protocol === 'https:' ? 'https:' : 'http:';
  return `${protocol}//${host}:8000`;
}

export const API_URL = resolveBaseUrl();

export class ApiError extends Error {
  status: number;
  code: string;
  /** true — сервер не ответил (сеть/CORS/backend не запущен) */
  network: boolean;
  constructor(message: string, status: number, code: string, network = false) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.network = network;
  }
}

// CSRF-токен хранится только в памяти (по контракту).
let csrfToken: string | null = null;
export function setCsrfToken(token: string | null) {
  csrfToken = token;
}

// Подписка на «сессия истекла» (401 вне экрана входа).
type UnauthorizedHandler = () => void;
let onUnauthorized: UnauthorizedHandler | null = null;
export function setUnauthorizedHandler(fn: UnauthorizedHandler | null) {
  onUnauthorized = fn;
}

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH';
  body?: unknown;
  /** для login/me 401 — ожидаемый ответ, глобальный обработчик не нужен */
  silent401?: boolean;
}

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const method = opts.method ?? 'GET';
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (method !== 'GET') {
    headers['Content-Type'] = 'application/json';
    if (csrfToken) headers['X-CSRF-Token'] = csrfToken;
  }

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      credentials: 'include',
      body: method === 'GET' ? undefined : JSON.stringify(opts.body ?? {}),
    });
  } catch {
    throw new ApiError(
      `Сервер недоступен (${API_URL}). Проверьте, что backend запущен, и что фронтенд открыт через тот же хост (localhost).`,
      0,
      'network_error',
      true,
    );
  }

  let data: unknown = null;
  const text = await res.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!res.ok) {
    const err = (data as ApiErrorBody | null)?.error;
    const message = err?.message || `Ошибка запроса (HTTP ${res.status})`;
    const code = err?.code || `http_${res.status}`;
    if (res.status === 401 && !opts.silent401 && onUnauthorized) onUnauthorized();
    throw new ApiError(message, res.status, code);
  }
  return data as T;
}

export const get = <T>(path: string, opts?: Pick<RequestOptions, 'silent401'>) => request<T>(path, opts);
export const post = <T>(path: string, body: unknown = {}, opts?: Pick<RequestOptions, 'silent401'>) =>
  request<T>(path, { method: 'POST', body, ...opts });
export const patch = <T>(path: string, body: unknown = {}) => request<T>(path, { method: 'PATCH', body });
