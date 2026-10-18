import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { api } from '../api/endpoints';
import type { CourseSummary, QuizResult } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { Alert, CourseBadge, ErrorState, PageHeader, Progress, Spinner } from '../components/ui';
import { errMsg, useAsync } from '../hooks/useAsync';
import { fmtDate } from '../lib/format';

export default function CourseView() {
  const { id } = useParams();
  const courseId = Number(id);
  const { refreshUnread } = useAuth();
  const q = useAsync(() => api.course(courseId), [courseId]);
  const [openLesson, setOpenLesson] = useState<number | null>(null);
  const [busyLesson, setBusyLesson] = useState<number | null>(null);
  const [answer, setAnswer] = useState<number | null>(null);
  const [quizBusy, setQuizBusy] = useState(false);
  const [result, setResult] = useState<QuizResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (Number.isNaN(courseId)) return <ErrorState error="Некорректный адрес курса." />;
  if (q.loading && !q.data) return <Spinner />;
  if (q.error && !q.data) return <ErrorState error={q.error} onRetry={q.reload} />;
  if (!q.data) return null;

  const { lessons, quiz } = q.data;
  const course: CourseSummary = result?.course ?? q.data.course;
  const allRead = lessons.length > 0 && lessons.every((l) => l.completed);
  const completed = course.status === 'completed';

  async function complete(lessonId: number) {
    setBusyLesson(lessonId);
    setError(null);
    try {
      await api.completeLesson(courseId, lessonId);
      await q.reload(); // уроки + прогресс берём с сервера
      void refreshUnread();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setBusyLesson(null);
    }
  }

  async function submitQuiz() {
    if (answer == null) return;
    setQuizBusy(true);
    setError(null);
    try {
      const r = await api.submitQuiz(courseId, answer);
      setResult(r);
      await q.reload();
      void refreshUnread();
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setQuizBusy(false);
    }
  }

  return (
    <>
      <p className="crumbs">
        <Link to="/academy">← Jana Academy</Link>
      </p>
      <PageHeader title={course.title} subtitle={course.description} actions={<CourseBadge status={course.status} />} />

      <section className="card">
        <Progress value={course.progress} label="Прогресс курса" />
        <div className="muted small course-meta">
          <span>Прогресс: {course.progress}%</span>
          <span>
            Уроков прочитано: {course.completed_lessons} из {course.lesson_count}
          </span>
          <span>≈ {course.duration_minutes} мин</span>
          {course.completed_at && <span>Пройден: {fmtDate(course.completed_at)}</span>}
          {course.score != null && <span>Результат: {course.score}%</span>}
        </div>
        <p className="muted small">После прочтения всех уроков прогресс достигает 90%, 100% — после правильного ответа на итоговый тест.</p>
      </section>

      {error && <Alert>{error}</Alert>}

      <h2 className="section-title">Уроки</h2>
      <div className="lessons">
        {lessons.map((l, i) => {
          const open = openLesson === l.id;
          return (
            <section key={l.id} className={`card lesson ${l.completed ? 'done' : ''}`}>
              <button className="lesson-head" onClick={() => setOpenLesson(open ? null : l.id)} aria-expanded={open}>
                <span className={`lesson-num ${l.completed ? 'ok' : ''}`}>{l.completed ? '✓' : i + 1}</span>
                <span className="lesson-title">{l.title}</span>
                <span className="muted small">{l.completed ? 'Прочитан' : 'Не прочитан'}</span>
                <span aria-hidden>{open ? '▴' : '▾'}</span>
              </button>
              {open && (
                <div className="lesson-body">
                  <div className="pre-text">{l.content}</div>
                  {!l.completed && (
                    <button className="btn btn-primary" disabled={busyLesson === l.id} onClick={() => complete(l.id)}>
                      {busyLesson === l.id ? 'Сохраняем…' : 'Отметить прочитанным'}
                    </button>
                  )}
                </div>
              )}
            </section>
          );
        })}
      </div>

      <h2 className="section-title">Итоговый тест</h2>
      <section className="card">
        {completed ? (
          <Alert kind="success">
            Курс пройден{course.score != null ? `, результат: ${course.score}%` : ''}. Прогресс сохранён в вашем профиле.
          </Alert>
        ) : !allRead ? (
          <Alert kind="info">Сначала прочитайте все уроки — тест откроется после этого.</Alert>
        ) : (
          <>
            <p>
              <strong>{quiz.question}</strong>
            </p>
            <div className="options">
              {quiz.options.map((o, i) => (
                <label key={i} className={`option ${answer === i ? 'on' : ''}`}>
                  <input type="radio" name="quiz" checked={answer === i} onChange={() => setAnswer(i)} />
                  <span>{o}</span>
                </label>
              ))}
            </div>
            <button className="btn btn-primary" disabled={answer == null || quizBusy} onClick={submitQuiz}>
              {quizBusy ? 'Проверяем…' : 'Ответить'}
            </button>
          </>
        )}
        {result && !result.passed && <Alert>Ответ неверный (результат: {result.score}%). Подумайте ещё и попробуйте снова.</Alert>}
        {result && result.passed && <Alert kind="success">Верно! Тест сдан, результат: {result.score}%.</Alert>}
      </section>
    </>
  );
}
