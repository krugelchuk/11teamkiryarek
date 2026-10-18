import { useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/endpoints';
import type { ArticleBody, AdminArticle, AdminCourse, CourseBody, NewEmployee, Role } from '../api/types';
import { useAuth } from '../auth/AuthContext';
import { Alert, EmptyState, ErrorState, PageHeader, Spinner } from '../components/ui';
import { errMsg, useAsync } from '../hooks/useAsync';
import { ROLE_LABEL, todayISO } from '../lib/format';

type Tab = 'people' | 'knowledge' | 'courses';

export default function Administration() {
  const [tab, setTab] = useState<Tab>('people');
  const pack = useAsync(() => api.learningPack(), []);
  const [importing, setImporting] = useState(false);
  const [importError, setImportError] = useState<string | null>(null);
  const [importResult, setImportResult] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  async function importPack() {
    setImporting(true); setImportError(null); setImportResult(null);
    try {
      const result = await api.importLearningPack();
      setImportResult(`Добавлено документов: ${result.created_documents}, курсов: ${result.created_courses}. Ранее добавленные материалы сохранены.`);
      await pack.reload(); setRevision(value => value + 1);
    } catch (error) { setImportError(errMsg(error)); }
    finally { setImporting(false); }
  }
  const imported = pack.data && pack.data.imported_documents === pack.data.documents_count && pack.data.imported_courses === pack.data.courses_count;
  return <>
    <PageHeader title="Управление данными" subtitle="Добавляйте сотрудников, учебные материалы и документы организации" actions={<Link className="btn btn-secondary" to="/integrations">1С и Documentolog ↗</Link>} />
    <section className="card" style={{marginBottom: 24}}>
      <h2>{pack.data?.title ?? 'Учебные материалы прототипа'}</h2>
      <p className="muted small">{pack.data?.disclaimer ?? 'Необязательный набор памяток и курсов. Ваши данные не заменяются.'}</p>
      {importError && <Alert>{importError}</Alert>}{importResult && <Alert kind="success">{importResult}</Alert>}
      {pack.error ? <ErrorState error={pack.error} onRetry={pack.reload} /> :
        <button className="btn btn-secondary" onClick={() => void importPack()} disabled={importing || pack.loading || !!imported}>{importing ? 'Добавляем…' : imported ? 'Учебный комплект уже добавлен' : 'Добавить учебный комплект'}</button>}
    </section>
    <div className="seg admin-tabs" role="tablist">
      {([['people', 'Сотрудники'], ['knowledge', 'База знаний'], ['courses', 'Курсы']] as [Tab, string][]).map(([key, title]) =>
        <button key={key} role="tab" aria-selected={tab === key} className={tab === key ? 'on' : ''} onClick={() => setTab(key)}>{title}</button>)}
    </div>
    {tab === 'people' ? <People key={`people-${revision}`} /> : tab === 'knowledge' ? <Documents key={`documents-${revision}`} /> : <CourseEditor key={`courses-${revision}`} />}
  </>;
}

function People() {
  const { user } = useAuth();
  const list = useAsync(() => api.team(), []);
  const blank = (): NewEmployee => ({name: '', email: '', password: '', company: user?.company ?? '', role: 'employee', position: '', department: '', manager_id: null, hire_date: todayISO(), vacation_balance: 0});
  const [form, setForm] = useState(blank);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(null); setOk(null);
    try {
      const added = await api.createEmployee(form);
      setOk(`Создан сотрудник ${added.name}. Передайте ему указанный email и пароль лично.`);
      setForm(blank()); await list.reload();
    } catch (e) { setError(errMsg(e)); } finally { setBusy(false); }
  }
  return <div className="grid-2">
    <section className="card"><h2>Новый сотрудник</h2><p className="muted small">Локальный справочник. После создания сотрудник видит свой профиль только для чтения. Подключение официальной кадровой системы — отдельный этап.</p>
      <form className="form" onSubmit={submit}>
        {error && <Alert>{error}</Alert>}{ok && <Alert kind="success">{ok}</Alert>}
        <label className="field"><span>Ф.И.О.</span><input required maxLength={150} value={form.name} onChange={e => setForm({...form, name: e.target.value})} /></label>
        <div className="row-2">
          <label className="field"><span>Email</span><input required type="email" value={form.email} onChange={e => setForm({...form, email: e.target.value})} /></label>
          <label className="field"><span>Пароль · минимум 10 символов</span><input required autoComplete="new-password" type="password" minLength={10} maxLength={256} value={form.password} onChange={e => setForm({...form, password: e.target.value})} /></label>
        </div>
        <div className="row-2">
          <label className="field"><span>Компания</span><input required value={form.company} onChange={e => setForm({...form, company: e.target.value})} /></label>
          <label className="field"><span>Роль</span><select value={form.role} onChange={e => setForm({...form, role: e.target.value as Role})}>{(['employee','manager','hr'] as Role[]).map(role => <option key={role} value={role}>{ROLE_LABEL[role]}</option>)}</select></label>
        </div>
        <div className="row-2">
          <label className="field"><span>Должность</span><input value={form.position} onChange={e => setForm({...form, position: e.target.value})} /></label>
          <label className="field"><span>Подразделение</span><input value={form.department} onChange={e => setForm({...form, department: e.target.value})} /></label>
        </div>
        <label className="field"><span>Руководитель</span><select value={form.manager_id ?? ''} onChange={e => setForm({...form, manager_id: e.target.value ? Number(e.target.value) : null})}><option value="">Без руководителя · согласует HR</option>{list.data?.items.filter(person => person.role !== 'employee').map(person => <option key={person.id} value={person.id}>{person.name}</option>)}</select></label>
        <div className="row-2">
          <label className="field"><span>Дата приёма</span><input required type="date" value={form.hire_date} onChange={e => setForm({...form, hire_date: e.target.value})} /></label>
          <label className="field"><span>Доступно дней отпуска</span><input required type="number" min={0} max={365} value={form.vacation_balance} onChange={e => setForm({...form, vacation_balance: Number(e.target.value)})} /></label>
        </div>
        <button className="btn btn-primary" disabled={busy}>{busy ? 'Создаём…' : 'Добавить сотрудника'}</button>
      </form>
    </section>
    <section className="card"><h2>Сотрудники организации</h2>
      {list.loading && !list.data ? <Spinner /> : list.error ? <ErrorState error={list.error} onRetry={list.reload} /> : <ul className="list">{list.data?.items.map(person => <li className="list-item col" key={person.id}><strong>{person.name}</strong><span>{person.email}</span><span className="muted small">{ROLE_LABEL[person.role]} · {person.department || 'Без подразделения'} · {person.vacation_balance} дн.</span><span className="muted small">Руководитель: {person.manager_name ?? '—'}</span></li>)}</ul>}
    </section>
  </div>;
}

const blankArticle = (): ArticleBody => ({title: '', summary: '', content: '', roles: ['employee','manager','hr'], is_active: true});

function Documents() {
  const list = useAsync(() => api.adminArticles(), []);
  const [id, setId] = useState<number | undefined>();
  const [form, setForm] = useState(blankArticle);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  function edit(article: AdminArticle) {
    setId(article.id); setForm({title: article.title, summary: article.summary, content: article.content, roles: article.roles, is_active: article.is_active}); setError(null); setOk(null);
  }
  async function save(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(null); setOk(null);
    try { await api.saveArticle(form, id); setOk('Документ сохранён. Поиск помощника уже использует обновлённый текст.'); setId(undefined); setForm(blankArticle()); await list.reload(); }
    catch (e) { setError(errMsg(e)); } finally { setBusy(false); }
  }
  return <div className="grid-2">
    <section className="card"><h2>{id ? 'Редактировать документ' : 'Новый документ'}</h2><p className="muted small">Помощник ищет по тексту опубликованных документов. Отдельные ключевые слова и заготовленные вопросы не нужны.</p>
      <form className="form" onSubmit={save}>
        {error && <Alert>{error}</Alert>}{ok && <Alert kind="success">{ok}</Alert>}
        <label className="field"><span>Название</span><input required maxLength={200} value={form.title} onChange={e => setForm({...form, title: e.target.value})} /></label>
        <label className="field"><span>Краткое описание</span><input maxLength={500} value={form.summary} onChange={e => setForm({...form, summary: e.target.value})} /></label>
        <label className="field"><span>Текст документа</span><textarea required rows={12} maxLength={40000} value={form.content} onChange={e => setForm({...form, content: e.target.value})} /></label>
        <fieldset className="admin-choices"><legend>Кому доступен документ</legend>{(['employee','manager','hr'] as Role[]).map(role => <label key={role}><input type="checkbox" checked={form.roles.includes(role)} onChange={e => setForm({...form, roles: e.target.checked ? [...form.roles, role] : form.roles.filter(item => item !== role)})} />{ROLE_LABEL[role]}</label>)}</fieldset>
        <label className="admin-check"><input type="checkbox" checked={form.is_active} onChange={e => setForm({...form, is_active: e.target.checked})} />Опубликован и участвует в поиске</label>
        <div className="row-2"><button className="btn btn-primary" disabled={busy || !form.roles.length}>{busy ? 'Сохраняем…' : 'Сохранить документ'}</button>{id && <button type="button" className="btn btn-secondary" onClick={() => {setId(undefined); setForm(blankArticle());}}>Отмена редактирования</button>}</div>
      </form>
    </section>
    <section className="card"><h2>База знаний</h2>{list.loading && !list.data ? <Spinner /> : list.error ? <ErrorState error={list.error} onRetry={list.reload} /> : !list.data?.items.length ? <EmptyState title="Документов ещё нет" hint="Добавьте регламент, памятку или ответы на частые вопросы." /> : <ul className="list">{list.data.items.map(article => <li key={article.id} className="list-item col"><strong>{article.title}</strong><span className="muted small">{article.summary}</span><span className="muted small">{article.is_active ? 'Опубликован' : 'Снят с публикации'} · {article.roles.map(role => ROLE_LABEL[role]).join(', ')}</span><button className="btn btn-secondary btn-sm" onClick={() => edit(article)}>Редактировать</button></li>)}</ul>}</section>
  </div>;
}

const blankCourse = (): CourseBody => ({title:'', description:'', duration_minutes:10, lessons:[{title:'',content:''}], question:'', options:['',''], correct_index:0});

function CourseEditor() {
  const list = useAsync(() => api.adminCourseDetails(), []);
  const [id, setId] = useState<number | undefined>();
  const [form, setForm] = useState(blankCourse);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  function load(course: AdminCourse, asNew: boolean) {
    setId(asNew ? undefined : course.id);
    setForm({title: course.title, description: course.description, duration_minutes: course.duration_minutes, lessons: course.lessons.map(l => ({title:l.title,content:l.content})), question: course.question, options: course.options, correct_index: course.correct_index});
    setError(null); setOk(asNew ? 'Материалы скопированы в новую версию. Измените название и сохраните курс.' : null);
  }
  async function submit(e: FormEvent) {
    e.preventDefault(); setBusy(true); setError(null); setOk(null);
    try { await api.saveCourse(form, id); setForm(blankCourse()); setId(undefined); setOk('Курс сохранён. Назначьте его сотруднику в разделе «Уведомления».'); await list.reload(); }
    catch (e) { setError(errMsg(e)); } finally { setBusy(false); }
  }
  function changeLesson(index: number, field: 'title' | 'content', value: string) {
    setForm({...form, lessons: form.lessons.map((lesson, i) => i === index ? {...lesson,[field]:value} : lesson)});
  }
  return <div className="grid-2">
    <section className="card"><h2>{id ? 'Редактировать неназначенный курс' : 'Новый курс'}</h2>
      <form className="form" onSubmit={submit}>
        {error && <Alert>{error}</Alert>}{ok && <Alert kind="success">{ok}</Alert>}
        <label className="field"><span>Название курса</span><input required maxLength={200} value={form.title} onChange={e => setForm({...form,title:e.target.value})} /></label>
        <label className="field"><span>Описание</span><textarea rows={2} maxLength={2000} value={form.description} onChange={e => setForm({...form,description:e.target.value})} /></label>
        <label className="field"><span>Продолжительность, минут</span><input required type="number" min={1} max={10000} value={form.duration_minutes} onChange={e => setForm({...form,duration_minutes:Number(e.target.value)})} /></label>
        {form.lessons.map((lesson, index) => <fieldset className="admin-lesson" key={index}><legend>Урок {index+1}</legend>
          <label className="field"><span>Название урока</span><input required maxLength={200} value={lesson.title} onChange={e => changeLesson(index,'title',e.target.value)} /></label>
          <label className="field"><span>Материал</span><textarea required rows={5} maxLength={20000} value={lesson.content} onChange={e => changeLesson(index,'content',e.target.value)} /></label>
          {form.lessons.length > 1 && <button type="button" className="btn btn-secondary btn-sm" onClick={() => setForm({...form,lessons:form.lessons.filter((_, i) => i !== index)})}>Убрать урок</button>}
        </fieldset>)}
        <button type="button" className="btn btn-secondary" disabled={form.lessons.length >= 20} onClick={() => setForm({...form,lessons:[...form.lessons,{title:'',content:''}]})}>+ Добавить урок</button>
        <h3>Итоговый тест</h3>
        <label className="field"><span>Вопрос</span><input required maxLength={1000} value={form.question} onChange={e => setForm({...form,question:e.target.value})} /></label>
        {form.options.map((option,index) => <label className="field" key={index}><span>Вариант {index+1}</span><input required maxLength={500} value={option} onChange={e => setForm({...form,options:form.options.map((value,i) => i===index ? e.target.value : value)})} /></label>)}
        <div className="row-2"><button type="button" className="btn btn-secondary btn-sm" disabled={form.options.length >= 8} onClick={() => setForm({...form,options:[...form.options,'']})}>+ Вариант</button><button type="button" className="btn btn-secondary btn-sm" disabled={form.options.length <= 2} onClick={() => setForm({...form,options:form.options.slice(0,-1),correct_index:Math.min(form.correct_index,form.options.length-2)})}>Убрать последний</button></div>
        <label className="field"><span>Правильный ответ</span><select value={form.correct_index} onChange={e => setForm({...form,correct_index:Number(e.target.value)})}>{form.options.map((_,index) => <option key={index} value={index}>Вариант {index+1}</option>)}</select></label>
        <button className="btn btn-primary" disabled={busy}>{busy ? 'Сохраняем…' : 'Сохранить курс'}</button>
        {id && <button type="button" className="btn btn-secondary" onClick={() => {setId(undefined); setForm(blankCourse());}}>Отмена редактирования</button>}
      </form>
    </section>
    <section className="card"><h2>Каталог курсов</h2><p className="muted small">Назначенные курсы не изменяются задним числом: можно создать новую версию с сохранением прежнего прогресса сотрудников.</p>
      {list.loading && !list.data ? <Spinner /> : list.error ? <ErrorState error={list.error} onRetry={list.reload} /> : !list.data?.items.length ? <EmptyState title="Курсов ещё нет" hint="Добавьте свои уроки и вопрос теста." /> : <ul className="list">{list.data.items.map(course => <li key={course.id} className="list-item col"><strong>{course.title}</strong><span className="muted small">{course.lessons.length} ур. · {course.duration_minutes} мин. · назначений {course.assignment_count}</span><button className="btn btn-secondary btn-sm" onClick={() => load(course,course.assignment_count > 0)}>{course.assignment_count ? 'Создать новую версию' : 'Редактировать'}</button></li>)}</ul>}
    </section>
  </div>;
}
