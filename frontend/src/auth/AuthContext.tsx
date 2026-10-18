import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { api } from '../api/endpoints';
import { ApiError, setCsrfToken, setUnauthorizedHandler } from '../api/client';
import type { Profile } from '../api/types';

interface AuthState {
  user: Profile | null;
  /** идёт первичная проверка сессии (GET /api/auth/me) */
  booting: boolean;
  /** backend недоступен при старте */
  bootError: ApiError | null;
  /** сессия истекла посреди работы */
  sessionExpired: boolean;
  /** непрочитанные уведомления (для бейджа в меню) */
  unread: number;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refreshUnread: () => Promise<void>;
  setUnread: (n: number) => void;
  retryBoot: () => void;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Profile | null>(null);
  const [booting, setBooting] = useState(true);
  const [bootError, setBootError] = useState<ApiError | null>(null);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [unread, setUnread] = useState(0);
  const [bootTick, setBootTick] = useState(0);

  useEffect(() => {
    let alive = true;
    setBooting(true);
    setBootError(null);
    api
      .me()
      .then((r) => alive && setUser(r.user))
      .catch((e: unknown) => {
        if (!alive) return;
        if (e instanceof ApiError && e.status === 401) setUser(null);
        else if (e instanceof ApiError) setBootError(e);
      })
      .finally(() => alive && setBooting(false));
    return () => {
      alive = false;
    };
  }, [bootTick]);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      setCsrfToken(null);
      setUser((u) => {
        if (u) setSessionExpired(true);
        return null;
      });
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  const refreshUnread = useCallback(async () => {
    try {
      const r = await api.notifications();
      setUnread(r.unread_count);
    } catch {
      /* бейдж не критичен; ошибки показывает сам экран уведомлений */
    }
  }, []);

  useEffect(() => {
    if (!user) {
      setUnread(0);
      return;
    }
    void refreshUnread();
    const t = window.setInterval(() => void refreshUnread(), 60000);
    return () => window.clearInterval(t);
  }, [user, refreshUnread]);

  const login = useCallback(async (email: string, password: string) => {
    const r = await api.login(email, password);
    setSessionExpired(false);
    setUser(r.user);
  }, []);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error;
      setCsrfToken(null);
    }
    setUser(null);
    setSessionExpired(false);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      booting,
      bootError,
      sessionExpired,
      unread,
      login,
      logout,
      refreshUnread,
      setUnread,
      retryBoot: () => setBootTick((t) => t + 1),
    }),
    [user, booting, bootError, sessionExpired, unread, login, logout, refreshUnread],
  );

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAuth вне AuthProvider');
  return v;
}
