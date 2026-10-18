import { useState } from 'react';
import { api } from '../api/endpoints';
import type { HrRequest, HrRequestDetails } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { errMsg, useAsync } from '../hooks/useAsync';
import { STATUS_LABEL, TYPE_LABEL, daysWord, fmtDateTime, fmtPeriod } from '../lib/format';
import { Alert, ErrorState, Modal, Spinner, StatusBadge } from './ui';

interface Props {
  id: number;
  onClose: () => void;
  /** вызвать после изменения заявки, чтобы родитель обновил список */
  onChanged: () => void;
}

/** Карточка заявки с историей. Отмена — только своей pending-заявки. */
export default function RequestDetails({ id, onClose, onChanged }: Props) {
  const { user, refreshUnread } = useAuth();
  const q = useAsync<HrRequestDetails>(() => api.request(id), [id]);
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirm, setConfirm] = useState(false);

  const r = q.data;
  const canCancel = !!r && !!user && r.user_id === user.id && r.status === 'pending';

  async function cancel() {
    setBusy(true);
    setError(null);
    try {
      await api.cancel(id, comment.trim() || undefined);
      setConfirm(false);
      setComment('');
      await q.reload();
      onChanged();
      void refreshUnread();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={`Заявка № ${id}`} onClose={onClose} wide>
      {q.loading && !r ? (
        <Spinner />
      ) : q.error && !r ? (
        <ErrorState error={q.error} onRetry={q.reload} />
      ) : r ? (
        <>
          <Summary r={r} />
          <h3>История</h3>
          {r.history.length === 0 ? (
            <p className="muted">История пуста.</p>
          ) : (
            <ol className="timeline">
              {r.history.map((h) => (
                <li key={h.id}>
                  <span className={`dot dot-${h.status}`} aria-hidden />
                  <div>
                    <div>
                      <strong>{STATUS_LABEL[h.status] ?? h.status}</strong> · {h.actor_name}
                    </div>
                    {h.comment && <div className="quote">«{h.comment}»</div>}
                    <div className="muted small">{fmtDateTime(h.created_at)}</div>
                  </div>
                </li>
              ))}
            </ol>
          )}

          {error && <Alert>{error}</Alert>}
          {canCancel && !confirm && (
            <div className="modal-actions">
              <button className="btn btn-danger-outline" onClick={() => setConfirm(true)}>
                Отменить заявку
              </button>
            </div>
          )}
          {canCancel && confirm && (
            <div className="confirm-box">
              <label className="field">
                <span>Комментарий к отмене (необязательно)</span>
                <textarea rows={2} value={comment} onChange={(e) => setComment(e.target.value)} maxLength={500} />
              </label>
              <div className="modal-actions">
                <button className="btn btn-secondary" onClick={() => setConfirm(false)} disabled={busy}>
                  Назад
                </button>
                <button className="btn btn-danger" onClick={cancel} disabled={busy}>
                  {busy ? 'Отменяем…' : 'Подтвердить отмену'}
                </button>
              </div>
            </div>
          )}
        </>
      ) : null}
    </Modal>
  );
}

export function Summary({ r }: { r: HrRequest }) {
  return (
    <dl className="kv">
      <dt>Тип</dt>
      <dd>{TYPE_LABEL[r.type] ?? r.type}</dd>
      <dt>Сотрудник</dt>
      <dd>
        {r.employee_name} <span className="muted">· {r.department}</span>
      </dd>
      <dt>Период</dt>
      <dd>
        {fmtPeriod(r.start_date, r.end_date)} <span className="muted">· {daysWord(r.days)}</span>
      </dd>
      <dt>Статус</dt>
      <dd>
        <StatusBadge status={r.status} />
      </dd>
      <dt>Комментарий</dt>
      <dd>{r.comment || '—'}</dd>
      <dt>Создана</dt>
      <dd>{fmtDateTime(r.created_at)}</dd>
      {r.reviewer_name && (
        <>
          <dt>Рассмотрел(а)</dt>
          <dd>{r.reviewer_name}</dd>
        </>
      )}
      {r.decision_comment && (
        <>
          <dt>Комментарий решения</dt>
          <dd>{r.decision_comment}</dd>
        </>
      )}
    </dl>
  );
}
