import { useState, type FormEvent } from 'react';
import { useSearchParams } from 'react-router-dom';
import { api } from '../api/endpoints';
import { useAuth } from '../auth/AuthContext';
import RequestDetails from '../components/RequestDetails';
import { Alert, EmptyState, ErrorState, PageHeader, Spinner, StatusBadge } from '../components/ui';
import { errMsg, useAsync } from '../hooks/useAsync';
import { TYPE_LABEL, daysWord, fmtDateTime, fmtPeriod, inclusiveDays, todayISO } from '../lib/format';

export default function Requests() {
  const { user, refreshUnread } = useAuth();
  const [params, setParams] = useSearchParams();
  const list = useAsync(() => api.requests('mine'), []);
  const openId = params.get('open') ? Number(params.get('open')) : null;

  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const today = todayISO();
  const days = inclusiveDays(start, end);
  const profile = useAsync(() => api.profile(), []);
  const balance = profile.data?.vacation_balance ?? user?.vacation_balance;
  const datesInvalid = !!start && !!end && end < start;

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setOk(null);
    if (datesInvalid) {
      setError('Дата окончания не может быть раньше даты начала.');
      return;
    }
    setBusy(true);
    try {
      const created = await api.createRequest({ type: 'vacation', start_date: start, end_date: end, comment: comment.trim() });
      setOk(`Заявка № ${created.id} отправлена на согласование.`);
      setStart('');
      setEnd('');
      setComment('');
      await list.reload();
      void refreshUnread();
    } catch (err) {
      setError(errMsg(err));
    } finally {
      setBusy(false);
    }
  }

  function closeDetails() {
    const next = new URLSearchParams(params);
    next.delete('open');
    setParams(next, { replace: true });
  }

  const items = list.data?.items ?? [];

  return (
    <>
      <PageHeader title="Мои заявки" subtitle="Оформите отпуск и отслеживайте статус согласования" />

      <div className="grid-sidebar">
        <section className="card">
          <h2>Новая заявка · отпуск</h2>
          <form onSubmit={submit} className="form">
            {error && <Alert>{error}</Alert>}
            {ok && <Alert kind="success">{ok}</Alert>}
            <div className="row-2">
              <label className="field">
                <span>Дата начала</span>
                <input type="date" required min={today} value={start} onChange={(e) => setStart(e.target.value)} />
              </label>
              <label className="field">
                <span>Дата окончания</span>
                <input type="date" required min={start || today} value={end} onChange={(e) => setEnd(e.target.value)} />
              </label>
            </div>
            <label className="field">
              <span>Комментарий</span>
              <textarea rows={3} value={comment} onChange={(e) => setComment(e.target.value)} maxLength={500} placeholder="Например: семейные планы" />
            </label>
            <div className="calc">
              <div>
                Дней в заявке: <strong>{days ? daysWord(days) : '—'}</strong>
                {balance != null && (
                  <>
                    {' '}
                    · остаток: <strong>{daysWord(balance)}</strong>
                  </>
                )}
              </div>
              {days != null && balance != null && days > balance && (
                <div className="warn small">Недостаточно дней отпуска. Выберите более короткий период — сервер не примет заявку сверх остатка.</div>
              )}
            </div>
            <p className="muted small">
              Упрощение MVP: дни считаются календарно, включительно (выходные и праздники не исключаются). Остаток списывается только после одобрения. Пересекающиеся заявки и прошедшие даты не принимаются.
            </p>
            <button className="btn btn-primary" disabled={busy || !start || !end || datesInvalid || (days != null && balance != null && days > balance)}>
              {busy ? 'Отправляем…' : 'Отправить на согласование'}
            </button>
          </form>
        </section>

        <section className="card">
          <div className="card-head">
            <h2>Список заявок</h2>
            <button className="btn btn-secondary btn-sm" onClick={() => void list.reload()} disabled={list.loading}>
              Обновить
            </button>
          </div>
          {list.loading && !list.data ? (
            <Spinner />
          ) : list.error && !list.data ? (
            <ErrorState error={list.error} onRetry={list.reload} />
          ) : items.length === 0 ? (
            <EmptyState title="Заявок пока нет" hint="Заполните форму слева, чтобы создать первую." />
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>№</th>
                    <th>Тип</th>
                    <th>Период</th>
                    <th>Дней</th>
                    <th>Создана</th>
                    <th>Статус</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((r) => (
                    <tr key={r.id} className="clickable" tabIndex={0} onClick={() => setParams({ open: String(r.id) })} onKeyDown={(e) => e.key === 'Enter' && setParams({ open: String(r.id) })}>
                      <td>{r.id}</td>
                      <td>{TYPE_LABEL[r.type] ?? r.type}</td>
                      <td>{fmtPeriod(r.start_date, r.end_date)}</td>
                      <td>{r.days}</td>
                      <td>{fmtDateTime(r.created_at)}</td>
                      <td>
                        <StatusBadge status={r.status} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {openId != null && !Number.isNaN(openId) && (
        <RequestDetails
          id={openId}
          onClose={closeDetails}
          onChanged={() => {
            void list.reload();
          }}
        />
      )}
    </>
  );
}
