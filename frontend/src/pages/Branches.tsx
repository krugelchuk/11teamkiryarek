import { useEffect, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../api/endpoints';
import { branchApi, type Branch, type BranchDetail } from '../api/branches';
import { useAuth } from '../auth/AuthContext';
import AstanaMap from '../components/AstanaMap';
import { Alert, CourseBadge, EmptyState, ErrorState, Modal, PageHeader, Progress, Spinner, StatusBadge } from '../components/ui';
import { errMsg, useAsync } from '../hooks/useAsync';
import { fmtDate as formatDate, initials, ROLE_LABEL, todayISO } from '../lib/format';
import '../branches.css';

const after = (day: string, count: number) => { const date = new Date(`${day}T12:00:00Z`); date.setUTCDate(date.getUTCDate() + count); return date.toISOString().slice(0, 10); };

export default function Branches() {
  const {user} = useAuth();
  const [from, setFrom] = useState(todayISO);
  const [to, setTo] = useState(() => after(todayISO(), 13));
  const [search, setSearch] = useState('');
  const [staffedOnly, setStaffedOnly] = useState(false);
  const [selected, setSelected] = useState<string | null>(null);
  const [revision, setRevision] = useState(0);
  const valid = !!from && !!to && to >= from && to <= after(from, 61);
  const list = useAsync(() => valid ? branchApi.list(from, to) : Promise.resolve(null), [from, to, revision]);
  const items = list.data?.items ?? [];
  useEffect(() => { if (!selected && items.length) setSelected(items.find(b => b.is_mine)?.id ?? items[0].id); }, [items, selected]);
  const visible = items.filter(b => (!staffedOnly || b.member_count > 0) && `${b.address} ${b.district}`.toLocaleLowerCase('ru').includes(search.toLocaleLowerCase('ru')));
  const refresh = () => setRevision(n => n + 1);
  return <>
    <PageHeader title="Команда на карте" subtitle="Астана · реальные адреса Jana Post и календарь отпусков вашей команды" actions={<button className="btn btn-secondary" onClick={refresh}>Обновить данные</button>} />
    <section className="branch-overview">
      <div><span className="branch-kicker">JANA POST / АСТАНА</span><h2>Город один.<br />Команда рядом.</h2><p>Выберите точку на карте, чтобы открыть сотрудников и увидеть пересечения отпусков.</p></div>
      <div className="branch-overview-numbers"><div><strong>{items.length || '—'}</strong><span>проверенных точек</span></div><div><strong>{items.reduce((sum, b) => sum + b.member_count, 0)}</strong><span>сотрудников в вашей области доступа</span></div></div>
    </section>
    <section className="card branch-controls">
      <label className="field"><span>Поиск по адресу или району</span><input placeholder="Например, Сыганак" value={search} onChange={e => setSearch(e.target.value)} /></label>
      <label className="field"><span>Начало периода</span><input type="date" value={from} onChange={e => {setFrom(e.target.value); if (e.target.value) setTo(after(e.target.value, 13));}} /></label>
      <label className="field"><span>Конец периода</span><input type="date" value={to} min={from} max={from ? after(from, 61) : undefined} onChange={e => setTo(e.target.value)} /></label>
      <label className="branch-checkbox"><input type="checkbox" checked={staffedOnly} onChange={e => setStaffedOnly(e.target.checked)} /> С доступными сотрудниками</label>
    </section>
    {!valid ? <Alert>Выберите период от 1 до 62 дней.</Alert> : list.error ? <ErrorState error={list.error} onRetry={list.reload} /> : list.loading ? <Spinner label="Загружаем филиалы и календарь…" /> : <>
      <div className="branch-scope"><strong>{list.data?.scope}</strong><span>{list.data?.demo_mode ? 'Демо: сотрудники и привязки вымышлены, адреса точек реальные.' : 'Сотрудников и привязки к филиалам добавляет HR.'}</span></div>
      <div className="branch-map-layout">
        <section className="branch-list" aria-label="Список филиалов">
          <div className="branch-list-head"><strong>Филиалы</strong><span>{visible.length} из {items.length}</span></div>
          <div className="branch-list-scroll">{visible.length ? visible.map(b => <button key={b.id} className={`branch-list-item ${b.id === selected ? 'active' : ''}`} onClick={() => setSelected(b.id)} aria-pressed={b.id === selected}>
            <span className={`branch-list-number ${b.shortage_days ? 'risk' : ''}`}>{items.indexOf(b) + 1}</span><span><strong>{b.address}</strong><small>{b.district ? `Район ${b.district}` : 'Астана'}{b.is_mine ? ' · Ваш филиал' : ''}</small><span className="branch-list-count">{b.member_count ? `${b.member_count} сотр. · мин. вне отпуска: ${b.min_remaining}` : 'Нет сотрудников в вашей области доступа'}</span>{b.shortage_days > 0 && <em>Ниже минимума: {b.shortage_days} дн.</em>}</span>
          </button>) : <EmptyState title="Точки не найдены" hint="Измените адрес или снимите фильтр." />}</div>
        </section>
        <AstanaMap items={items} selected={selected} onSelect={setSelected} />
      </div>
      <p className="branch-source">Точки: <a href={list.data?.source_url} target="_blank" rel="noreferrer">публичные карточки 2ГИС</a> · сверены 18.10.2026 · выборка из 13 точек, не полный список сети. Подложка © OpenStreetMap. Для подложки нужен интернет.</p>
      {selected && <BranchPanel key={`${selected}-${from}-${to}-${revision}`} id={selected} from={from} to={to} all={items} hr={user?.role === 'hr'} onChange={refresh} />}
    </>}
  </>;
}

function BranchPanel({id, from, to, all, hr, onChange}: {id: string; from: string; to: string; all: Branch[]; hr: boolean; onChange: () => void}) {
  const detail = useAsync(() => branchApi.detail(id, from, to), [id, from, to]);
  const [person, setPerson] = useState<number | null>(null);
  if (detail.loading) return <Spinner />;
  if (detail.error) return <ErrorState error={detail.error} onRetry={detail.reload} />;
  if (!detail.data) return null;
  const d = detail.data;
  return <section className="card branch-detail">
    <div className="branch-detail-head"><div><span className="branch-kicker">JANA POST · ФИЛИАЛ</span><h2>{d.branch.address}</h2><p className="muted">{d.scope} · {formatDate(from)} — {formatDate(to)}</p></div><a className="btn btn-secondary" href={d.branch.source_url} target="_blank" rel="noreferrer">Открыть в 2ГИС ↗</a></div>
    <div className="branch-detail-stats"><div><strong>{d.members.length}</strong><span>сотрудников доступно</span></div><div><strong>{Math.max(...d.calendar.map(day => day.approved))}</strong><span>максимум в отпуске одновременно</span></div><div><strong>{Math.min(...d.calendar.map(day => day.remaining))}</strong><span>минимум вне отпуска</span></div>{hr && <div><strong>{d.branch.min_staff ?? '—'}</strong><span>минимум, заданный HR</span></div>}</div>
    <p className="muted small">Расчёт учитывает только согласованные отпуска. Ожидающие заявки показаны отдельно. Нахождение вне отпуска не подтверждает присутствие на смене; автоматического отказа в отпуске нет.</p>
    {d.members.length ? <>
      <h3>Сотрудники</h3><div className="branch-people">{d.members.map(p => <button key={p.id} className="branch-person" onClick={() => setPerson(p.id)}><span className="avatar">{initials(p.name)}</span><span><strong>{p.name}</strong><small>{p.position} · {ROLE_LABEL[p.role]}</small></span><span aria-hidden>↗</span></button>)}</div>
      <Calendar detail={d} />
    </> : <EmptyState title="Нет доступных вам сотрудников в этом филиале" hint={hr ? 'Назначьте филиал сотруднику ниже.' : 'Сотрудник видит себя, руководитель — себя и прямых подчинённых. Привязку к филиалу задаёт HR.'} />}
    {hr && <BranchSettings id={id} detail={d} all={all} onChange={onChange} />}
    {person !== null && <Modal title="Карточка сотрудника" wide onClose={() => setPerson(null)}><EmployeeCard branchId={id} uid={person} /></Modal>}
  </section>;
}

function Calendar({detail: d}: {detail: BranchDetail}) {
  return <><div className="branch-calendar-heading"><h3>Календарь отпусков</h3><span><i className="leave-key approved" />Согласован <i className="leave-key pending" />Ожидает решения</span></div><div className="branch-calendar-scroll" tabIndex={0} role="region" aria-label="Календарь отпусков, прокрутка по горизонтали"><table className="branch-calendar"><thead><tr><th scope="col">Сотрудник</th>{d.days.map(day => <th key={day} scope="col" title={formatDate(day)}>{day.slice(8)}<small>{day.slice(5, 7)}</small></th>)}</tr></thead><tbody>
    {d.members.map(p => <tr key={p.id}><th scope="row">{p.name}</th>{d.days.map(day => {
      const leaves = d.leaves.filter(r => r.user_id === p.id && r.start_date <= day && r.end_date >= day);
      const state = leaves.some(r => r.status === 'approved') ? 'approved' : leaves.length ? 'pending' : '';
      return <td key={day} className={state ? `leave-${state}` : ''} title={`${p.name} · ${formatDate(day)}: ${state === 'approved' ? 'согласованный отпуск' : state === 'pending' ? 'ожидает решения' : 'нет отпуска'}`}><span>{state === 'approved' ? 'О' : state === 'pending' ? '?' : '·'}</span></td>;
    })}</tr>)}
    <tr className="coverage-row"><th scope="row">Вне согласованного отпуска</th>{d.calendar.map(day => <td key={day.date} className={day.shortage ? 'coverage-risk' : ''} title={day.shortage ? 'Ниже минимума HR' : 'Без учёта графика смен'}>{day.remaining}</td>)}</tr>
    </tbody></table></div>{d.calendar.some(day => day.shortage) && <Alert kind="info">В отмеченные дни число сотрудников вне отпуска ниже минимума, заданного HR. Согласование остаётся за руководителем и HR.</Alert>}</>;
}

function BranchSettings({id, detail, all, onChange}: {id: string; detail: BranchDetail; all: Branch[]; onChange: () => void}) {
  const staff = useAsync(() => api.team(), []);
  const [uid, setUid] = useState('');
  const [target, setTarget] = useState(id);
  const [minimum, setMinimum] = useState(detail.branch.min_staff?.toString() ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function save(e: FormEvent, action: 'assign' | 'minimum') {
    e.preventDefault(); setBusy(true); setError(null);
    try { if (action === 'assign') await branchApi.assign(Number(uid), target || null); else await branchApi.configure(id, minimum === '' ? null : Number(minimum)); onChange(); }
    catch (err) { setError(errMsg(err)); } finally { setBusy(false); }
  }
  return <details className="branch-settings"><summary>Управление филиалом · HR</summary>{error && <Alert>{error}</Alert>}<div className="branch-settings-grid">
    <form className="form" onSubmit={e => void save(e, 'assign')}><h3>Привязка сотрудника</h3>{staff.error && <ErrorState error={staff.error} onRetry={staff.reload} />}<label className="field"><span>Сотрудник</span><select required value={uid} onChange={e => setUid(e.target.value)}><option value="">Выберите сотрудника</option>{staff.data?.items.map(p => <option value={p.id} key={p.id}>{p.name} · {p.branch_address ?? 'без филиала'}</option>)}</select></label><label className="field"><span>Филиал</span><select value={target} onChange={e => setTarget(e.target.value)}><option value="">Без филиала</option>{all.map(b => <option key={b.id} value={b.id}>{b.address}</option>)}</select></label><button className="btn btn-primary" disabled={busy || !uid || staff.loading}>Сохранить привязку</button></form>
    <form className="form" onSubmit={e => void save(e, 'minimum')}><h3>Минимум вне отпуска</h3><p className="muted small">Порог для всего филиала задаёт HR. Это ориентир для планирования, а не правило компании или оценка того, «заслужен» ли отпуск.</p><label className="field"><span>Минимум сотрудников · пусто = не задан</span><input type="number" min="0" max="10000" step="1" value={minimum} onChange={e => setMinimum(e.target.value)} /></label><button className="btn btn-secondary" disabled={busy}>Сохранить минимум</button></form>
  </div></details>;
}

function EmployeeCard({branchId, uid}: {branchId: string; uid: number}) {
  const data = useAsync(() => branchApi.employee(branchId, uid), [branchId, uid]);
  if (data.loading) return <Spinner />;
  if (data.error) return <ErrorState error={data.error} onRetry={data.reload} />;
  if (!data.data) return null;
  const {profile: p, courses, requests} = data.data;
  return <div className="branch-employee-detail"><div className="branch-employee-heading"><span className="avatar">{initials(p.name)}</span><div><h2>{p.name}</h2><p>{p.position} · {p.department}</p></div></div><dl className="branch-profile"><div><dt>Филиал</dt><dd>{p.branch_address}</dd></div><div><dt>Руководитель</dt><dd>{p.manager_name ?? 'Не назначен'}</dd></div><div><dt>Email</dt><dd>{p.email}</dd></div><div><dt>Остаток отпуска</dt><dd>{p.vacation_balance} дн.</dd></div></dl>
    <h3>Обучение · Jana Academy</h3>{courses.length ? courses.map(c => <div key={c.id} className="branch-course"><div><strong>{c.title}</strong><CourseBadge status={c.status} /></div><Progress value={c.progress} label={c.title} /></div>) : <p className="muted">Курсы пока не назначены.</p>}
    <h3>Заявки на отпуск</h3>{requests.length ? <div className="branch-requests">{requests.map(r => <div key={r.id}><span>№{r.id} · {formatDate(r.start_date)} — {formatDate(r.end_date)}</span><StatusBadge status={r.status} /></div>)}</div> : <p className="muted">Заявок пока нет.</p>}<Link className="btn btn-secondary" to="/requests">Открыть мои заявки</Link>
  </div>;
}
