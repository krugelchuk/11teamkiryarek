import { Link } from 'react-router-dom';
import { api } from '../api/endpoints';
import { useAuth } from '../auth/AuthContext';
import { CourseBadge, EmptyState, ErrorState, PageHeader, Progress, Spinner, Stat, StatusBadge } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import { ROLE_LABEL, TYPE_LABEL, daysWord, fmtDate, fmtDateTime, fmtPeriod } from '../lib/format';
import Icon from '../components/Icon';

export default function Dashboard() {
  const { user } = useAuth();
  const dash = useAsync(() => api.dashboard(), []);
  const notes = useAsync(() => api.notifications(), []);

  if (dash.loading && !dash.data) return <Spinner />;
  if (dash.error && !dash.data) return <ErrorState error={dash.error} onRetry={dash.reload} />;
  const d = dash.data;
  if (!d) return null;
  const p = d.profile;
  const canApprove = user?.role === 'manager' || user?.role === 'hr';
  const unreadList = (notes.data?.items ?? []).filter((n) => !n.is_read).slice(0, 4);

  return (
    <>
      <PageHeader
        title={`Здравствуйте, ${p.name}!`}
        subtitle={`${ROLE_LABEL[p.role]} · ${p.position}`}
        actions={
          <Link to="/requests" className="btn btn-primary">
            + Заявка на отпуск
          </Link>
        }
      />

      <section className="workday-banner" aria-label="Быстрые сервисы">
        <div className="workday-intro"><span className="section-eyebrow">QADAM11 · ВАШ РАБОЧИЙ ДЕНЬ</span><h2>Меньше переписок.<br /><span>Больше ясности.</span></h2><p>Оформите отпуск, продолжите обучение или найдите ответ у HR-помощника.</p></div>
        <div className="quick-services">
          <Link to="/requests"><span className="quick-service-icon"><Icon name="doc" size={24} /></span><span className="quick-service-copy"><strong>Мои заявки</strong><small>Подать и узнать статус</small></span><span className="quick-service-arrow" aria-hidden="true">↗</span></Link>
          <Link to="/academy"><span className="quick-service-icon"><Icon name="book" size={24} /></span><span className="quick-service-copy"><strong>Обучение</strong><small>Продолжить свой курс</small></span><span className="quick-service-arrow" aria-hidden="true">↗</span></Link>
          <Link to="/assistant"><span className="quick-service-icon"><Icon name="spark" size={24} /></span><span className="quick-service-copy"><strong>Спросить AI Jana</strong><small>Ответ с источником</small></span><span className="quick-service-arrow" aria-hidden="true">↗</span></Link>
        </div>
      </section>

      <div className={`stats ${canApprove ? 'stats-with-approvals' : ''}`}>
        <Stat label="Остаток отпуска" value={daysWord(p.vacation_balance)} tone="accent" />
        <Stat label="Мои заявки на согласовании" value={d.stats.my_pending} />
        <Stat label="Непрочитанные уведомления" value={d.stats.unread_notifications} tone={d.stats.unread_notifications ? 'warn' : undefined} />
        <Stat label="Курсы: назначено / пройдено" value={`${d.stats.assigned_courses} / ${d.stats.completed_courses}`} />
        {canApprove && <Stat label="Ждут моего решения" value={d.stats.pending_approvals} tone={d.stats.pending_approvals ? 'warn' : undefined} />}
      </div>

      <div className="grid-2">
        <section className="card">
          <h2>Профиль</h2>
          <p className="muted small">Кадровые данные доступны для просмотра. Для исправления обратитесь в HR.</p>
          <dl className="kv">
            <dt>Ф.И.О.</dt>
            <dd>{p.name}</dd>
            <dt>Компания</dt>
            <dd>{p.company}</dd>
            <dt>Должность</dt>
            <dd>{p.position}</dd>
            <dt>Подразделение</dt>
            <dd>{p.department}</dd>
            <dt>Филиал</dt>
            <dd>{p.branch_address ? <Link className="link" to="/branches">{p.branch_address} ↗</Link> : 'Не назначен'}</dd>
            <dt>Руководитель</dt>
            <dd>{p.manager_name ?? '—'}</dd>
            <dt>Дата приёма</dt>
            <dd>{fmtDate(p.hire_date)}</dd>
            <dt>Остаток отпуска</dt>
            <dd>
              <strong>{daysWord(p.vacation_balance)}</strong>
            </dd>
            <dt>Email</dt>
            <dd>{p.email}</dd>
          </dl>
        </section>

        <section className="card">
          <div className="card-head">
            <h2>Уведомления</h2>
            <Link to="/notifications" className="link">
              Все
            </Link>
          </div>
          {notes.loading && !notes.data ? (
            <Spinner />
          ) : notes.error ? (
            <ErrorState error={notes.error} onRetry={notes.reload} />
          ) : unreadList.length === 0 ? (
            <EmptyState title="Нет непрочитанных" hint="Здесь появятся изменения статусов заявок и новые курсы." />
          ) : (
            <ul className="list">
              {unreadList.map((n) => (
                <li key={n.id} className="list-item unread">
                  <div>
                    <strong>{n.title}</strong>
                    <div className="muted small">{n.body}</div>
                  </div>
                  <span className="muted small nowrap">{fmtDateTime(n.created_at)}</span>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card">
          <div className="card-head">
            <h2>Последние заявки</h2>
            <Link to="/requests" className="link">
              Все заявки
            </Link>
          </div>
          {d.recent_requests.length === 0 ? (
            <EmptyState title="Заявок пока нет" hint="Оформите первую заявку на отпуск." action={<Link to="/requests" className="btn btn-secondary">Создать заявку</Link>} />
          ) : (
            <ul className="list">
              {d.recent_requests.map((r) => (
                <li key={r.id} className="list-item">
                  <Link to={`/requests?open=${r.id}`} className="list-link">
                    <div>
                      <strong>
                        {TYPE_LABEL[r.type] ?? r.type} · {fmtPeriod(r.start_date, r.end_date)}
                      </strong>
                      <div className="muted small">{daysWord(r.days)}</div>
                    </div>
                    <StatusBadge status={r.status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section className="card">
          <div className="card-head">
            <h2>Обучение</h2>
            <Link to="/academy" className="link">
              Jana Academy
            </Link>
          </div>
          {d.courses.length === 0 ? (
            <EmptyState title="Курсы не назначены" hint="Назначенные курсы появятся здесь." />
          ) : (
            <ul className="list">
              {d.courses.map((c) => (
                <li key={c.id} className="list-item col">
                  <Link to={`/academy/${c.id}`} className="list-link">
                    <strong>{c.title}</strong>
                    <CourseBadge status={c.status} />
                  </Link>
                  <Progress value={c.progress} label={c.title} />
                  <span className="muted small">
                    {c.progress}% · уроков {c.completed_lessons} из {c.lesson_count}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>
    </>
  );
}
