import { useEffect, useState, type FormEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../api/endpoints';
import type { AppNotification } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { Alert, EmptyState, ErrorState, PageHeader, Spinner } from '../components/ui';
import { errMsg, useAsync } from '../hooks/useAsync';
import { fmtDateTime } from '../lib/format';

export default function Notifications() {
  const { user, setUnread } = useAuth();
  const nav = useNavigate();
  const q = useAsync(() => api.notifications(), []);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const items = q.data?.items ?? [];
  const unread = q.data?.unread_count ?? 0;

  async function reloadAll() {
    await q.reload();
  }

  // счётчик в меню синхронизируем с тем, что вернул сервер
  const serverUnread = q.data?.unread_count;
  useEffect(() => {
    if (serverUnread !== undefined) setUnread(serverUnread);
  }, [serverUnread, setUnread]);

  async function open(n: AppNotification) {
    setError(null);
    try {
      if (!n.is_read) await api.markRead(n.id);
      await reloadAll();
    } catch (e) {
      setError(errMsg(e));
      return;
    }
    if (n.entity_type === 'request') nav(`/requests?open=${n.entity_id}`);
    else if (n.entity_type === 'course') nav(`/academy/${n.entity_id}`);
  }

  async function markOnly(n: AppNotification) {
    setError(null);
    try {
      await api.markRead(n.id);
      await reloadAll();
    } catch (e) {
      setError(errMsg(e));
    }
  }

  async function readAll() {
    setBusy(true);
    setError(null);
    try {
      await api.markAllRead();
      await reloadAll();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Уведомления"
        subtitle={unread > 0 ? `Непрочитанных: ${unread}` : 'Все прочитано'}
        actions={
          <button className="btn btn-secondary" onClick={readAll} disabled={busy || unread === 0}>
            Прочитать все
          </button>
        }
      />
      {error && <Alert>{error}</Alert>}

      <section className="card">
        {q.loading && !q.data ? (
          <Spinner />
        ) : q.error && !q.data ? (
          <ErrorState error={q.error} onRetry={q.reload} />
        ) : items.length === 0 ? (
          <EmptyState title="Уведомлений нет" hint="Здесь появятся изменения статусов заявок и назначения курсов." />
        ) : (
          <ul className="list notif-list">
            {items.map((n) => (
              <li key={n.id} className={`list-item notif ${n.is_read ? '' : 'unread'}`}>
                <button className="notif-main" onClick={() => void open(n)}>
                  <span className={`notif-dot ${n.is_read ? '' : 'on'}`} aria-label={n.is_read ? 'Прочитано' : 'Не прочитано'} />
                  <span>
                    <strong>{n.title}</strong>
                    <span className="muted block">{n.body}</span>
                    <span className="muted small block">
                      {fmtDateTime(n.created_at)} · {n.entity_type === 'request' ? 'Заявка' : n.entity_type === 'course' ? 'Курс' : n.entity_type} № {n.entity_id}
                    </span>
                  </span>
                </button>
                {!n.is_read && (
                  <button className="btn btn-secondary btn-sm" onClick={() => void markOnly(n)}>
                    Прочитано
                  </button>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>

      {user?.role === 'hr' && <AssignCourse />}
    </>
  );
}

function AssignCourse() {
  const team = useAsync(() => api.team(), []);
  const courses = useAsync(() => api.adminCourses(), []);
  const [userId, setUserId] = useState('');
  const [courseId, setCourseId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setOk(null);
    try {
      await api.assignCourse(Number(userId), Number(courseId));
      const u = team.data?.items.find((x) => x.id === Number(userId));
      const c = courses.data?.items.find((x) => x.id === Number(courseId));
      setOk(`Курс «${c?.title ?? courseId}» назначен: ${u?.name ?? userId}. Сотрудник получит уведомление.`);
      setUserId('');
      setCourseId('');
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  const loading = (team.loading && !team.data) || (courses.loading && !courses.data);
  const loadError = team.error ?? courses.error;

  return (
    <section className="card">
      <h2>Назначить курс сотруднику</h2>
      <p className="muted small">Доступно HR. Если курс уже назначен, система сообщит об этом.</p>
      {loading ? (
        <Spinner />
      ) : loadError && (!team.data || !courses.data) ? (
        <ErrorState
          error={loadError}
          onRetry={() => {
            void team.reload();
            void courses.reload();
          }}
        />
      ) : (
        <form className="form" onSubmit={submit}>
          {error && <Alert>{error}</Alert>}
          {ok && <Alert kind="success">{ok}</Alert>}
          <div className="row-2">
            <label className="field">
              <span>Сотрудник</span>
              <select required value={userId} onChange={(e) => setUserId(e.target.value)}>
                <option value="">Выберите сотрудника</option>
                {team.data!.items.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.name} — {u.position}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Курс</span>
              <select required value={courseId} onChange={(e) => setCourseId(e.target.value)}>
                <option value="">Выберите курс</option>
                {courses.data!.items.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.title} ({c.duration_minutes} мин)
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div>
            <button className="btn btn-primary" disabled={busy || !userId || !courseId}>
              {busy ? 'Назначаем…' : 'Назначить курс'}
            </button>
          </div>
        </form>
      )}
    </section>
  );
}
