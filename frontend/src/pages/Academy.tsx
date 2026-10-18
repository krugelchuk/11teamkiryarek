import { Link } from 'react-router-dom';
import { api } from '../api/endpoints';
import { CourseBadge, EmptyState, ErrorState, PageHeader, Progress, Spinner } from '../components/ui';
import { useAsync } from '../hooks/useAsync';
import { fmtDate } from '../lib/format';

export default function Academy() {
  const q = useAsync(() => api.courses(), []);
  const items = q.data?.items ?? [];

  return (
    <>
      <PageHeader title="Jana Academy" subtitle="Назначенные вам курсы: читайте уроки и сдавайте итоговый тест" />
      {q.loading && !q.data ? (
        <Spinner />
      ) : q.error && !q.data ? (
        <ErrorState error={q.error} onRetry={q.reload} />
      ) : items.length === 0 ? (
        <div className="card">
          <EmptyState title="Курсы пока не назначены" hint="Когда HR назначит курс, вы получите уведомление и увидите его здесь." />
        </div>
      ) : (
        <div className="cards">
          {items.map((c) => (
            <article key={c.id} className="card course-card">
              <div className="card-head">
                <h3>{c.title}</h3>
                <CourseBadge status={c.status} />
              </div>
              <p className="muted">{c.description}</p>
              <Progress value={c.progress} label={c.title} />
              <div className="muted small course-meta">
                <span>{c.progress}%</span>
                <span>
                  Уроков: {c.completed_lessons} из {c.lesson_count}
                </span>
                <span>≈ {c.duration_minutes} мин</span>
              </div>
              <div className="muted small">
                Назначен: {fmtDate(c.assigned_at)}
                {c.completed_at && <> · Пройден: {fmtDate(c.completed_at)}</>}
                {c.score != null && <> · Результат: {c.score}%</>}
              </div>
              <Link to={`/academy/${c.id}`} className={`btn ${c.status === 'completed' ? 'btn-secondary' : 'btn-primary'}`}>
                {c.status === 'completed' ? 'Открыть материалы' : c.status === 'assigned' ? 'Начать' : 'Продолжить'}
              </Link>
            </article>
          ))}
        </div>
      )}
    </>
  );
}
