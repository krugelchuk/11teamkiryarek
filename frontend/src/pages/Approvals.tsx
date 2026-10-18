import { useState } from 'react';
import { api } from '../api/endpoints';
import type { HrRequest, RequestStatus } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import RequestDetails, { Summary } from '../components/RequestDetails';
import { Alert, EmptyState, ErrorState, Modal, PageHeader, Spinner, StatusBadge } from '../components/ui';
import { errMsg, useAsync } from '../hooks/useAsync';
import { daysWord, fmtDateTime, fmtPeriod } from '../lib/format';

type Filter = 'pending' | 'all';

export default function Approvals() {
  const { user, refreshUnread } = useAuth();
  const isHr = user?.role === 'hr';
  const list = useAsync(() => api.requests(isHr ? 'all' : 'team'), [isHr]);
  const [filter, setFilter] = useState<Filter>('pending');
  const [deciding, setDeciding] = useState<{ req: HrRequest; decision: 'approved' | 'rejected' } | null>(null);
  const [details, setDetails] = useState<number | null>(null);
  const [flash, setFlash] = useState<string | null>(null);

  const all = list.data?.items ?? [];
  const items = filter === 'pending' ? all.filter((r) => r.status === 'pending') : all;
  const pendingCount = all.filter((r) => r.status === 'pending').length;

  return (
    <>
      <PageHeader
        title="Согласование"
        subtitle={isHr ? 'Заявки всех сотрудников' : 'Заявки вашей команды'}
        actions={
          <div className="seg" role="tablist">
            <button role="tab" aria-selected={filter === 'pending'} className={filter === 'pending' ? 'on' : ''} onClick={() => setFilter('pending')}>
              Ожидают ({pendingCount})
            </button>
            <button role="tab" aria-selected={filter === 'all'} className={filter === 'all' ? 'on' : ''} onClick={() => setFilter('all')}>
              Все
            </button>
          </div>
        }
      />
      {flash && <Alert kind="success">{flash}</Alert>}

      <section className="card">
        {list.loading && !list.data ? (
          <Spinner />
        ) : list.error && !list.data ? (
          <ErrorState error={list.error} onRetry={list.reload} />
        ) : items.length === 0 ? (
          <EmptyState title={filter === 'pending' ? 'Нет заявок, ожидающих решения' : 'Заявок нет'} hint="Новые заявки появятся здесь, и вы получите уведомление." />
        ) : (
          <div className="table-wrap">
            <table className="table">
              <thead>
                <tr>
                  <th>Сотрудник</th>
                  <th>Период</th>
                  <th>Дней</th>
                  <th>Комментарий</th>
                  <th>Статус</th>
                  <th aria-label="Действия" />
                </tr>
              </thead>
              <tbody>
                {items.map((r) => {
                  const own = r.user_id === user?.id;
                  return (
                    <tr key={r.id}>
                      <td>
                        <button className="link-btn" onClick={() => setDetails(r.id)}>
                          {r.employee_name}
                        </button>
                        <div className="muted small">{r.department}</div>
                      </td>
                      <td>
                        {fmtPeriod(r.start_date, r.end_date)}
                        <div className="muted small">{fmtDateTime(r.created_at)}</div>
                      </td>
                      <td>{r.days}</td>
                      <td className="cell-comment">{r.comment || '—'}</td>
                      <td>
                        <StatusBadge status={r.status} />
                      </td>
                      <td className="cell-actions">
                        {r.status === 'pending' ? (
                          own ? (
                            <span className="muted small">Свою заявку согласовать нельзя</span>
                          ) : (
                            <>
                              <button className="btn btn-primary btn-sm" onClick={() => setDeciding({ req: r, decision: 'approved' })}>
                                Одобрить
                              </button>
                              <button className="btn btn-danger-outline btn-sm" onClick={() => setDeciding({ req: r, decision: 'rejected' })}>
                                Отклонить
                              </button>
                            </>
                          )
                        ) : (
                          <button className="btn btn-secondary btn-sm" onClick={() => setDetails(r.id)}>
                            Карточка
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {deciding && (
        <DecisionModal
          req={deciding.req}
          decision={deciding.decision}
          onClose={() => setDeciding(null)}
          onDone={async (msg) => {
            setDeciding(null);
            setFlash(msg);
            await list.reload();
            void refreshUnread();
          }}
          onConflict={async () => {
            await list.reload();
          }}
        />
      )}
      {details != null && <RequestDetails id={details} onClose={() => setDetails(null)} onChanged={() => void list.reload()} />}
    </>
  );
}

function DecisionModal({
  req,
  decision,
  onClose,
  onDone,
  onConflict,
}: {
  req: HrRequest;
  decision: 'approved' | 'rejected';
  onClose: () => void;
  onDone: (msg: string) => void | Promise<void>;
  onConflict: () => void | Promise<void>;
}) {
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const reject = decision === 'rejected';
  const missing = reject && !comment.trim();

  async function submit() {
    if (missing) {
      setError('При отклонении комментарий обязателен.');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const r = await api.decide(req.id, decision, comment.trim());
      const label: Record<RequestStatus, string> = { approved: 'одобрена', rejected: 'отклонена', pending: 'обновлена', cancelled: 'отменена' };
      await onDone(`Заявка № ${r.id} (${r.employee_name}) ${label[r.status]}.`);
    } catch (e) {
      setError(errMsg(e));
      // 409 — решение уже принято/заявка изменилась: подтянуть актуальный список
      if (typeof e === 'object' && e && 'status' in e && (e as { status: number }).status === 409) await onConflict();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={reject ? 'Отклонить заявку' : 'Одобрить заявку'} onClose={onClose}>
      <Summary r={req} />
      <p className="muted small">
        {reject ? 'Укажите причину — сотрудник увидит её в уведомлении.' : `Будет списано ${daysWord(req.days)} из остатка сотрудника (если остатка достаточно).`}
      </p>
      {error && <Alert>{error}</Alert>}
      <label className="field">
        <span>Комментарий{reject ? ' (обязательно)' : ' (необязательно)'}</span>
        <textarea rows={3} value={comment} onChange={(e) => setComment(e.target.value)} maxLength={500} autoFocus />
      </label>
      <div className="modal-actions">
        <button className="btn btn-secondary" onClick={onClose} disabled={busy}>
          Отмена
        </button>
        <button className={`btn ${reject ? 'btn-danger' : 'btn-primary'}`} onClick={submit} disabled={busy || missing}>
          {busy ? 'Сохраняем…' : reject ? 'Отклонить' : 'Одобрить'}
        </button>
      </div>
    </Modal>
  );
}
