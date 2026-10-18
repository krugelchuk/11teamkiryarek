import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError } from '../api/client';

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: ApiError | null;
  reload: () => Promise<void>;
  setData: (v: T | null) => void;
}

/** Загрузка данных с loading/error состоянием и ручным reload. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[] = []): AsyncState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ApiError | null>(null);
  const seq = useRef(0);
  const fnRef = useRef(fn);
  fnRef.current = fn;

  const run = useCallback(async () => {
    const id = ++seq.current;
    setLoading(true);
    setError(null);
    try {
      const r = await fnRef.current();
      if (id === seq.current) setData(r);
    } catch (e) {
      if (id === seq.current) setError(e instanceof ApiError ? e : new ApiError(String(e), 0, 'unknown'));
    } finally {
      if (id === seq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void run();
    return () => {
      seq.current++;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return { data, loading, error, reload: run, setData };
}

export function errMsg(e: unknown): string {
  return e instanceof ApiError ? e.message : 'Что-то пошло не так. Попробуйте ещё раз.';
}
